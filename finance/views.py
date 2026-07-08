"""财务 API 视图兼容导出模块。"""

from .views_payables import (
    finance_payable_detail_api,
    finance_payable_payments_api,
    finance_payables_api,
    finance_payables_overview_api,
)
from .views_payments import finance_payment_detail_api, finance_payments_api
from .views_payroll import (
    payroll_basic_info_api,
    payroll_basic_info_detail_api,
    payroll_monthly_api,
    payroll_monthly_calculate_api,
    payroll_monthly_detail_api,
    payroll_monthly_recalculate_api,
)
from .views_receivables import (
    finance_receipt_detail_api,
    finance_receivable_detail_api,
    finance_receivable_receipts_api,
    finance_receivables_api,
    finance_receivables_overview_api,
)
from .views_settings import (
    finance_annuity_insurance_settings_api,
    finance_employment_insurance_settings_api,
    finance_income_tax_settings_api,
    finance_payroll_basic_item_settings_api,
    finance_payroll_employment_insurance_settings_api,
)

__all__ = [
    "finance_annuity_insurance_settings_api",
    "finance_employment_insurance_settings_api",
    "finance_income_tax_settings_api",
    "finance_payroll_basic_item_settings_api",
    "finance_payroll_employment_insurance_settings_api",
    "finance_payable_detail_api",
    "finance_payable_payments_api",
    "finance_payables_api",
    "finance_payables_overview_api",
    "finance_payment_detail_api",
    "finance_payments_api",
    "finance_receipt_detail_api",
    "finance_receivable_detail_api",
    "finance_receivable_receipts_api",
    "finance_receivables_api",
    "finance_receivables_overview_api",
    "payroll_basic_info_api",
    "payroll_basic_info_detail_api",
    "payroll_monthly_api",
    "payroll_monthly_calculate_api",
    "payroll_monthly_detail_api",
    "payroll_monthly_recalculate_api",
]
