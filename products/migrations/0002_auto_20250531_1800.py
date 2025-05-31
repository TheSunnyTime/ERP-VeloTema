# products/migrations/0002_auto_20250531_1800.py
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'), # Убедись, что здесь ссылка на твою первую миграцию '0001_initial.py'
    ]

    operations = [
        migrations.RenameField(
            model_name='product',      # Имя твоей модели
            old_name='wholesale_price', # Старое имя поля
            new_name='cost_price',      # Новое имя поля
        ),
    ]