# Generated by Django 5.2.1 on 2025-05-31 15:39

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('salary_management', '0002_allemployeessalaryreportproxy_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='allemployeessalaryreportproxy',
            options={'verbose_name': 'Сводный отчет по зарплате', 'verbose_name_plural': 'Итоговая зарплата'},
        ),
    ]
