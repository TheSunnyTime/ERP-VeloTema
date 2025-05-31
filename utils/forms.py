# F:\CRM 2.0\ERP\utils\forms.py
from django import forms
# Если SalaryPaymentAdminForm будет использоваться, нужно импортировать SalaryPayment
# from .models import SalaryPayment 

class CsvImportForm(forms.Form):
    csv_file = forms.FileField(label="CSV файл прайс-листа")

# --- ФОРМА ДЛЯ SalaryPaymentAdmin ---
# Эту форму можно сделать очень простой, так как основная логика
# отображения баланса и прав доступа находится в SalaryPaymentAdmin.
# Если у тебя нет других кастомных полей или валидации для SalaryPayment,
# ты можешь даже не определять эту форму и убрать form = SalaryPaymentAdminForm
# из класса SalaryPaymentAdmin в utils/admin.py. Django тогда использует стандартную ModelForm.

# class SalaryPaymentAdminForm(forms.ModelForm):
#     class Meta:
#         model = SalaryPayment # Убедись, что SalaryPayment импортирована, если раскомментируешь
#         fields = '__all__'
    
    # Никаких кастомных clean-методов или дополнительных полей здесь больше не нужно
    # для отображения баланса, так как это делает SalaryPaymentAdmin.display_current_employee_balance