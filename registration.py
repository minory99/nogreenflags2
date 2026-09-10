from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import db
from states import Registration
from keyboards import (
    gender_kb, looking_for_kb, skip_kb, flaws_multiselect_kb, main_menu_kb,
)
from flaws_data import get_flaw_label

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    # обновляем username при каждом /start — он мог поменяться или появиться позже
    db.upsert_user(message.from_user.id, username=message.from_user.username or "")

    user = db.get_user(message.from_user.id)
    if user and user["is_profile_complete"]:
        await message.answer(
            "С возвращением! 👋\nЧто хотите сделать?",
            reply_markup=main_menu_kb(),
        )
        return

    await state.clear()
    await message.answer(
        "Привет! 👋 Это FlawMatch — бот знакомств, где мы находим тебе пару "
        "не по достоинствам, а по совместимости *недостатков*.\n\n"
        "Ты укажешь свои слабые стороны и то, какие недостатки партнёра готов(а) терпеть — "
        "а мы найдём тех, с кем это совпадёт в обе стороны.\n\n"
        "Как тебя зовут?",
        parse_mode="Markdown",
    )
    await state.set_state(Registration.name)


@router.message(Registration.name)
async def reg_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Сколько тебе лет?")
    await state.set_state(Registration.age)


@router.message(Registration.age)
async def reg_age(message: Message, state: FSMContext):
    if not message.text.isdigit() or not (16 <= int(message.text) <= 99):
        await message.answer("Введи возраст числом (16-99).")
        return
    await state.update_data(age=int(message.text))
    await message.answer("Твой пол:", reply_markup=gender_kb())
    await state.set_state(Registration.gender)


@router.callback_query(Registration.gender, F.data.startswith("gender:"))
async def reg_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split(":")[1]
    await state.update_data(gender=gender)
    await callback.message.edit_text(f"Пол: {gender} ✅")
    await callback.message.answer("Кого хочешь найти?", reply_markup=looking_for_kb())
    await state.set_state(Registration.looking_for)
    await callback.answer()


@router.callback_query(Registration.looking_for, F.data.startswith("lf:"))
async def reg_looking_for(callback: CallbackQuery, state: FSMContext):
    lf = callback.data.split(":")[1]
    await state.update_data(looking_for=lf)
    await callback.message.edit_text("Ищу: сохранено ✅")
    await callback.message.answer("Из какого ты города?")
    await state.set_state(Registration.city)
    await callback.answer()


@router.message(Registration.city)
async def reg_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    await message.answer(
        "Расскажи пару слов о себе (можно с юмором про свои же слабости 😉):"
    )
    await state.set_state(Registration.bio)


@router.message(Registration.bio)
async def reg_bio(message: Message, state: FSMContext):
    await state.update_data(bio=message.text.strip())
    await message.answer("Пришли своё фото для анкеты:")
    await state.set_state(Registration.photo)


@router.message(Registration.photo, F.photo)
async def reg_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=photo_id)
    await message.answer(
        "Теперь самое главное 👇\n\n"
        "Выбери *свои недостатки* — то, за что тебя можно поругать. "
        "Можно выбрать несколько, потом нажми «Готово».",
        parse_mode="Markdown",
        reply_markup=flaws_multiselect_kb(set(), mode="flaws"),
    )
    await state.update_data(selected_flaws=[])
    await state.set_state(Registration.flaws_select)


@router.message(Registration.photo)
async def reg_photo_invalid(message: Message):
    await message.answer("Пожалуйста, пришли именно фото (как изображение, не файлом).")


@router.callback_query(Registration.flaws_select, F.data.startswith("flaws:"))
async def reg_flaws_toggle(callback: CallbackQuery, state: FSMContext):
    fid = callback.data.split(":")[1]
    data = await state.get_data()
    selected = set(data.get("selected_flaws", []))
    if fid in selected:
        selected.discard(fid)
    else:
        selected.add(fid)
    await state.update_data(selected_flaws=list(selected))
    await callback.message.edit_reply_markup(reply_markup=flaws_multiselect_kb(selected, mode="flaws"))
    await callback.answer()


