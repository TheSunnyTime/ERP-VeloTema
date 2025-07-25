# Generated by Django 5.2.1 on 2025-05-27 19:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0007_alter_order_target_cash_register'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='service',
            options={'ordering': ['name'], 'verbose_name': 'Услуга', 'verbose_name_plural': 'Услуги'},
        ),
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[('new', 'Новый'), ('in_progress', 'В работе'), ('issued', 'Выдан'), ('cancelled', 'Отменен')], default='new', max_length=20, verbose_name='Статус заказа'),
        ),
    ]
