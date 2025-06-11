import asyncio
from telegram import Bot

TOKEN = '7763554734:AAGDA226E22vMeqpCTh7w6HlSLGct8W3pyY'

async def main():
    bot = Bot(token=TOKEN)
    updates = await bot.get_updates()
    for u in updates:
        print(u.message.chat.id, u.message.chat.username, u.message.text)

if __name__ == '__main__':
    asyncio.run(main())