# F:\CRM 2.0\ERP\sms_service\management\commands\test_sms.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from sms_service.rocket_sms_api import RocketSMSAPI
from sms_service.models import SMSSettings

User = get_user_model()

class Command(BaseCommand):
    """
    Команда для тестирования SMS API
    Запуск: python manage.py test_sms
    """
    help = 'Тестирует работу SMS API Rocket SMS'

    def handle(self, *args, **options):
        """Главная функция команды"""
        
        self.stdout.write("🚀 Начинаем тестирование SMS API...")
        
        # Шаг 1: Проверяем настройки SMS
        self.stdout.write("\n📋 Шаг 1: Проверяем настройки SMS")
        
        sms_settings = SMSSettings.objects.filter(is_active=True).first()
        if not sms_settings:
            self.stdout.write(
                self.style.ERROR("❌ Не найдены активные настройки SMS!")
            )
            self.stdout.write("💡 Создайте настройки SMS в админке:")
            self.stdout.write("   - Логин от Rocket SMS")
            self.stdout.write("   - Пароль от Rocket SMS") 
            self.stdout.write("   - Имя отправителя")
            return
        
        self.stdout.write(
            self.style.SUCCESS(f"✅ Настройки найдены: {sms_settings.name}")
        )
        self.stdout.write(f"   Логин: {sms_settings.username}")
        self.stdout.write(f"   Имя отправителя: {sms_settings.sender_name}")
        
        # Шаг 2: Создаём API объект
        self.stdout.write("\n🔧 Шаг 2: Подключаемся к Rocket SMS API")
        
        try:
            api = RocketSMSAPI()
            self.stdout.write(
                self.style.SUCCESS("✅ API объект создан успешно")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Ошибка создания API: {e}")
            )
            return
        
        # Шаг 3: Проверяем соединение
        self.stdout.write("\n🌐 Шаг 3: Проверяем соединение с API")
        
        # Получаем подробную информацию об ошибке
        balance_result = api.check_balance()
        
        if balance_result['success']:
            self.stdout.write(
                self.style.SUCCESS("✅ Соединение с API работает")
            )
        else:
            self.stdout.write(
                self.style.ERROR("❌ Нет соединения с API")
            )
            self.stdout.write(f"🔍 Подробности ошибки: {balance_result['error']}")
            return
        
        # Шаг 4: Проверяем баланс
        self.stdout.write("\n💰 Шаг 4: Проверяем баланс на счету")
        
        balance_result = api.check_balance()
        if balance_result['success']:
            balance = balance_result['balance']
            currency = balance_result.get('currency', 'BYN')
            self.stdout.write(
                self.style.SUCCESS(f"✅ Баланс: {balance} {currency}")
            )
            
            if float(balance) < 1:
                self.stdout.write(
                    self.style.WARNING("⚠️  Внимание: баланс меньше 1 BYN")
                )
        else:
            self.stdout.write(
                self.style.ERROR(f"❌ Ошибка получения баланса: {balance_result['error']}")
            )
            return
        
        # Шаг 5: Итоговая информация
        self.stdout.write("\n🎉 Итого:")
        self.stdout.write("✅ Настройки SMS найдены")
        self.stdout.write("✅ API подключение работает") 
        self.stdout.write("✅ Баланс получен успешно")
        self.stdout.write("\n💡 SMS API готов к работе!")
        self.stdout.write("\n📝 Что дальше:")
        self.stdout.write("   1. Создайте шаблоны SMS в админке")
        self.stdout.write("   2. Попробуйте отправить тестовое SMS")
        self.stdout.write("   3. Настройте автоотправку уведомлений")

        # Шаг 5: Предлагаем отправить тестовое SMS
        self.stdout.write("\n📱 Шаг 5: Тестовая отправка SMS")
        
        # Спрашиваем пользователя
        test_phone = input("📞 Введите номер телефона для теста (например +375291234567) или нажмите Enter для пропуска: ")
        
        if test_phone.strip():
            # Получаем пользователя для записи в историю
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            try:
                # Берём первого суперпользователя
                admin_user = User.objects.filter(is_superuser=True).first()
                if not admin_user:
                    # Создаём тестового пользователя если нет админа
                    admin_user = User.objects.create_user(
                        username='sms_test', 
                        email='test@test.com'
                    )
                
                # Отправляем тестовое SMS
                test_message = "Тестовое SMS от CRM системы. Всё работает!"
                
                self.stdout.write(f"📤 Отправляем тестовое SMS на {test_phone}")
                
                result = api.send_single_sms(
                    phone_number=test_phone,
                    message_text=test_message,
                    user=admin_user,
                    recipient_name="Тестовый получатель"
                )
                
                if result['success']:
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ SMS отправлено! ID: {result.get('message_id', 'N/A')}")
                    )
                    if 'cost' in result:
                        self.stdout.write(f"💰 Стоимость: {result['cost']} BYN")
                else:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Ошибка отправки: {result['error']}")
                    )
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Ошибка при тестовой отправке: {str(e)}")
                )
        else:
            self.stdout.write("⏭️ Тестовая отправка пропущена")