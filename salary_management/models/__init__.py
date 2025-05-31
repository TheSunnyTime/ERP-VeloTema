from .core_models import EmployeeRate, SalaryCalculation, SalaryPayment
# Импортируем обе модели из detail_models.py
from .detail_models import SalaryCalculationDetail, ProductSalaryDetail 

__all__ = [
    'EmployeeRate',
    'SalaryCalculation',
    'SalaryPayment',
    'SalaryCalculationDetail',
    'ProductSalaryDetail', # Добавляем ProductSalaryDetail
]