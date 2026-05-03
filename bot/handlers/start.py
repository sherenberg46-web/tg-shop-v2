import logging
import os
import re

from aiogram import Router, F

log = logging.getLogger(__name__)
from aiogram.types import (
    Message, CallbackQuery, WebAppInfo,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from bot.states import MainMenu, GameSearch, Consultation

router = Router()

WEBAPP_URL = os.getenv("WEBAPP_URL", "https://sublime-serenity-production-dde7.up.railway.app")

# Resolve DB_PATH the same way the backend does
def _resolve_db_path() -> str:
    try:
        from backend.config import settings
        return str(settings.DB_PATH)
    except Exception:
        path = os.getenv("DB_PATH", "database/shop.db")
        if not os.path.isabs(path):
            path = os.path.join(os.path.dirname(__file__), "..", "..", path)
        return os.path.normpath(path)

DB_PATH = _resolve_db_path()

# Тексты кнопок нижней клавиатуры
BTN_SHOP    = "🛒 Открыть магазин"
BTN_GAMES   = "🎮 Купить игру"
BTN_SUBS    = "🎯 Подписки"
BTN_TOPUP   = "💰 Пополнить"
BTN_AI      = "🤖 AI Консультант"


# ── Keyboards ─────────────────────────────────────────────────────────────────

def reply_keyboard() -> ReplyKeyboardMarkup:
    """Нижняя постоянная клавиатура."""
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_SHOP,  web_app=WebAppInfo(url=WEBAPP_URL))
    builder.button(text=BTN_AI)
    builder.button(text=BTN_GAMES)
    builder.button(text=BTN_SUBS)
    builder.button(text=BTN_TOPUP)
    builder.adjust(2, 3)
    return builder.as_markup(resize_keyboard=True)


def main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🎮 Хочу купить игру",    callback_data="want_game")
    builder.button(text="🎯 Хочу подписку",        callback_data="want_subscription")
    builder.button(text="💰 Пополнить кошелёк",    callback_data="want_topup")
    builder.button(text="🤖 Консультация с AI",    callback_data="want_consultation")
    builder.adjust(2, 2)
    return builder.as_markup()


def parse_product_buttons(text: str) -> InlineKeyboardBuilder:
    """Парсит [ТОВАР:ID:название] теги и создаёт кнопки с web_app."""
    builder = InlineKeyboardBuilder()
    for product_id, product_name in re.findall(r'\[ТОВАР:(\d+):([^\]]+)\]', text):
        url = f"{WEBAPP_URL}/product/{product_id}"
        builder.button(text=f"🛒 {product_name[:30]}", web_app=WebAppInfo(url=url))
    return builder


def clean_product_tags(text: str) -> str:
    """Убирает [ТОВАР:...] теги из текста."""
    return re.sub(r'\[ТОВАР:\d+:[^\]]+\]', '', text).strip()


async def send_ai_response(
    edit_target,        # message to edit_text on
    reply_target,       # message to answer on (for new messages)
    user_message: str,
    history: list,
    region: str,
    extra_buttons: list[tuple] | None = None,
    use_edit: bool = True,
):
    """Вызвать AI и показать результат. Возвращает обновлённую историю."""
    from bot.ai_consultant import ask_consultant

    try:
        response, updated_history = await ask_consultant(user_message, history, region, DB_PATH)
    except Exception as e:
        err = f"⚠️ Ошибка AI консультанта: {e}\n\nПопробуйте позже или напишите @Sherenberg"
        if use_edit:
            await edit_target.edit_text(err)
        else:
            await reply_target.answer(err)
        return history  # вернуть старую историю без изменений

    keyboard = parse_product_buttons(response)
    if extra_buttons:
        for btn_text, cb in extra_buttons:
            keyboard.button(text=btn_text, callback_data=cb)
    keyboard.button(text="🏠 Главное меню", callback_data="back_to_menu")
    keyboard.adjust(1)

    clean_text = clean_product_tags(response)
    markup = keyboard.as_markup()

    try:
        if use_edit:
            await edit_target.edit_text(clean_text, reply_markup=markup)
        else:
            await reply_target.answer(clean_text, reply_markup=markup)
    except Exception:
        # Если текст слишком длинный или содержит спецсимволы — отправить без форматирования
        if use_edit:
            await edit_target.edit_text(clean_text[:4096], reply_markup=markup)
        else:
            await reply_target.answer(clean_text[:4096], reply_markup=markup)

    return updated_history