@router.callback_query(Registration.flaws_select, F.data == "flaws_done")
async def reg_flaws_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("selected_flaws"):
        await callback.answer("Выбери хотя бы один недостаток 🙂", show_alert=True)
        return
    await callback.message.edit_text("Недостатки сохранены ✅")
    await callback.message.answer(
        "Хочешь добавить недостаток текстом, которого нет в списке? "
        "Напиши его в свободной форме или нажми «Пропустить».",
        reply_markup=skip_kb("skip_flaws_custom"),
    )
    await state.set_state(Registration.flaws_custom)
    await callback.answer()


@router.message(Registration.flaws_custom)
async def reg_flaws_custom_text(message: Message, state: FSMContext):
    await state.update_data(custom_flaws=message.text.strip())
    await _go_to_tolerance(message, state)


@router.callback_query(Registration.flaws_custom, F.data == "skip_flaws_custom")
async def reg_flaws_custom_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(custom_flaws="")
    await callback.message.edit_text("Пропущено")
    await _go_to_tolerance(callback.message, state)
    await callback.answer()


async def _go_to_tolerance(message: Message, state: FSMContext):
    await message.answer(
        "Теперь укажи, какие недостатки партнёра ты готов(а) *терпеть*. "
        "Это ключевая часть матчинга — чем честнее, тем лучше подбор!",
        parse_mode="Markdown",
        reply_markup=flaws_multiselect_kb(set(), mode="tol"),
    )
    await state.update_data(selected_tolerance=[])
    await state.set_state(Registration.tolerance_select)


@router.callback_query(Registration.tolerance_select, F.data.startswith("tol:"))
async def reg_tolerance_toggle(callback: CallbackQuery, state: FSMContext):
    fid = callback.data.split(":")[1]
    data = await state.get_data()
    selected = set(data.get("selected_tolerance", []))
    if fid in selected:
        selected.discard(fid)
    else:
        selected.add(fid)
    await state.update_data(selected_tolerance=list(selected))
    await callback.message.edit_reply_markup(reply_markup=flaws_multiselect_kb(selected, mode="tol"))
    await callback.answer()


@router.callback_query(Registration.tolerance_select, F.data == "tol_done")
async def reg_tolerance_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("selected_tolerance"):
        await callback.answer("Выбери хотя бы один пункт 🙂", show_alert=True)
        return
    await callback.message.edit_text("Толерантность сохранена ✅")
    await callback.message.answer(
        "Что-то ещё готов(а) терпеть, чего нет в списке? Напиши текстом или нажми «Пропустить».",
        reply_markup=skip_kb("skip_tol_custom"),
    )
    await state.set_state(Registration.tolerance_custom)
    await callback.answer()


@router.message(Registration.tolerance_custom)
async def reg_tolerance_custom_text(message: Message, state: FSMContext):
    await state.update_data(custom_tolerance=message.text.strip())
    await _finish_registration(message, state)


@router.callback_query(Registration.tolerance_custom, F.data == "skip_tol_custom")
async def reg_tolerance_custom_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(custom_tolerance="")
    await callback.message.edit_text("Пропущено")
    await _finish_registration(callback.message, state)
    await callback.answer()


async def _finish_registration(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.chat.id

    db.upsert_user(
        user_id,
        name=data["name"],
        age=data["age"],
        gender=data["gender"],
        looking_for=data["looking_for"],
        city=data["city"],
        bio=data["bio"],
        photo_file_id=data["photo_file_id"],
        custom_flaws=data.get("custom_flaws", ""),
        custom_tolerance=data.get("custom_tolerance", ""),
    )
    db.set_user_flaws(user_id, data.get("selected_flaws", []))
    db.set_user_tolerance(user_id, data.get("selected_tolerance", []))
    db.mark_profile_complete(user_id)

    flaws_txt = ", ".join(get_flaw_label(f) for f in data.get("selected_flaws", []))
    await message.answer(
        f"Готово! 🎉 Твоя анкета сохранена.\n\nТвои недостатки: {flaws_txt}\n\n"
        "Теперь можешь смотреть анкеты других.",
        reply_markup=main_menu_kb(),
    )
    await state.clear()
