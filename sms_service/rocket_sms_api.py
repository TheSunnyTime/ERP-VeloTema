# F:\CRM 2.0\ERP\sms_service\rocket_sms_api.py
import requests
import json
from django.conf import settings
from django.utils import timezone
from .models import SMSSettings, SMSMessage
from django.contrib.auth import get_user_model

User = get_user_model()

class RocketSMSAPI:
    """
    Класс для работы с API Rocket SMS
    Отправляет SMS через сервис rocket-sms.by
    """
    
    def __init__(self):
        """
        Инициализируем класс
        Получаем настройки из базы данных
        """
        try:
            # Берём активные настройки SMS из базы
            self.settings = SMSSettings.objects.filter(is_active=True).first()
            
            if not self.settings:
                raise Exception("Не найдены активные настройки SMS в системе")
                
            # Настройки для API
            self.api_url = self.settings.api_url
            self.username = self.settings.username
            self.password = self.settings.password
            self.sender_name = self.settings.sender_name
            
        except Exception as e:
            print(f"Ошибка инициализации RocketSMSAPI: {e}")
            self.settings = None
    
    def check_balance(self):
        """
        Проверяем баланс на счету Rocket SMS
        Возвращает: словарь с информацией о балансе или ошибке
        """
        if not self.settings:
            return {'success': False, 'error': 'Настройки SMS не найдены'}
        
        try:
            # URL для проверки баланса согласно документации
            balance_url = "http://api.rocketsms.by/json/balance"
            
            # Параметры для POST запроса согласно документации (как в примере PHP)
            data = f"username={self.username}&password={self.password}"
            
            print(f"📡 Отправляем запрос на: {balance_url}")
            print(f"📤 Данные запроса: {data}")
            
            # Отправляем POST запрос к API согласно документации
            response = requests.post(
                balance_url, 
                data=data, 
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            print(f"📥 Статус ответа: {response.status_code}")
            print(f"📄 Ответ сервера: {response.text}")
            
            # Проверяем ответ
            if response.status_code == 200:
                if response.text.strip():  # Проверяем что ответ не пустой
                    try:
                        result = response.json()
                        
                        # Если есть ошибка в ответе
                        if 'error' in result:
                            return {
                                'success': False,
                                'error': f'Ошибка API: {result["error"]}',
                                'raw_response': response.text
                            }
                        
                        # Если всё успешно
                        return {
                            'success': True,
                            'balance': result.get('balance', 0),
                            'currency': result.get('currency', 'BYN'),
                            'raw_response': response.text
                        }
                    except json.JSONDecodeError:
                        return {
                            'success': False,
                            'error': f'Неверный JSON ответ: {response.text}',
                            'raw_response': response.text
                        }
                else:
                    return {
                        'success': False,
                        'error': 'Пустой ответ от API',
                        'raw_response': response.text
                    }
            else:
                return {
                    'success': False,
                    'error': f'Ошибка HTTP: {response.status_code}',
                    'raw_response': response.text
                }
                
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'Превышено время ожидания ответа'}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': f'Ошибка сети: {str(e)}'}
        except Exception as e:
            return {'success': False, 'error': f'Неизвестная ошибка: {str(e)}'}
        
    def send_single_sms(self, phone_number, message_text, user, recipient_name=""):
        """
        Отправляем одно SMS сообщение
        
        phone_number: номер телефона (например: +375291234567)
        message_text: текст сообщения
        user: пользователь который отправляет (для истории)
        recipient_name: имя получателя (необязательно)
        
        Возвращает: словарь с результатом отправки
        """
        if not self.settings:
            return {'success': False, 'error': 'Настройки SMS не найдены'}
        
        # Создаём запись в истории SMS сразу
        sms_message = SMSMessage.objects.create(
            phone_number=phone_number,
            recipient_name=recipient_name,
            message_text=message_text,
            status='pending',
            sent_by=user
        )
        print(f"📝 Создана запись SMS в БД: ID={sms_message.pk}, статус={sms_message.status}")
        
        try:
            # Очищаем номер телефона (убираем пробелы, дефисы)
            clean_phone = phone_number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            
            # URL для отправки SMS согласно документации
            # URL для отправки SMS согласно документации (как в примере)
            sms_url = "http://api.rocketsms.by/json/send"

            # Данные для отправки SMS согласно документации (как в PHP примере)
            data = f"username={self.username}&password={self.password}&phone={clean_phone}&text={message_text}"

            print(f"📡 Отправляем SMS на: {sms_url}")
            print(f"📤 Данные: {data}")

            # Отправляем POST запрос к API
            response = requests.post(
                sms_url, 
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )

            print(f"📥 Ответ SMS API: {response.text}")
            
            # Сохраняем ответ API в базу
            sms_message.api_response = response.text
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    
                    # Проверяем есть ли ошибка в ответе
                    if 'error' in result:
                        # Есть ошибка от API
                        sms_message.status = 'failed'
                        sms_message.save()
                        return {
                            'success': False,
                            'error': f'Ошибка API: {result["error"]}',
                            'sms_record_id': sms_message.id
                        }
                    
                    # Проверяем есть ли ID сообщения (значит отправлено успешно)
                    if 'id' in result:
                        # SMS отправлено успешно
                        sms_message.status = 'sent'
                        sms_message.rocket_sms_id = str(result['id'])
                        
                        # Получаем стоимость из ответа
                        cost_info = result.get('cost', {})
                        if isinstance(cost_info, dict):
                            sms_message.cost = cost_info.get('money', 0)
                        else:
                            sms_message.cost = cost_info
                            
                        sms_message.sent_at = timezone.now()
                        sms_message.save()
                        
                        return {
                            'success': True,
                            'message_id': str(result['id']),
                            'cost': sms_message.cost,
                            'status': result.get('status', 'SENT'),
                            'sms_record_id': sms_message.id
                        }
                    else:
                        # Нет ID в ответе - что-то не так
                        sms_message.status = 'failed'
                        sms_message.save()
                        return {
                            'success': False,
                            'error': 'API не вернул ID сообщения',
                            'sms_record_id': sms_message.id
                        }
                        
                except json.JSONDecodeError:
                    # Не удалось распарсить JSON
                    sms_message.status = 'failed'
                    sms_message.save()
                    return {
                        'success': False,
                        'error': 'Неверный формат ответа от API',
                        'sms_record_id': sms_message.id
                    }
            else:
                # Ошибка HTTP
                sms_message.status = 'failed'
                sms_message.save()
                return {
                    'success': False,
                    'error': f'Ошибка HTTP: {response.status_code}',
                    'sms_record_id': sms_message.id
                }
                
        except requests.exceptions.Timeout:
            sms_message.status = 'failed'
            sms_message.save()
            return {
                'success': False,
                'error': 'Превышено время ожидания ответа',
                'sms_record_id': sms_message.id
            }
        except Exception as e:
            sms_message.status = 'failed'
            sms_message.save()
            return {
                'success': False,
                'error': f'Ошибка отправки: {str(e)}',
                'sms_record_id': sms_message.id
            }
    def test_connection(self):
        """
        Простая проверка соединения с API
        Возвращает: True если всё работает, False если есть проблемы
        """
        balance_result = self.check_balance()
        return balance_result.get('success', False)