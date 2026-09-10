from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InputMediaPhoto
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

import db
from matching import compute_compatibility
from keyboards import browse_kb, main_menu_kb, profile_view_kb, match_actions_kb, unmatch_confirm_kb
from flaws_data import get_flaw_label
from config import MIN_COMPAT_THRESHOLD, GOOD_COMPAT_THRESHOLD
from states import Report

router = Router()


def _build_ranked_candidates(user_id: int):
    """
    Ослабляет только порог совместимости, если по нему никого не нашлось —
    но пол по предпочтениям всегда учитывается строго, это не ослабляется:
      1) пол по предпочтениям с обеих сторон + совместимость выше порога
      2) пол по предпочтениям с обеих сторон, порог совместимости не важен
    Возвращает (список [(candidate, result), ...] отсортированный по убыванию совместимости, уровень).
    """
    user = db.get_user(user_id)
    my_flaws = db.get_user_flaws(user_id)
    my_tolerance = db.get_user_tolerance(user_id)

    candidates = db.get_candidates(user_id)

    def gender_ok(c):
        my_side = user["looking_for"] == "any" or c["gender"] == user["looking_for"]
        their_side = c["looking_for"] == "any" or user["gender"] == c["looking_for"]
        return my_side and their_side

    scored = []
    for c in candidates:
        if not gender_ok(c):
            continue
        c_flaws = db.get_user_flaws(c["user_id"])
        c_tolerance = db.get_user_tolerance(c["user_id"])
        result = compute_compatibility(my_flaws, my_tolerance, c_flaws, c_tolerance)
        scored.append((c, result))

    def sorted_by_score(items):
        return sorted(items, key=lambda pair: pair[1].score, reverse=True)

    # Уровень 1: строгий — совместимость выше порога
    level1 = [(c, r) for c, r in scored if r.score >= MIN_COMPAT_THRESHOLD]
    if level1:
        return sorted_by_score(level1), 1

    # Уровень 2: порог совместимости убираем, но пол остаётся строгим фильтром
    if scored:
        return sorted_by_score(scored), 2

    return [], 0


async def _send_candidate(message: Message, candidate, result, level: int = 1):
    flaws = db.get_user_flaws(candidate["user_id"])
    flaws_txt = ", ".join(get_flaw_label(f) for f in flaws) or "—"

    if level == 1:
        badge = "🔥 Отличная совместимость" if result.score >= GOOD_COMPAT_THRESHOLD else "🤝 Есть общая почва"
        note = ""
    else:
        badge = "🤝 Есть общая почва"
        note = "\n\n<i>Подходящих по обычному порогу совместимости анкет не нашлось — показываем варианты пошире.</i>"

    caption = (
        f"<b>{candidate['name']}, {candidate['age']}</b>, {candidate['city']}\n\n"
        f"{candidate['bio']}\n\n"
        f"<b>Недостатки:</b> {flaws_txt}\n\n"
        f"<b>Совместимость: {int(result.score * 100)}%</b> {badge}"
        f"{note}"
    )

    if candidate["photo_file_id"]:
        await message.answer_photo(
            candidate["photo_file_id"],
            caption=caption,
            parse_mode="HTML",
            reply_markup=browse_kb(candidate["user_id"]),
        )
    else:
        await message.answer(
            caption, parse_mode="HTML", reply_markup=browse_kb(candidate["user_id"])
        )


@router.callback_query(F.data == "menu:browse")
async def menu_browse(callback: CallbackQuery):
    await callback.answer()
    await show_next_candidate(callback.message, callback.from_user.id)


async def show_next_candidate(message: Message, user_id: int):
    ranked, level = _build_ranked_candidates(user_id)
    if not ranked:
        await message.answer(
            "Анкет пока нет вообще — загляни позже, база пользователей растёт!",
            reply_markup=main_menu_kb(),
        )
        return
    candidate, result = ranked[0]
    await _send_candidate(message, candidate, result, level)


@router.callback_query(F.data.startswith("pass:"))
async def on_pass(callback: CallbackQuery):
    target_id = int(callback.data.split(":")[1])
    db.record_action(callback.from_user.id, target_id, "pass")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await callback.answer()
    await show_next_candidate(callback.message, callback.from_user.id)


