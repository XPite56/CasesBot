import asyncio
import logging
import random
import time
from pathlib import Path
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton

# --- КОНФИГУРАЦИЯ ---
# Замени на свой токен от @BotFather
BOT_TOKEN = '8439766241:AAE29-i50ck72HKexlbMFJkpqCWgGN55AKc'

# Имя файла базы данных (создастся сама)
DB_NAME = 'bot_database.db'

# Имя файла с твоим спрайтом (должен лежать рядом со скриптом)
CASE_IMAGE_FILE = "image_3.png"

# Настройка логирования (чтобы видеть ошибки в консоли)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- МАТЕМАТИКА КЕЙСА ---
# Возможные награды (виртуальные звезды)
REWARDS = [1, 2, 3, 5, 10, 15, 25]
# Веса (шансы). Чем больше число, тем выше шанс.
# Сумма весов = 100. Примерно: 50% на 1 звезду, 0.2% на 25 звезд.
WEIGHTS = [50, 25, 15, 6, 3, 0.8, 0.2]

def calculate_spin_reward():
    """Выбирает случайный приз на основе весов."""
    return random.choices(REWARDS, weights=WEIGHTS, k=1)[0]

# --- БАЗА ДАННЫХ (SQLite + aiosqlite) ---

async def init_db():
    """Создает таблицу пользователей, если её нет."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                last_free_spin INTEGER DEFAULT 0
            )
        ''')
        await db.commit()

async def get_user_data(user_id: int):
    """Получает данные юзера или создает нового, если его нет."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT balance, last_free_spin FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"balance": row[0], "last_free_spin": row[1]}
            else:
                # Регистрируем нового пользователя
                await db.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
                await db.commit()
                return {"balance": 0, "last_free_spin": 0}

async def update_after_spin(user_id: int, win_amount: int, current_time: int):
    """Обновляет баланс и время последнего спина."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            UPDATE users 
            SET balance = balance + ?, last_free_spin = ? 
            WHERE user_id = ?
        ''', (win_amount, current_time, user_id))
        await db.commit()

# --- КЛАВИАТУРЫ ---
def main_keyboard():
    kb = [
        [KeyboardButton(text="🎁 Бесплатный кейс")],
        [KeyboardButton(text="👤 Мой профиль")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- ХЕНДЛЕРЫ (ОБРАБОТЧИКИ КОМАНД) ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """Приветствие при команде /start"""
    # Регистрируем пользователя в БД при старте
    await get_user_data(message.from_user.id)
    await message.answer(
        "Привет! Я бот с кейсами Telegram Stars.\n"
        "Ты можешь открывать бесплатный кейс каждые 24 часа и копить звезды!",
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "👤 Мой профиль")
async def profile_handler(message: types.Message):
    """Показывает баланс пользователя."""
    user_data = await get_user_data(message.from_user.id)
    balance = user_data['balance']
    await message.answer(f"👤 **Твой профиль**\n\n💰 Баланс: {balance} виртуальных ⭐️")

@dp.message(F.text == "🎁 Бесплатный кейс")
async def free_case_handler(message: types.Message):
    """Основная логика открытия кейса."""
    user_id = message.from_user.id
    user_data = await get_user_data(user_id)
    
    last_spin_time = user_data['last_free_spin']
    current_time = int(time.time()) # Текущее время в секундах (Unix timestamp)
    cooldown_seconds = 24 * 60 * 60 # 24 часа в секундах
    
    time_passed = current_time - last_spin_time
    
    if time_passed < cooldown_seconds:
        # Если 24 часа еще не прошло
        wait_seconds = cooldown_seconds - time_passed
        hours = wait_seconds // 3600
        minutes = (wait_seconds % 3600) // 60
        await message.answer(
            f"⏳ Кейс еще не готов!\n"
            f"Приходи через: {hours} ч. {minutes} мин."
        )
    else:
        # Можно крутить!
        
        # 1. Вычисляем выигрыш
        win_amount = calculate_spin_reward()
        
        # 2. Обновляем базу данных
        await update_after_spin(user_id, win_amount, current_time)
        
        # 3. Подготавливаем изображение для отправки
        image_path = Path(CASE_IMAGE_FILE)
        if not image_path.exists():
             await message.answer("Ошибка: Изображение кейса не найдено.")
             return
        
        photo = FSInputFile(image_path)
        
        # 4. Отправляем фото с результатом
        caption = (
            f"🎁 **Кейс открыт!**\n\n"
            f"Поздравляю! Тебе выпало: **{win_amount} ⭐️**\n"
            f"Они добавлены на твой виртуальный баланс."
        )
        await bot.send_photo(chat_id=message.chat.id, photo=photo, caption=caption, parse_mode="Markdown")

# --- ЗАПУСК БОТА ---
async def main():
    # Инициализируем БД перед стартом
    await init_db()
    logger.info("База данных инициализирована. Бот запускается...")
    # Запускаем поллинг (прослушивание сообщений)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
