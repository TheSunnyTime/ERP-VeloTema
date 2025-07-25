# Generated by Django 5.2.1 on 2025-06-03 07:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0015_alter_order_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[('new', 'Новый'), ('in_progress', 'В работе'), ('ready', 'Готов'), ('issued', 'Выдан'), ('cancelled', 'Отменен')], default='new', max_length=20, verbose_name='Статус заказа'),
        ),
        migrations.AlterField(
            model_name='orderproductitem',
            name='cost_price_at_sale',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Себестоимость на момент заказа (FIFO)'),
        ),
    ]
