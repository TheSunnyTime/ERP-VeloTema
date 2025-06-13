import sqlite3
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
import os
REGISTERED_CHAT_FILE = "registered_chat_id.txt"

TOKEN = "7763554734:AAGDA226E22vMeqpCTh7w6HlSLGct8W3pyY"
DB_PATH = "../db.sqlite3"  # путь к базе

# id чата для авторассылки (туда бот будет слать сообщения сам каждый день)
CHAT_ID = "ТВОЙ_CHAT_ID"  # подставь сюда реальный chat_id для авторассылки!

def get_orders(order_type_id, limit):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if order_type_id == 1:
        cursor.execute("""
            SELECT id, status, due_date, repaired_item
            FROM orders_order 
            WHERE status NOT IN ('done', 'ready', 'issued', 'cancelled')
              AND due_date IS NOT NULL
              AND due_date != '-'
              AND order_type_id = 1
            ORDER BY due_date ASC, id ASC
            LIMIT ?
        """, (limit,))
    else:
        cursor.execute("""
            SELECT id, status, due_date
            FROM orders_order 
            WHERE status NOT IN ('done', 'ready', 'issued', 'cancelled')
              AND due_date IS NOT NULL
              AND due_date != '-'
              AND order_type_id = 2
            ORDER BY due_date ASC, id ASC
            LIMIT ?
        """, (limit,))
    orders = cursor.fetchall()
    conn.close()
    return orders

def rus_status(status):
    status = status.lower()
    if status == "new":
        return "Новый"
    if status == "in_progress":
        return "В работе"
    if status == "awaiting":
        return "Ожидает"
    return status

def format_date(due_date):
    try:
        dt = datetime.strptime(due_date, "%Y-%m-%d")
        return dt.strftime("%d.%m")
    except Exception:
        return due_date
    
def save_chat_id(chat_id):
    # Сохраняем chat_id в файл, если его там еще нет
    chat_id = str(chat_id)
    if not os.path.exists(REGISTERED_CHAT_FILE):
        with open(REGISTERED_CHAT_FILE, "w") as f:
            f.write(chat_id + "\n")
    else:
        with open(REGISTERED_CHAT_FILE, "r") as f:
            lines = f.read().splitlines()
        if chat_id not in lines:
            with open(REGISTERED_CHAT_FILE, "a") as f:
                f.write(chat_id + "\n")

def load_first_chat_id():
    # Загружаем первый chat_id из файла для авторассылки
    if os.path.exists(REGISTERED_CHAT_FILE):
        with open(REGISTERED_CHAT_FILE, "r") as f:
            lines = f.read().splitlines()
        if lines:
            return int(lines[0])
    return None

async def send_hot_orders(bot, chat_id):
    repairs = get_orders(1, 3)
    sales = get_orders(2, 3)
    text = ""

    if not repairs and not sales:
        text = "Нет срочных заказов 🚀"
    else:
        if repairs:
            text += "🔧 Срочные заказы (Ремонт):\n"
            for order in repairs:
                order_id, status, due_date, repaired_item = order
                text += (
                    f"• Заказ {order_id} | Статус: {rus_status(status)} | "
                    f"Изделие: {repaired_item} | Срок: {format_date(due_date)}\n"
                )
        if sales:
            if text:
                text += "\n"
            text += "🛒 Срочные заказы (Продажа):\n"
            for order in sales:
                order_id, status, due_date = order
                text += (
                    f"• Заказ {order_id} | Статус: {rus_status(status)} | "
                    f"Срок: {format_date(due_date)}\n"
                )

    await bot.send_message(chat_id=chat_id, text=text)

async def hot_orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_hot_orders(context.bot, update.effective_chat.id)

async def register_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_chat_id(chat_id)
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Этот чат зарегистрирован для авторассылки! chat_id: {chat_id}"
    )

async def scheduled_send_hot_orders(app):
    chat_id = load_first_chat_id()
    if chat_id:
        await send_hot_orders(app.bot, chat_id)
    else:
        print("Нет зарегистрированного chat_id для рассылки.")

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("hot_orders", hot_orders_command))
    app.add_handler(CommandHandler("register_chat", register_chat_command))  # новая команда

    scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Moscow'))
    scheduler.add_job(scheduled_send_hot_orders, 'cron', hour=10, minute=0, args=[app])
    scheduler.start()

    print("Бот и рассылка запущены.")

    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())