# ── /start ────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_name = message.from_user.first_name or "друг"
    # Сначала показываем нижнюю клавиатуру
    await message.answer(
        f"👋 Привет, {user_name}! Добро пожаловать в *GAME STORE* 🎮",
        parse_mode="Markdown",
        reply_markup=reply_keyboard(),
    )
    # Затем inline-меню с разделами
    await message.answer(
        "Здесь вы найдёте игры и подписки PlayStation "
        "по выгодным ценам из регионов 🇺🇦 UA и 🇹🇷 TR.\n\n"
        "*Что вас интересует?*",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
    await state.set_state(MainMenu.waiting_choice)


# ── Обработчики кнопок нижней клавиатуры ─────────────────────────────────────

@router.message(F.text == BTN_GAMES)
async def btn_games(message: Message, state: FSMContext):
    await state.clear()
    builder = InlineKeyboardBuilder()
    genres = [
        "⚔️ Экшн", "🧙 RPG", "⚽ Спорт", "🏎️ Гонки",
        "😱 Хоррор", "🔫 Шутер", "🧩 Головоломки", "👨‍👩‍👧 Семейные", "🎲 Другой",
    ]
    for genre in genres:
        builder.button(text=genre, callback_data=f"genre_{genre}")
    builder.adjust(3, 3, 3)
    await message.answer(
        "🎮 *Выбор игры*\n\nКакой жанр вас интересует?",
        parse_mode="Markdown",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(GameSearch.waiting_genre)


@router.message(F.text == BTN_SUBS)
async def btn_subs(message: Message, state: FSMContext):
    await state.clear()
    builder = InlineKeyboardBuilder()
    builder.button(text="🎮 PS Plus Essential", callback_data="sub_essential")
    builder.button(text="🎮 PS Plus Extra",     callback_data="sub_extra")
    builder.button(text="🎮 PS Plus Deluxe",    callback_data="sub_deluxe")
    builder.button(text="🎯 EA Play",           callback_data="sub_ea")
    builder.button(text="❓ Помогите выбрать",  callback_data="sub_help")
    builder.adjust(1)
    await message.answer(
        "🎯 *Подписки PlayStation*\n\nКакая подписка вас интересует?",
        parse_mode="Markdown",
        reply_markup=builder.as_markup(),
    )


@router.message(F.text == BTN_TOPUP)
async def btn_topup(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🇺🇦 Пополнить кошелёк UA",
        web_app=WebAppInfo(url=f"{WEBAPP_URL}?section=topup&region=UA"),
    )
    builder.button(
        text="🇹🇷 Пополнить кошелёк TR",
        web_app=WebAppInfo(url=f"{WEBAPP_URL}?section=topup&region=TR"),
    )
    builder.adjust(1)
    await message.answer(
        "💰 *Пополнение кошелька PlayStation*\n\nВыберите регион:",
        parse_mode="Markdown",
        reply_markup=builder.as_markup(),
    )


@router.message(F.text == BTN_AI)
async def btn_ai(message: Message, state: FSMContext):
    await state.set_state(Consultation.chatting)
    await state.update_data(history=[])
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Завершить консультацию", callback_data="back_to_menu")
    await message.answer(
        "🤖 AI Консультант GAME STORE\n\n"
        "Задайте любой вопрос, например:\n"
        "• «Какие игры есть для двоих?»\n"
        "• «Что купить на 100 BYN?»\n"
        "• «Посоветуй RPG как Elden Ring»\n"
        "• «Стоит ли брать PS Plus?»",
        reply_markup=builder.as_markup(),
    )


# ── Назад в меню ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🎮 *GAME STORE*\n\nЧто вас интересует?",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


# ── Хочу игру ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "want_game")
async def want_game(callback: CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    genres = [
        "⚔️ Экшн", "🧙 RPG", "⚽ Спорт", "🏎️ Гонки",
        "😱 Хоррор", "🔫 Шутер", "🧩 Головоломки", "👨‍👩‍👧 Семейные", "🎲 Другой",
    ]
    for genre in genres:
        builder.button(text=genre, callback_data=f"genre_{genre}")
    builder.button(text="◀️ Назад", callback_data="back_to_menu")
    builder.adjust(3, 3, 3, 1)

    await callback.message.edit_text(
        "🎮 *Выбор игры*\n\nКакой жанр вас интересует?",
        parse_mode="Markdown",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(GameSearch.waiting_genre)


@router.callback_query(GameSearch.waiting_genre, F.data.startswith("genre_"))
async def choose_genre(callback: CallbackQuery, state: FSMContext):
    genre = callback.data.removeprefix("genre_")
    await state.update_data(genre=genre)

    builder = InlineKeyboardBuilder()
    builder.button(text="🎮 PS5",       callback_data="platform_PS5")
    builder.button(text="🎮 PS4",       callback_data="platform_PS4")
    builder.button(text="🎮 PS4 & PS5", callback_data="platform_both")
    builder.button(text="◀️ Назад",     callback_data="want_game")
    builder.adjust(3, 1)

    await callback.message.edit_text(
        f"🎮 Жанр: *{genre}*\n\nДля какой платформы?",
        parse_mode="Markdown",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(GameSearch.waiting_platform)


@router.callback_query(GameSearch.waiting_platform, F.data.startswith("platform_"))
async def choose_platform(callback: CallbackQuery, state: FSMContext):
    platform = callback.data.removeprefix("platform_")
    await state.update_data(platform=platform)

    builder = InlineKeyboardBuilder()
    builder.button(text="💵 До 50 BYN",         callback_data="budget_50")
    builder.button(text="💵 До 100 BYN",        callback_data="budget_100")
    builder.button(text="💵 До 200 BYN",        callback_data="budget_200")
    builder.button(text="💵 Без ограничений",   callback_data="budget_any")
    builder.button(text="◀️ Назад",             callback_data="want_game")
    builder.adjust(2, 2, 1)

    data = await state.get_data()
    await callback.message.edit_text(
        f"🎮 Жанр: *{data['genre']}* | Платформа: *{platform}*\n\nКакой бюджет?",
        parse_mode="Markdown",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(GameSearch.waiting_budget)


@router.callback_query(GameSearch.waiting_budget, F.data.startswith("budget_"))
async def choose_budget(callback: CallbackQuery, state: FSMContext):
    budget = callback.data.removeprefix("budget_")
    data = await state.get_data()

    await callback.message.edit_text("🔍 Ищу подходящие игры...")

    query = f"Ищу игру жанра {data['genre']} для {data['platform']}"
    if budget != "any":
        query += f" с бюджетом до {budget} BYN"

    history = await send_ai_response(
        edit_target=callback.message,
        reply_target=None,
        user_message=query,
        history=[],
        region="UA",
        extra_buttons=[("🤖 Задать вопрос AI", "continue_consultation")],
    )
    await state.update_data(history=history)
    await state.set_state(Consultation.chatting)


# ── Хочу подписку ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "want_subscription")
async def want_subscription(callback: CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="🎮 PS Plus Essential",       callback_data="sub_essential")
    builder.button(text="🎮 PS Plus Extra",           callback_data="sub_extra")
    builder.button(text="🎮 PS Plus Deluxe",          callback_data="sub_deluxe")
    builder.button(text="🎯 EA Play",                 callback_data="sub_ea")
    builder.button(text="❓ Помогите выбрать",        callback_data="sub_help")
    builder.button(text="◀️ Назад",                   callback_data="back_to_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        "🎯 *Подписки PlayStation*\n\nКакая подписка вас интересует?",
        parse_mode="Markdown",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.in_({"sub_essential", "sub_extra", "sub_deluxe", "sub_ea"}))
async def open_subscription(callback: CallbackQuery):
    section_map = {
        "sub_essential": "subscriptions",
        "sub_extra":     "subscriptions",
        "sub_deluxe":    "subscriptions",
        "sub_ea":        "subscriptions",
    }
    section = section_map[callback.data]
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🛒 Открыть в магазине",
        web_app=WebAppInfo(url=f"{WEBAPP_URL}?section={section}"),
    )
    builder.button(text="◀️ Назад", callback_data="want_subscription")
    builder.adjust(1)
    await callback.message.edit_text(
        "🎯 Открываю раздел подписок в магазине:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "sub_help")
async def sub_help(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🤖 Сейчас объясню разницу...")

    history = await send_ai_response(
        edit_target=callback.message,
        reply_target=None,
        user_message=(
            "Объясни разницу между PS Plus Essential, Extra и Deluxe. "
            "Какую лучше выбрать для обычного игрока?"
        ),
        history=[],
        region="UA",
        extra_buttons=[("🤖 Ещё вопрос", "continue_consultation")],
    )
    await state.update_data(history=history)
    await state.set_state(Consultation.chatting)


# ── Пополнение кошелька ───────────────────────────────────────────────────────

@router.callback_query(F.data == "want_topup")
async def want_topup(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🇺🇦 Пополнить кошелёк UA",
        web_app=WebAppInfo(url=f"{WEBAPP_URL}?section=topup&region=UA"),
    )
    builder.button(
        text="🇹🇷 Пополнить кошелёк TR",
        web_app=WebAppInfo(url=f"{WEBAPP_URL}?section=topup&region=TR"),
    )
    builder.button(text="◀️ Назад", callback_data="back_to_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        "💰 *Пополнение кошелька PlayStation*\n\nВыберите регион для пополнения:",
        parse_mode="Markdown",
        reply_markup=builder.as_markup(),
    )


# ── AI Консультация ───────────────────────────────────────────────────────────

@router.callback_query(F.data.in_({"want_consultation", "continue_consultation"}))
async def want_consultation(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Consultation.chatting)

    # Сохраняем историю только если начинаем новую консультацию
    data = await state.get_data()
    if callback.data == "want_consultation" or not data.get("history"):
        await state.update_data(history=[])

    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Завершить консультацию", callback_data="back_to_menu")

    await callback.message.edit_text(
        "🤖 AI Консультант GAME STORE\n\n"
        "Я помогу подобрать игру или подписку именно для вас!\n\n"
        "Задайте любой вопрос, например:\n"
        "• «Какие игры есть для двоих?»\n"
        "• «Что купить на 100 BYN?»\n"
        "• «Посоветуй RPG как Elden Ring»\n"
        "• «Стоит ли брать PS Plus?»",
        reply_markup=builder.as_markup(),
    )


@router.message(Consultation.chatting)
async def consultation_message(message: Message, state: FSMContext):
    from bot.ai_consultant import ask_consultant

    text = message.text or ""

    # Нажатие кнопок нижней клавиатуры — пропускаем, их ловят хэндлеры выше
    if text in (BTN_SHOP, BTN_AI, BTN_GAMES, BTN_SUBS, BTN_TOPUP):
        return
    if not text.strip():
        await message.answer("Напишите ваш вопрос текстом 😊")
        return

    data = await state.get_data()
    history = data.get("history", [])

    await message.bot.send_chat_action(message.chat.id, "typing")

    # ask_consultant никогда не поднимает исключений — возвращает текст ошибки
    response, updated_history = await ask_consultant(text, history, "UA", DB_PATH)
    await state.update_data(history=updated_history)

    # Собираем кнопки из тегов [ТОВАР:ID:название]
    keyboard = parse_product_buttons(response)
    keyboard.button(text="🏠 Завершить консультацию", callback_data="back_to_menu")
    keyboard.adjust(1)

    clean_text = clean_product_tags(response).strip() or response

    try:
        await message.answer(clean_text, reply_markup=keyboard.as_markup())
    except Exception as e:
        log.error("Failed to send AI response: %s", e)
        await message.answer(
            "❌ Не удалось отправить ответ. Напишите менеджеру @Sherenberg"
        )
