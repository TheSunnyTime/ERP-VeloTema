import sqlite3
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime

TOKEN = "7763554734:AAGDA226E22vMeqpCTh7w6HlSLGct8W3pyY"
DB_PATH = "../db.sqlite3"  # путь к базе

def get_orders(order_type_id, limit):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Для ремонта добавляем repaired_item
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
    else:  # Для продажи поле repaired_item не нужно
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
        return "в работе"
    if status == "awaiting":
        return "Ожидает"
    return status

def format_date(due_date):
    try:
        dt = datetime.strptime(due_date, "%Y-%m-%d")
        return dt.strftime("%d.%m")
    except Exception:
        return due_date

async def hot_orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем 3 ремонта и 3 продажи
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

    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("hot_orders", hot_orders_command))
    app.run_polling()

if __name__ == "__main__":
    main()