from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'orders'
    verbose_name = 'Заказы'  # <--- Ваша строка для перевода

    def ready(self):
        # Импортируем обработчики сигналов здесь, чтобы они были зарегистрированы
        # при запуске Django.
        import orders.deadlines.handlers # noqa: F401
        # Если у тебя есть другие сигналы в orders, их тоже можно импортировать здесь.
        # Например: import orders.signals