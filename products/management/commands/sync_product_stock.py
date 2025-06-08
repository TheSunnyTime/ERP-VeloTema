from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.db import transaction
from products.models import Product
from suppliers.models import SupplyItem # Убедись в правильности импорта

class Command(BaseCommand):
    help = 'Synchronizes Product.stock_quantity with the sum of SupplyItem.quantity_remaining_in_batch for all products.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate the process and show what would be updated, without actually saving changes.',
        )
        parser.add_argument(
            '--product-ids',
            nargs='+',
            type=int,
            help='Specific product IDs to process (optional).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        product_ids = options['product_ids']

        products_to_sync = Product.objects.all()
        if product_ids:
            products_to_sync = products_to_sync.filter(id__in=product_ids)
            self.stdout.write(self.style.WARNING(f"Processing specific products: {product_ids}"))
        else:
            self.stdout.write(self.style.WARNING("Processing all products..."))

        updated_count = 0
        processed_count = 0
        errors_count = 0

        for product in products_to_sync:
            processed_count += 1
            
            # Рассчитываем сумму остатков по всем партиям для этого товара
            # Убедись, что фильтр для SupplyItem корректен (например, только активные поставки, если это нужно)
            # В данном случае, мы просто суммируем все quantity_remaining_in_batch для данного продукта.
            calculated_stock_from_batches = SupplyItem.objects.filter(
                product=product
            ).aggregate(
                total_remaining=Sum('quantity_remaining_in_batch')
            )['total_remaining'] or 0 # Если нет партий или сумма NULL, считаем 0

            if product.stock_quantity != calculated_stock_from_batches:
                self.stdout.write(self.style.NOTICE(
                    f"Product ID {product.id} ('{product.name}'): "
                    f"Current stock_quantity = {product.stock_quantity}, "
                    f"Calculated from batches = {calculated_stock_from_batches}. "
                    f"{'Will be updated.' if not dry_run else 'Would be updated.'}"
                ))
                if not dry_run:
                    try:
                        product.stock_quantity = calculated_stock_from_batches
                        product.save(update_fields=['stock_quantity', 'updated_at']) # Обновляем и updated_at
                        updated_count += 1
                    except Exception as e:
                        self.stderr.write(self.style.ERROR(f"Error updating Product ID {product.id}: {e}"))
                        errors_count +=1
            else:
                self.stdout.write(
                    f"Product ID {product.id} ('{product.name}'): "
                    f"stock_quantity ({product.stock_quantity}) is already in sync with batches."
                )
        
        self.stdout.write(self.style.SUCCESS(f"\nProcessed {processed_count} products."))
        if errors_count > 0:
            self.stderr.write(self.style.ERROR(f"Encountered {errors_count} errors during update."))
        if dry_run:
            self.stdout.write(self.style.WARNING(f"DRY RUN completed. {updated_count} products would have been updated."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully updated stock_quantity for {updated_count} products."))