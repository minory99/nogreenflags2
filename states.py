from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    name = State()
    age = State()
    gender = State()
    looking_for = State()
    city = State()
    bio = State()
    photo = State()
    flaws_select = State()
    flaws_custom = State()
    tolerance_select = State()
    tolerance_custom = State()


class EditProfile(StatesGroup):
    waiting_text = State()
    waiting_photo = State()
    gender_select = State()
    looking_for_select = State()
    flaws_select = State()
    tolerance_select = State()


class Chatting(StatesGroup):
    active = State()


class Report(StatesGroup):
    waiting_reason = State()