@router.callback_query(F.data.startswith("like:"))
async def on_like(callback: CallbackQuery):
    from_id = callback.from_user.id
    target_id = int(callback.data.split(":")[1])
    db.record_action(from_id, target_id, "like")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    if db.has_mutual_like(from_id, target_id):
        my_flaws = db.get_user_flaws(from_id)
        my_tol = db.get_user_tolerance(from_id)
        their_flaws = db.get_user_flaws(target_id)
        their_tol = db.get_user_tolerance(target_id)
        result = compute_compatibility(my_flaws, my_tol, their_flaws, their_tol)
        db.create_match(from_id, target_id, result.score)

        me = db.get_user(from_id)
        them = db.get_user(target_id)

        await callback.message.answer(
            f"🎉 Это мэтч с {them['name']}! Совместимость {int(result.score*100)}%.",
            reply_markup=match_actions_kb(target_id),
        )
        try:
            await callback.bot.send_message(
                target_id,
                f"🎉 Это мэтч с {me['name']}! Совместимость {int(result.score*100)}%.",
                reply_markup=match_actions_kb(from_id),
            )
        except Exception:
            pass  # пользователь мог заблокировать бота

    await callback.answer("Лайк отправлен ❤️")
    await show_next_candidate(callback.message, from_id)


@router.callback_query(F.data == "menu:matches")
async def menu_matches(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    matches = db.get_matches_for_user(user_id)
    if not matches:
        await callback.message.answer("Пока нет мэтчей. Смотри анкеты и ставь лайки!", reply_markup=main_menu_kb())
        return

    await callback.message.answer(f"<b>У тебя {len(matches)} мэтч(ей):</b>", parse_mode="HTML")
    for m in matches:
        other_id = m["user_b"] if m["user_a"] == user_id else m["user_a"]
        other = db.get_user(other_id)
        if other:
            await callback.message.answer(
                f"{other['name']} — совместимость {int(m['score']*100)}%",
                reply_markup=match_actions_kb(other_id),
            )
    await callback.message.answer("Что дальше?", reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu:back")
async def menu_back(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Главное меню:", reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu:profile")
async def menu_profile(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    flaws = db.get_user_flaws(user_id)
    tolerance = db.get_user_tolerance(user_id)
    flaws_txt = ", ".join(get_flaw_label(f) for f in flaws) or "—"
    tol_txt = ", ".join(get_flaw_label(f) for f in tolerance) or "—"

    caption = (
        f"<b>{user['name']}, {user['age']}</b>, {user['city']}\n\n"
        f"{user['bio']}\n\n"
        f"<b>Мои недостатки:</b> {flaws_txt}\n"
        f"<b>Готов(а) терпеть:</b> {tol_txt}"
    )
    if user["photo_file_id"]:
        await callback.message.answer_photo(user["photo_file_id"], caption=caption, parse_mode="HTML",
                                             reply_markup=profile_view_kb())
    else:
        await callback.message.answer(caption, parse_mode="HTML", reply_markup=profile_view_kb())


# ---------- Разматчить ----------

@router.callback_query(F.data.startswith("unmatch:"))
async def on_unmatch_ask(callback: CallbackQuery):
    other_id = int(callback.data.split(":")[1])
    await callback.message.answer(
        "Точно хочешь разматчиться? Переписка и мэтч исчезнут для вас обоих.",
        reply_markup=unmatch_confirm_kb(other_id),
    )
    await callback.answer()


@router.callback_query(F.data == "unmatch_no")
async def on_unmatch_cancel(callback: CallbackQuery):
    await callback.message.edit_text("Окей, оставляем как есть 🙂")
    await callback.answer()


@router.callback_query(F.data.startswith("unmatch_yes:"))
async def on_unmatch_confirm(callback: CallbackQuery):
    other_id = int(callback.data.split(":")[1])
    me_id = callback.from_user.id
    db.delete_match(me_id, other_id)
    await callback.message.edit_text("Мэтч отменён 💔")
    try:
        await callback.bot.send_message(other_id, "Твой собеседник решил разматчиться.")
    except Exception:
        pass
    await callback.answer()


# ---------- Пожаловаться ----------

@router.callback_query(F.data.startswith("report:"))
async def on_report(callback: CallbackQuery, state: FSMContext):
    other_id = int(callback.data.split(":")[1])
    await state.update_data(report_target=other_id)
    await state.set_state(Report.waiting_reason)
    await callback.message.answer("Опиши коротко, что случилось (увидят только модераторы):")
    await callback.answer()


@router.message(Report.waiting_reason)
async def on_report_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get("report_target")
    db.create_report(message.from_user.id, target_id, message.text.strip() if message.text else "")
    await message.answer("Спасибо, жалоба отправлена на рассмотрение 🙏", reply_markup=main_menu_kb())
    await state.clear()
