# orders/migrations/0012_auto_20250531_1819.py
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0011_alter_order_payment_method_on_closure'), # <--- ВОТ ЭТА СТРОКА
    ]

    operations = [
        migrations.RenameField(
            model_name='order',      # Имя твоей модели
            old_name='employee',     # Старое имя поля
            new_name='manager',      # Новое имя поля
        ),
    ]