# F:\CRM 2.0\ERP\reports\models.py
from django.db import models

class ReportAccessPermission(models.Model):
    class Meta:
        verbose_name = "Права доступа к отчетам"
        verbose_name_plural = "Права доступа к отчетам"
        # Добавляем новое право для отчета по расходам
        permissions = [
            ("view_stock_summary_report", "Может просматривать сводный отчет по остаткам"),
            ("view_cash_overview_report", "Может просматривать отчет по кассе"), # Убедись, что это право используется, если есть такой отчет
            ("view_all_employee_salaries", "Может просматривать все зарплаты сотрудников"),
            ("view_expense_report", "Может просматривать отчет по расходам"), # <--- НАШЕ НОВОЕ ПРАВО
        ]
    def __str__(self):
        # Можно оставить как есть, или не определять, т.к. экземпляры этой модели обычно не создаются напрямую
        return f"Контейнер прав для отчетов {self.pk or ''}"

class StockSummaryReportProxy(ReportAccessPermission): # Родитель ReportAccessPermission
    class Meta:
        proxy = True
        verbose_name = "Сводный отчет по остаткам"
        verbose_name_plural = "Сводный отчет по остаткам"

class EmployeeSalaryReportProxy(ReportAccessPermission): # Родитель ReportAccessPermission
    class Meta:
        proxy = True
        app_label = 'reports' # Можно оставить 'reports', если хочешь чтобы все отчеты были сгруппированы там
        verbose_name = "Мой отчет по зарплате"
        verbose_name_plural = "Мой отчет по зарплате"

class AllEmployeesSalaryReportProxy(ReportAccessPermission): # Родитель ReportAccessPermission
    class Meta:
        proxy = True
        app_label = 'salary_management' 
        verbose_name = "Сводный отчет по зарплате" 
        verbose_name_plural = "Итоговая зарплата" 

# Новая прокси-модель для отчета по расходам
class ExpenseReportProxy(ReportAccessPermission): # Наследуемся от ReportAccessPermission
    class Meta:
        proxy = True
        app_label = 'reports' # Чтобы отображалось в приложении "Отчеты"
        verbose_name = "Отчет по расходам"
        verbose_name_plural = "Отчет по расходам" # Это будет названием ссылки