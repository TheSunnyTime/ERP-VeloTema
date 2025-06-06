# ERP/clients/management/commands/normalize_phones.py
import re
from django.core.management.base import BaseCommand
from django.db import transaction, IntegrityError
from clients.models import Client 
from django.core.exceptions import ValidationError

class Command(BaseCommand):
    help = (
        "Normalizes phone numbers in the Client model to 375XXXXXXXXX format, "
        "reports on problematic numbers and potential duplicates. "
        "Does NOT automatically fix duplicates or apply changes if duplicates are found."
    )

    def _get_normalized_phone(self, client_instance, original_phone_str):
        if not original_phone_str or not original_phone_str.strip():
            return None, []
        
        temp_phone = re.sub(r'\D', '', original_phone_str)
        if not temp_phone:
            return None, []

        if len(temp_phone) == 9 and not temp_phone.startswith("375"):
            temp_phone = "375" + temp_phone
        elif len(temp_phone) == 10 and temp_phone.startswith("80"):
            temp_phone = "375" + temp_phone[2:]
        
        validation_errors = []
        if temp_phone.startswith("375") and len(temp_phone) != 12:
            validation_errors.append(
                f"Normalized to '{temp_phone}' but has incorrect length (expected 12 digits starting with 375)."
            )
        elif not temp_phone.startswith("375") and len(temp_phone) > 0 :
             validation_errors.append(
                f"Normalized to '{temp_phone}' which is not a standard Belarusian format."
            )

        if validation_errors:
            return temp_phone, validation_errors 
            
        return temp_phone, []


    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Pass 1: Analyzing phone numbers and identifying potential issues..."))
        
        clients_to_examine = [] 
        potential_duplicates_map = {} 

        for client in Client.objects.all():
            original_phone = client.phone
            normalized_phone, errors = self._get_normalized_phone(client, original_phone)
            
            client_data = {
                'id': client.id,
                'name': client.name,
                'original_phone': original_phone,
                'normalized_phone_candidate': normalized_phone,
                'current_db_phone': client.phone, 
                'errors': errors,
                'needs_update': False,
                'is_part_of_duplicate': False
            }
            clients_to_examine.append(client_data)

            if normalized_phone and not errors: 
                if normalized_phone not in potential_duplicates_map:
                    potential_duplicates_map[normalized_phone] = []
                potential_duplicates_map[normalized_phone].append(client.id)

        # Отчет о проблемных номерах
        self.stdout.write(self.style.MIGRATE_HEADING("\n--- Problematic Phone Numbers (Format/Validation Issues) ---")) # ИЗМЕНЕНО
        problems_found = False
        for data in clients_to_examine:
            if data['errors']:
                problems_found = True
                self.stdout.write(self.style.WARNING(
                    f"Client ID {data['id']} ('{data['name']}'): Original '{data['original_phone']}' -> Candidate '{data['normalized_phone_candidate']}'. Errors: {'; '.join(data['errors'])}"
                ))
        if not problems_found:
            self.stdout.write(self.style.SUCCESS("No format/validation issues found in phone numbers during initial analysis."))

        # Отчет о дубликатах
        self.stdout.write(self.style.MIGRATE_HEADING("\n--- Potential Duplicate Phone Numbers (after normalization) ---")) # ИЗМЕНЕНО
        duplicates_found = False
        ids_in_duplicate_sets = set()
        for phone, client_ids in potential_duplicates_map.items():
            if len(client_ids) > 1:
                duplicates_found = True
                ids_in_duplicate_sets.update(client_ids)
                self.stdout.write(self.style.ERROR(f"DUPLICATE: Phone '{phone}' for Client IDs: {client_ids}"))
        
        if not duplicates_found:
            self.stdout.write(self.style.SUCCESS("No duplicate phone numbers found after normalization."))
        else:
            for data in clients_to_examine:
                if data['id'] in ids_in_duplicate_sets:
                    data['is_part_of_duplicate'] = True

        # Определяем, какие номера действительно нужно обновить
        self.stdout.write(self.style.MIGRATE_HEADING("\n--- Proposed Changes (for non-problematic, non-duplicate entries) ---")) # ИЗМЕНЕНО
        clients_to_update_safely = []
        for data in clients_to_examine:
            if not data['errors'] and not data['is_part_of_duplicate']:
                if data['current_db_phone'] != data['normalized_phone_candidate'] or \
                   (data['current_db_phone'] and data['normalized_phone_candidate'] is None) or \
                   (data['current_db_phone'] is None and data['normalized_phone_candidate']):
                    data['needs_update'] = True
                    clients_to_update_safely.append(data)
                    self.stdout.write(
                        f"Client ID {data['id']} ('{data['name']}'): Phone '{data['current_db_phone']}' WILL BE UPDATED to '{data['normalized_phone_candidate']}'"
                    )
        
        if not clients_to_update_safely:
            self.stdout.write(self.style.SUCCESS("No phone numbers require safe automatic updates at this time."))

        if problems_found or duplicates_found:
            self.stdout.write(self.style.WARNING(
                "\nFound problematic numbers or duplicates. Please review the messages above. "
                "Automatic updates will only be applied to non-problematic, non-duplicate entries that need changes."
            ))
            if duplicates_found: 
                 self.stdout.write(self.style.ERROR("CRITICAL: Duplicates found. No automatic updates will be performed. Please fix duplicates manually and re-run."))
                 return 

        if not clients_to_update_safely:
            self.stdout.write(self.style.NOTICE("No updates to perform."))
            return

        if input("\nApply these safe updates? (yes/no): ").lower() != 'yes':
            self.stdout.write(self.style.WARNING("Updates cancelled by user."))
            return

        updated_count = 0
        with transaction.atomic():
            for data in clients_to_update_safely:
                if data['needs_update']:
                    client_to_save = Client.objects.get(pk=data['id'])
                    client_to_save.phone = data['normalized_phone_candidate']
                    try:
                        client_to_save.save(update_fields=['phone'])
                        updated_count += 1
                    except IntegrityError as e:
                        self.stdout.write(self.style.ERROR(f"IntegrityError for Client ID {data['id']} ('{data['name']}') when updating phone to '{data['normalized_phone_candidate']}'. Error: {e}"))
                    except ValidationError as e:
                         self.stdout.write(self.style.ERROR(f"ValidationError for Client ID {data['id']} ('{data['name']}') when updating phone to '{data['normalized_phone_candidate']}'. Error: {e}"))
                    except Exception as e:
                         self.stdout.write(self.style.ERROR(f"Unexpected error for Client ID {data['id']} ('{data['name']}') when updating: {e}"))

        self.stdout.write(self.style.SUCCESS(f"\nSuccessfully applied {updated_count} phone number updates."))