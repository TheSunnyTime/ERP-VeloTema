# suppliers/migrations/000X_correct_existing_supplyitem_batches.py 
# (замени 000X на реальный номер твоей миграции)

from django.db import migrations, models # Добавил models для F

def set_initial_remaining_quantities(apps, schema_editor):
    SupplyItem = apps.get_model('suppliers', 'SupplyItem')

    # Находим все SupplyItem, где quantity_received > 0 
    # и quantity_remaining_in_batch НЕ РАВНО quantity_received.
    # Это могут быть либо те, где remaining = 0 (старые записи), 
    # либо те, где оно почему-то отличается.
    # Мы хотим для всех таких установить remaining = received.
    items_to_correct = SupplyItem.objects.filter(quantity_received__gt=0).exclude(
        quantity_remaining_in_batch=models.F('quantity_received')
    )

    count_corrected = 0
    if items_to_correct.exists():
        print(f"\n[Data Migration] Коррекция quantity_remaining_in_batch для {items_to_correct.count()} записей SupplyItem...")
        for item in items_to_correct:
            old_remaining = item.quantity_remaining_in_batch
            item.quantity_remaining_in_batch = item.quantity_received
            item.save(update_fields=['quantity_remaining_in_batch'])
            print(f"  Исправлено: SupplyItem ID {item.pk}, Product ID: {item.product_id}, "
                  f"Rec: {item.quantity_received}, Old Rem: {old_remaining}, New Rem: {item.quantity_remaining_in_batch}")
            count_corrected +=1
        print(f"[Data Migration] Коррекция завершена. Исправлено записей: {count_corrected}.")
    else:
        print("\n[Data Migration] Не найдено записей SupplyItem, требующих коррекции quantity_remaining_in_batch (где remaining != received).")

def revert_set_initial_remaining_quantities(apps, schema_editor):
    # Эту операцию сложно откатить безопасно, так как мы не знаем,
    # какими были предыдущие значения quantity_remaining_in_batch, если они были не 0.
    # Если они были 0 (как default при миграции), то можно было бы вернуть 0.
    # Пока оставляем пустым, так как это разовая коррекция для инициализации.
    print("\n[Data Migration] Откат операции set_initial_remaining_quantities не выполняется автоматически.")
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('suppliers', '0004_alter_supplyitem_quantity_remaining_in_batch'), # <--- ЗАМЕНИ НА ЭТО
    ]

    operations = [
        migrations.RunPython(set_initial_remaining_quantities, revert_set_initial_remaining_quantities),
    ]