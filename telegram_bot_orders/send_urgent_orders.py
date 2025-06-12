import sqlite3
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime  # Новый импорт

TOKEN = "7763554734:AAGDA226E22vMeqpCTh7w6HlSLGct8W3pyY"
DB_PATH = "../db.sqlite3"  # путь к базе

def get_urgent_orders():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, status, due_date, repaired_item
        FROM orders_order 
        WHERE status != 'done'
          AND due_date IS NOT NULL
          AND due_date != '-'
        ORDER BY due_date ASC, id ASC
        LIMIT 5
    """)
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
    # Преобразуем "2025-06-08" в "06.08"
    try:
        dt = datetime.strptime(due_date, "%Y-%m-%d")
        return dt.strftime("%d.%m")
    except Exception:
        return due_date  # если не получилось преобразовать — вернем как есть

async def urgent_orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    orders = get_urgent_orders()
    if not orders:
        text = "Нет срочных заказов 🚀"
    else:
        text = "🔥 Самые срочные заказы:\n"
        for order in orders:
            order_id, status, due_date, repaired_item = order
            text += (
                f"• Заказ {order_id} | статус: {rus_status(status)} | "
                f"Изделие: {repaired_item} | Срок: {format_date(due_date)}\n"
            )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("hot_orders", urgent_orders_command))
    app.run_polling()

if __name__ == "__main__":
    main()