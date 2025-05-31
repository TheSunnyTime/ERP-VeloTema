# F:\CRM 2.0\ERP\reports\models.py
from django.db import models

class ReportAccessPermission(models.Model):
    class Meta:
        verbose_name = "Права доступа к отчетам"
        verbose_name_plural = "Права доступа к отчетам"
        permissions = [
            ("view_stock_summary_report", "Может просматривать сводный отчет по остаткам"),
            ("view_cash_overview_report", "Может просматривать отчет по кассе"),
            ("view_all_employee_salaries", "Может просматривать все зарплаты сотрудников"), 
        ]
    def __str__(self):
        return f"Права для отчетов {self.pk or '(новый)'}"

class StockSummaryReportProxy(ReportAccessPermission):
    class Meta:
        proxy = True
        verbose_name = "Сводный отчет по остаткам"
        verbose_name_plural = "Сводный отчет по остаткам"

class EmployeeSalaryReportProxy(ReportAccessPermission): 
    class Meta:
        proxy = True
        app_label = 'reports' 
        verbose_name = "Мой отчет по зарплате"
        verbose_name_plural = "Мой отчет по зарплате"

class AllEmployeesSalaryReportProxy(ReportAccessPermission): # Родитель остается тем же
    class Meta:
        proxy = True
        app_label = 'salary_management' # <--- ИЗМЕНЕНИЕ: Привязываем к приложению "Зарплаты"
        verbose_name = "Сводный отчет по зарплате" # <--- ИЗМЕНЕНИЕ: Новое имя
        verbose_name_plural = "Итоговая зарплата" # <--- ИЗМЕНЕНИЕ: Новое имя