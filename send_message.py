import asyncio
from telegram import Bot

TOKEN = '7763554734:AAGDA226E22vMeqpCTh7w6HlSLGct8W3pyY'
CHAT_ID = 2032323036  # твой chat_id

async def main():
    try:
        print("Создаём бота...")
        bot = Bot(token=TOKEN)
        print("Пробуем отправить сообщение...")
        await bot.send_message(chat_id=CHAT_ID, text="Привет! Это бот. Всё работает :)")
        print("Сообщение отправлено!")
    except Exception as e:
        print("Произошла ошибка:", e)

if __name__ == '__main__':
    asyncio.run(main())