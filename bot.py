import asyncio
import json
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

BOT_TOKEN = "8249754947:AAG0SkjxBGz8xqPYmHVR9BFG6NHpRMtYb4Q"  

CATEGORIES = {
    "Шпагат": 21,
    "Осанка": 22,
    "Ягодицы": 12,
    "Тазовое дно": 10,
    "Молодость лица": 5,
}

BTN_BACK = "⬅️ Назад в меню"
BTN_BIND = "🎥 Привязать видео"
BTN_CANCEL_BIND = "❌ Отмена привязки"

VIDEOS_FILE = "videos.json"


def load_videos() -> dict:
    if not os.path.exists(VIDEOS_FILE):
        return {}
    try:
        with open(VIDEOS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_videos(data: dict) -> None:
    with open(VIDEOS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


VIDEOS = load_videos()

dp = Dispatcher()

# user_id -> state
# {
#   "category": str|None,
#   "bind_mode": bool,
#   "pending_number": int|None
# }
user_state = {}


def kb_categories() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    for title in CATEGORIES.keys():
        kb.add(KeyboardButton(text=title))
    kb.adjust(2)
    kb.row(KeyboardButton(text=BTN_BIND))
    return kb.as_markup(resize_keyboard=True)


def kb_numbers(total: int) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    for i in range(1, total + 1):
        kb.add(KeyboardButton(text=str(i)))
    kb.adjust(6)
    kb.row(KeyboardButton(text=BTN_BACK))
    return kb.as_markup(resize_keyboard=True)


def kb_cancel_bind() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text=BTN_CANCEL_BIND))
    kb.row(KeyboardButton(text=BTN_BACK))
    return kb.as_markup(resize_keyboard=True)


@dp.message(CommandStart())
async def start(message: Message):
    user_state[message.from_user.id] = {
        "category": None,
        "bind_mode": False,
        "pending_number": None,
    }
    await message.answer("Выбери категорию 👇", reply_markup=kb_categories())


@dp.message(F.text == BTN_BACK)
async def back_to_menu(message: Message):
    st = user_state.setdefault(message.from_user.id, {})
    st["category"] = None
    st["pending_number"] = None
    st["bind_mode"] = False
    await message.answer("Выбери категорию 👇", reply_markup=kb_categories())


@dp.message(F.text == BTN_BIND)
async def enable_bind_mode(message: Message):
    st = user_state.setdefault(message.from_user.id, {})
    st["bind_mode"] = True
    st["category"] = None
    st["pending_number"] = None
    await message.answer(
        "🎥 Режим привязки видео включён.\n"
        "Сначала выбери категорию, потом номер тренировки — и я попрошу видео.",
        reply_markup=kb_categories()
    )


@dp.message(F.text == BTN_CANCEL_BIND)
async def cancel_bind_mode(message: Message):
    st = user_state.setdefault(message.from_user.id, {})
    st["bind_mode"] = False
    st["pending_number"] = None
    await message.answer("Ок, режим привязки выключен ✅", reply_markup=kb_categories())


@dp.message(F.text.in_(CATEGORIES.keys()))
async def category_selected(message: Message):
    cat = message.text
    st = user_state.setdefault(message.from_user.id, {
        "category": None, "bind_mode": False, "pending_number": None
    })
    st["category"] = cat
    st["pending_number"] = None

    total = CATEGORIES[cat]
    await message.answer(
        f"{cat}\nВыбери номер тренировки (всего {total}) 👇",
        reply_markup=kb_numbers(total),
    )


@dp.message(F.video)
async def receive_video(message: Message):
    uid = message.from_user.id
    st = user_state.get(uid)

    if not st or not st.get("bind_mode") or not st.get("category") or not st.get("pending_number"):
        await message.answer(
            "Чтобы привязать видео:\n"
            "1) Нажми «🎥 Привязать видео»\n"
            "2) Выбери категорию\n"
            "3) Выбери номер\n"
            "4) Пришли видео",
            reply_markup=kb_categories(),
        )
        return

    cat = st["category"]
    num = st["pending_number"]
    file_id = message.video.file_id

    # сохраняем: VIDEOS[cat][num] = file_id
    VIDEOS.setdefault(cat, {})
    VIDEOS[cat][str(num)] = file_id
    save_videos(VIDEOS)

    st["pending_number"] = None

    await message.answer(
        f"✅ Видео привязано!\n{cat} — тренировка №{num}",
        reply_markup=kb_numbers(CATEGORIES[cat]),
    )


@dp.message()
async def handle_text(message: Message):
    uid = message.from_user.id
    st = user_state.setdefault(uid, {"category": None, "bind_mode": False, "pending_number": None})
    text = (message.text or "").strip()

    # если категория не выбрана
    if not st.get("category"):
        await message.answer("Выбери категорию 👇", reply_markup=kb_categories())
        return

    cat = st["category"]
    total = CATEGORIES[cat]

    # ожидаем номер
    if not text.isdigit():
        await message.answer(f"Нажми номер тренировки (1–{total}) кнопкой 👇", reply_markup=kb_numbers(total))
        return

    num = int(text)
    if not (1 <= num <= total):
        await message.answer(f"Номер должен быть 1–{total}", reply_markup=kb_numbers(total))
        return

    # если режим привязки — просим видео
    if st.get("bind_mode"):
        st["pending_number"] = num
        await message.answer(
            f"🎥 Пришли ВИДЕО для:\n{cat} — тренировка №{num}\n\n"
            f"Если передумал — нажми «{BTN_CANCEL_BIND}».",
            reply_markup=kb_cancel_bind()
        )
        return

    # обычный режим — отправляем видео, если есть
    file_id = VIDEOS.get(cat, {}).get(str(num))
    if file_id:
        await message.answer_video(file_id, caption=f"{cat} — тренировка №{num}")
    else:
        await message.answer(
            f"Для {cat} №{num} видео ещё не добавлено.\n"
            f"Нажми «🎥 Привязать видео», чтобы добавить.",
            reply_markup=kb_numbers(total),
        )


async def main():
    bot = Bot(BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())