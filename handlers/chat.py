from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

import db
from states import Chatting
from keyboards import chat_reply_kb, contact_link_kb, main_menu_reply_kb, CONTACT_BTN_TEXT, END_CHAT_BTN_TEXT

router = Router()


def _partner_state(current_state: FSMContext, bot_id: int, partner_id: int) -> FSMContext:
    key = StorageKey(bot_id=bot_id, chat_id=partner_id, user_id=partner_id)
    return FSMContext(storage=current_state.storage, key=key)


@router.callback_query(F.data.startswith("chat_start:"))
async def chat_start(callback: CallbackQuery, state: FSMContext):
    partner_id = int(callback.data.split(":")[1])
    partner = db.get_user(partner_id)
    if not partner:
        await callback.answer("Собеседник недоступен.", show_alert=True)
        return

    await state.update_data(chat_partner=partner_id)
    await state.set_state(Chatting.active)
    await callback.message.answer(
        f"💬 Открыт чат с {partner['name']} — переписка идёт прямо здесь, в боте.\n"
        f"Просто пиши сообщения, я их передам. Пока поддерживается только текст.",
        reply_markup=chat_reply_kb(),
    )
    await callback.answer()


@router.message(Chatting.active, F.text == CONTACT_BTN_TEXT)
async def share_contact(message: Message, state: FSMContext):
    data = await state.get_data()
    partner_id = data.get("chat_partner")
    if not partner_id:
        await message.answer("Чат не найден.")
        return

    me = db.get_user(message.from_user.id)
    if not me or not me["username"]:
        await message.answer(
            "У тебя не задан username в Telegram. Задай его в Настройки → Имя пользователя "
            "и попробуй снова."
        )
        return

    try:
        await message.bot.send_message(
            partner_id,
            f"📇 {me['name']} поделился(ась) с тобой контактом!",
            reply_markup=contact_link_kb(me["name"], me["username"]),
        )
        await message.answer("Контакт отправлен ✅")
    except Exception:
        await message.answer("Не получилось отправить — собеседник недоступен.")


@router.message(Chatting.active, F.text == END_CHAT_BTN_TEXT)
async def end_chat(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Чат завершён. Переписку можно возобновить со страницы мэтча.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer("Что дальше?", reply_markup=main_menu_reply_kb())


@router.message(Chatting.active)
async def relay_message(message: Message, state: FSMContext):
    data = await state.get_data()
    partner_id = data.get("chat_partner")
    if not partner_id:
        await state.clear()
        await message.answer("Чат не найден. Открой его заново со страницы мэтча.",
                              reply_markup=ReplyKeyboardRemove())
        return

    if not message.text:
        await message.answer("Пока можно передавать только текстовые сообщения 🙂")
        return

    me = db.get_user(message.from_user.id)
    sender_name = me["name"] if me else "Собеседник"

    try:
        await message.bot.send_message(partner_id, f"💬 {sender_name}: {message.text}")
    except Exception:
        await message.answer("Не получилось доставить сообщение — возможно, собеседник заблокировал бота.")
        return

    partner_ctx = _partner_state(state, message.bot.id, partner_id)
    partner_data = await partner_ctx.get_data()
    if partner_data.get("chat_partner") != message.from_user.id:
        await partner_ctx.update_data(chat_partner=message.from_user.id)
        await partner_ctx.set_state(Chatting.active)
        await message.bot.send_message(
            partner_id,
            "👆 Это переписка внутри бота — просто отвечай сюда, я передам.",
            reply_markup=chat_reply_kb(),
        )
