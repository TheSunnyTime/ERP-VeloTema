# Generated by Django 5.2.1 on 2025-06-03 07:58

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='OrderStatusColor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status_key', models.CharField(choices=[('new', 'Новый'), ('in_progress', 'В работе'), ('ready', 'Готов'), ('issued', 'Выдан'), ('cancelled', 'Отменен')], max_length=20, unique=True, verbose_name='Статус заказа (ключ)')),
                ('hex_color', models.CharField(default='#FFFFFF', help_text='Введите цвет в формате #RRGGBB (например, #FF0000 для красного).', max_length=7, verbose_name='HEX-код цвета')),
            ],
            options={
                'verbose_name': 'Цвет статуса заказа',
                'verbose_name_plural': 'Цвета статусов заказов',
                'ordering': ['status_key'],
            },
        ),
    ]
