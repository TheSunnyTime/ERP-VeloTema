import sqlite3
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "7763554734:AAGDA226E22vMeqpCTh7w6HlSLGct8W3pyY"
DB_PATH = "../db.sqlite3"  # путь к базе

def get_urgent_orders():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, status, due_date 
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
    if status.lower() == "new":
        return "Новый"
    return status

async def hot_orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    orders = get_urgent_orders()
    if not orders:
        text = "Нет срочных заказов 🚀"
    else:
        text = "🔥 Самые срочные заказы:\n"
        for order in orders:
            text += f"• Заказ {order[0]} | статус: {rus_status(order[1])} | Срок: {order[2]}\n"
    await update.message.reply_text(text)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("hot_orders", hot_orders_command))
    app.run_polling()

if __name__ == "__main__":
    main()