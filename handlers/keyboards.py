from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from flaws_data import flaws_by_category, FLAWS_CATALOG

# Текст кнопок чата (Reply-клавиатура во время переписки внутри бота)
CONTACT_BTN_TEXT = "📇 Дать свой контакт"
END_CHAT_BTN_TEXT = "⏹ Завершить чат"

# Текст кнопок главного меню (Reply-клавиатура основной навигации)
BROWSE_BTN_TEXT = "🔍 Смотреть анкеты"
MATCHES_BTN_TEXT = "💞 Мои мэтчи"
PROFILE_BTN_TEXT = "👤 Моя анкета"


def gender_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Мужской", callback_data="gender:M")
    b.button(text="Женский", callback_data="gender:F")
    b.button(text="Другое", callback_data="gender:other")
    b.adjust(3)
    return b.as_markup()


def looking_for_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Мужчин", callback_data="lf:M")
    b.button(text="Женщин", callback_data="lf:F")
    b.button(text="Всех", callback_data="lf:any")
    b.adjust(3)
    return b.as_markup()


def skip_kb(callback_data: str = "skip") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Пропустить ➡️", callback_data=callback_data)
    return b.as_markup()


def flaws_multiselect_kb(selected: set[str], mode: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    by_cat = flaws_by_category()
    for cat, items in by_cat.items():
        for fid, emoji, name in items:
            mark = "✅ " if fid in selected else ""
            b.button(text=f"{mark}{emoji} {name}", callback_data=f"{mode}:{fid}")
    b.adjust(1)
    b.row(InlineKeyboardButton(text=f"Готово ({len(selected)}) ✔️", callback_data=f"{mode}_done"))
    return b.as_markup()


def browse_kb(target_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="👎 Пропустить", callback_data=f"pass:{target_id}")
    b.button(text="❤️ Нравится", callback_data=f"like:{target_id}")
    b.adjust(2)
    return b.as_markup()


def main_menu_reply_kb() -> ReplyKeyboardMarkup:
    """Постоянная клавиатура внизу экрана — основная навигация по боту."""
    b = ReplyKeyboardBuilder()
    b.button(text=BROWSE_BTN_TEXT)
    b.button(text=MATCHES_BTN_TEXT)
    b.button(text=PROFILE_BTN_TEXT)
    b.adjust(1)
    return b.as_markup(resize_keyboard=True)


def profile_view_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Редактировать анкету", callback_data="menu:edit")
    b.adjust(1)
    return b.as_markup()


def edit_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Имя", callback_data="edit:name")
    b.button(text="Возраст", callback_data="edit:age")
    b.button(text="Пол", callback_data="edit:gender")
    b.button(text="Кого ищу", callback_data="edit:looking_for")
    b.button(text="Город", callback_data="edit:city")
    b.button(text="О себе", callback_data="edit:bio")
    b.button(text="Фото", callback_data="edit:photo")
    b.button(text="Мои недостатки", callback_data="edit:flaws")
    b.button(text="Что готов(а) терпеть", callback_data="edit:tolerance")
    b.button(text="⬅️ Назад", callback_data="edit:back")
    b.adjust(2, 2, 2, 1, 1, 1)
    return b.as_markup()


def match_actions_kb(other_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✍️ Написать", callback_data=f"chat_start:{other_id}")
    b.button(text="🔍 Смотреть анкеты дальше", callback_data="menu:browse")
    b.button(text="💔 Разматчить", callback_data=f"unmatch:{other_id}")
    b.button(text="🚩 Пожаловаться", callback_data=f"report:{other_id}")
    b.adjust(1, 1, 2)
    return b.as_markup()


def unmatch_confirm_kb(other_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Да, разматчить", callback_data=f"unmatch_yes:{other_id}")
    b.button(text="Отмена", callback_data="unmatch_no")
    b.adjust(2)
    return b.as_markup()


def chat_reply_kb() -> ReplyKeyboardMarkup:
    """Постоянная клавиатура снизу экрана, показывается пока идёт переписка внутри бота."""
    b = ReplyKeyboardBuilder()
    b.button(text=CONTACT_BTN_TEXT)
    b.button(text=END_CHAT_BTN_TEXT)
    b.adjust(1)
    return b.as_markup(resize_keyboard=True)


def contact_link_kb(name: str, username: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"Открыть профиль {name}", url=f"https://t.me/{username}")
    return b.as_markup()
