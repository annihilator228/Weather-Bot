from os import getenv
import asyncio
from aiogram import Bot, Dispatcher
from routes import router, init_db

Token = getenv("BOT_TOKEN")

dp = Dispatcher()
dp.include_router(router)

async def main():
    await init_db()
    bot = Bot(token=Token)
    print("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())