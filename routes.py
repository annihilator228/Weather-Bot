import aiohttp
import aiosqlite
from os import getenv
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery)

DB_NAME = "cities.db"
API_KEY = getenv('API_KEY')
router=Router()

url = "http://api.openweathermap.org/data/2.5/weather"

class WeatherForm(StatesGroup):
    city = State()

#----


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS cities(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            city TEXT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, city))""")
        await db.commit()


async def get_cities(user_id: int) -> list[str]:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT city FROM cities
            WHERE user_id = ?
            ORDER BY added_at DESC
            LIMIT 5
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def add_city(user_id: int, city: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO cities (user_id, city) VALUES (?, ?)
            ON CONFLICT(user_id, city) DO UPDATE SET added_at = CURRENT_TIMESTAMP
        """, (user_id, city))

        await db.execute("""
            DELETE FROM cities
            WHERE user_id = ? AND id NOT IN (
                SELECT id FROM cities
                WHERE user_id = ?
                ORDER BY added_at DESC
                LIMIT 5
            )
        """, (user_id, user_id))

        await db.commit()


#----


async def send_weather(message: Message, city):
    params = {
        "q": city,
        "appid": API_KEY,
        "units": "metric",
        "lang": "ru"}
    async with (aiohttp.ClientSession() as session):
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                await message.answer(f"В городе {data['name']} {data['weather'][0]['description']}\n"
                        f"Температура: {data['main']['temp']}°C\n"
                        f"Ощущается как: {data['main']['temp']}°C\n"
                        f"Влажность: {data['main']['humidity']}%\n")
            else:
                await message.answer(f"Ошибка {response.status}: {(await response.json()).get('message', '')}")


@router.message(Command('start'))
@router.message(F.text.lower().in_(["старт🚀", "старт"]))
async def start(message: Message):
    await message.answer("Привет!👋\n"
                         "Я бот для прогноза погоды⛅\n\n"
                         "/help - Помощь🆘")


@router.message(Command('help'))
@router.message(F.text.lower().in_(["помощь🆘", "помощь"]))
async def cmd_help(message: Message):
    keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Старт🚀"), KeyboardButton(text="Помощь🆘")],
    [KeyboardButton(text="Погода⛅")]], resize_keyboard=True)
    await message.answer("Команды:\n\n"
                         "/start - Запустить бота🚀\n"
                         "/help - Помощь🆘\n"
                         "/weather - Узнать погоду⛅",
                         reply_markup=keyboard)


@router.message(Command('weather'))
@router.message(F.text.lower().in_(["погода⛅", "погода"]))
async def cmd_weather(message: Message, state: FSMContext):
    names= await get_cities(message.from_user.id)
    inline_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"city:{name}"),]
            for name in names])

    await state.set_state(WeatherForm.city)
    await message.answer("Введите город: \n"
                         "Недавние поиски:🔍",
                         reply_markup=inline_keyboard)


@router.message(WeatherForm.city)
async def city(message: Message, state: FSMContext):
    city = message.text.strip()
    await add_city(message.from_user.id, city)
    await state.clear()
    await send_weather(message, city)


@router.callback_query(WeatherForm.city)
async def button(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    await callback.answer()
    if data.startswith("city:"):
        city = data.split(':', 1)[1]
        await state.clear()
        await send_weather(city)