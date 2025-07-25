# Generated by Django 5.2.1 on 2025-06-04 19:05

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0002_alter_task_payment_cash_register_for_supply'),
        ('uiconfig', '0003_supplystatuscolor'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskStatusColor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hex_color', models.CharField(default='#FFFFFF', help_text='Например, #RRGGBB', max_length=7, verbose_name='HEX цвет')),
                ('task_status', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='tasks.taskstatus', verbose_name='Статус задачи')),
            ],
            options={
                'verbose_name': 'Цвет статуса задачи',
                'verbose_name_plural': 'Цвета статусов задач',
                'ordering': ['task_status__name'],
            },
        ),
    ]
