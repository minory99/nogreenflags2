from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

import db
from states import EditProfile
from keyboards import (
    edit_menu_kb, gender_kb, looking_for_kb, flaws_multiselect_kb, main_menu_reply_kb,
)
from flaws_data import get_flaw_label

router = Router()

TEXT_FIELDS = {
    "name": "Введи новое имя:",
    "age": "Введи новый возраст (числом, 16-99):",
    "city": "Введи новый город:",
    "bio": "Напиши новое описание о себе:",
}

FIELD_LABELS = {
    "name": "Имя",
    "age": "Возраст",
    "city": "Город",
    "bio": "Описание",
}


@router.callback_query(F.data == "menu:edit")
async def edit_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Что хочешь изменить?", reply_markup=edit_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "edit:back")
async def edit_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Ок, возвращаемся в меню.", reply_markup=main_menu_reply_kb())
    await callback.answer()


# ---------- Текстовые поля: имя / возраст / город / био ----------

@router.callback_query(F.data.in_({f"edit:{f}" for f in TEXT_FIELDS}))
async def edit_text_field_start(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":")[1]
    await state.update_data(edit_field=field)
    await state.set_state(EditProfile.waiting_text)
    # временно прячем постоянную клавиатуру меню, чтобы её случайное нажатие
    # не попало в это текстовое поле как новое значение
    await callback.message.answer(TEXT_FIELDS[field], reply_markup=ReplyKeyboardRemove())
    await callback.answer()


@router.message(EditProfile.waiting_text)
async def edit_text_field_save(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data["edit_field"]
    value = message.text.strip()

    if field == "age":
        if not value.isdigit() or not (16 <= int(value) <= 99):
            await message.answer("Возраст должен быть числом от 16 до 99. Попробуй ещё раз:")
            return
        value = int(value)

    db.upsert_user(message.from_user.id, **{field: value})
    await message.answer(f"{FIELD_LABELS[field]} обновлено(а) ✅", reply_markup=main_menu_reply_kb())
    await state.clear()


# ---------- Пол / кого ищу ----------

@router.callback_query(F.data == "edit:gender")
async def edit_gender_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfile.gender_select)
    await callback.message.answer("Выбери пол:", reply_markup=gender_kb())
    await callback.answer()


@router.callback_query(EditProfile.gender_select, F.data.startswith("gender:"))
async def edit_gender_save(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split(":")[1]
    db.upsert_user(callback.from_user.id, gender=gender)
    await callback.message.edit_text("Пол обновлён ✅")
    await callback.message.answer("Готово!", reply_markup=main_menu_reply_kb())
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "edit:looking_for")
async def edit_looking_for_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfile.looking_for_select)
    await callback.message.answer("Кого хочешь найти?", reply_markup=looking_for_kb())
    await callback.answer()


@router.callback_query(EditProfile.looking_for_select, F.data.startswith("lf:"))
async def edit_looking_for_save(callback: CallbackQuery, state: FSMContext):
    lf = callback.data.split(":")[1]
    db.upsert_user(callback.from_user.id, looking_for=lf)
    await callback.message.edit_text("Предпочтения обновлены ✅")
    await callback.message.answer("Готово!", reply_markup=main_menu_reply_kb())
    await state.clear()
    await callback.answer()


# ---------- Фото ----------

@router.callback_query(F.data == "edit:photo")
async def edit_photo_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfile.waiting_photo)
    await callback.message.answer("Пришли новое фото:", reply_markup=ReplyKeyboardRemove())
    await callback.answer()


@router.message(EditProfile.waiting_photo, F.photo)
async def edit_photo_save(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    db.upsert_user(message.from_user.id, photo_file_id=photo_id)
    await message.answer("Фото обновлено ✅", reply_markup=main_menu_reply_kb())
    await state.clear()


@router.message(EditProfile.waiting_photo)
async def edit_photo_invalid(message: Message):
    await message.answer("Пожалуйста, пришли именно фото.")


# ---------- Недостатки ----------

@router.callback_query(F.data == "edit:flaws")
async def edit_flaws_start(callback: CallbackQuery, state: FSMContext):
    current = set(db.get_user_flaws(callback.from_user.id))
    await state.update_data(selected_flaws=list(current))
    await state.set_state(EditProfile.flaws_select)
    await callback.message.answer(
        "Обнови свои недостатки:", reply_markup=flaws_multiselect_kb(current, mode="flaws")
    )
    await callback.answer()


@router.callback_query(EditProfile.flaws_select, F.data.startswith("flaws:"))
async def edit_flaws_toggle(callback: CallbackQuery, state: FSMContext):
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


@router.callback_query(EditProfile.flaws_select, F.data == "flaws_done")
async def edit_flaws_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_flaws", [])
    if not selected:
        await callback.answer("Выбери хотя бы один недостаток 🙂", show_alert=True)
        return
    db.set_user_flaws(callback.from_user.id, selected)
    flaws_txt = ", ".join(get_flaw_label(f) for f in selected)
    await callback.message.edit_text(f"Недостатки обновлены ✅\n{flaws_txt}")
    await callback.message.answer("Готово!", reply_markup=main_menu_reply_kb())
    await state.clear()
    await callback.answer()


# ---------- Толерантность ----------

@router.callback_query(F.data == "edit:tolerance")
async def edit_tolerance_start(callback: CallbackQuery, state: FSMContext):
    current = set(db.get_user_tolerance(callback.from_user.id))
    await state.update_data(selected_tolerance=list(current))
    await state.set_state(EditProfile.tolerance_select)
    await callback.message.answer(
        "Обнови, что готов(а) терпеть в партнёре:",
        reply_markup=flaws_multiselect_kb(current, mode="tol"),
    )
    await callback.answer()


@router.callback_query(EditProfile.tolerance_select, F.data.startswith("tol:"))
async def edit_tolerance_toggle(callback: CallbackQuery, state: FSMContext):
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


@router.callback_query(EditProfile.tolerance_select, F.data == "tol_done")
async def edit_tolerance_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_tolerance", [])
    if not selected:
        await callback.answer("Выбери хотя бы один пункт 🙂", show_alert=True)
        return
    db.set_user_tolerance(callback.from_user.id, selected)
    tol_txt = ", ".join(get_flaw_label(f) for f in selected)
    await callback.message.edit_text(f"Толерантность обновлена ✅\n{tol_txt}")
    await callback.message.answer("Готово!", reply_markup=main_menu_reply_kb())
    await state.clear()
    await callback.answer()
