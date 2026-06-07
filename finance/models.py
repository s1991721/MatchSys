from datetime import date, datetime
from functools import lru_cache

from django.db import connection, models


class FinanceReceivable(models.Model):
    FINANCE_STATUS_CHOICES = (
        (0, "正常"),
        (1, "异常"),
        (2, "核销"),
    )

    pay_request_id = models.BigIntegerField(null=True, blank=True, verbose_name="来源请求书 pay_request.id")
    request_no = models.CharField(max_length=50, null=True, blank=True, verbose_name="请求书号快照")
    customer_id = models.BigIntegerField(null=True, blank=True, verbose_name="客户ID")
    customer_name = models.CharField(max_length=255, verbose_name="客户名称快照")
    receivable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="应收金额")
    received_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="已收金额")
    outstanding_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="未收金额")
    due_date = models.DateField(null=True, blank=True, verbose_name="预定到账日/入金期日")
    finance_status = models.SmallIntegerField(choices=FINANCE_STATUS_CHOICES, default=0, verbose_name="财务处理状态")
    remark = models.TextField(null=True, blank=True, verbose_name="备注")
    created_by = models.BigIntegerField(null=True, blank=True, verbose_name="创建人 employee.id")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_by = models.BigIntegerField(null=True, blank=True, verbose_name="更新人 employee.id")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="删除时间")

    class Meta:
        managed = False
        db_table = "finance_receivable"
        verbose_name = "应收台账"
        verbose_name_plural = "应收台账"

    def __str__(self):
        return f"{self.id}:{self.request_no or self.customer_name}"


class PayrollBasicInfo(models.Model):
    CONTRACT_TYPE_CHOICES = (
        (0, "正社员"),
        (1, "契约社员"),
        (2, "フリーランス"),
    )
    STATUS_CHOICES = (
        (0, "无效"),
        (1, "有效"),
    )

    employee_id = models.BigIntegerField(verbose_name="员工ID")
    employee_name = models.CharField(max_length=100, verbose_name="员工姓名")
    contract_type = models.SmallIntegerField(choices=CONTRACT_TYPE_CHOICES, default=0, verbose_name="契约类型")
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="基本工资")
    health_insurance = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="社保/健康保险")
    welfare_pension = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="厚生年金")
    employment_insurance = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="雇用保险")
    income_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="所得税")
    valid_until_date = models.DateField(null=True, blank=True, verbose_name="有效期截止日")
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=1, verbose_name="状态")
    remark = models.TextField(null=True, blank=True, verbose_name="备注")
    created_by = models.BigIntegerField(null=True, blank=True, verbose_name="创建人 employee.id")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_by = models.BigIntegerField(null=True, blank=True, verbose_name="更新人 employee.id")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="删除时间")

    class Meta:
        managed = False
        db_table = "payroll_basic_info"
        verbose_name = "工资基础信息"
        verbose_name_plural = "工资基础信息"

    def __str__(self):
        return f"{self.employee_id} payroll basic"

    @staticmethod
    def serialize(item, employee=None):
        contract_labels = {
            0: "正社员",
            1: "契约社员",
            2: "フリーランス",
        }
        status_labels = {
            0: "无效",
            1: "有效",
        }
        return {
            "id": item.id,
            "employee_id": item.employee_id,
            "employee_name": item.employee_name or (employee.name if employee else ""),
            "contract_type": item.contract_type,
            "contract_label": contract_labels.get(item.contract_type, ""),
            "base_salary": str(item.base_salary),
            "health_insurance": str(item.health_insurance),
            "welfare_pension": str(item.welfare_pension),
            "employment_insurance": str(item.employment_insurance),
            "income_tax": str(item.income_tax),
            "valid_until_date": item.valid_until_date.isoformat() if item.valid_until_date else "",
            "status": item.status,
            "status_label": status_labels.get(item.status, ""),
            "remark": item.remark or "",
        }


class PayrollMonthlyCalculationBase(models.Model):
    CONTRACT_TYPE_CHOICES = PayrollBasicInfo.CONTRACT_TYPE_CHOICES
    STATUS_CHOICES = (
        (0, "未确认"),
        (1, "已确认"),
        (2, "已发放"),
    )

    payroll_month = models.DateField(verbose_name="工资月份")
    employee_id = models.BigIntegerField(verbose_name="员工ID")
    employee_name = models.CharField(max_length=100, verbose_name="员工姓名")
    contract_type = models.SmallIntegerField(choices=CONTRACT_TYPE_CHOICES, default=0, verbose_name="契约类型")
    attendance_days = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="出勤日数")
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="基本工资")
    allowance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="补贴")
    deduction_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="扣款")
    social_insurance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="社保/年金/保险")
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="实发金额")
    bank_info = models.JSONField(null=True, blank=True, verbose_name="员工银行信息快照")
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0, verbose_name="状态")
    remark = models.TextField(null=True, blank=True, verbose_name="备注")
    created_by = models.BigIntegerField(null=True, blank=True, verbose_name="创建人 employee.id")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_by = models.BigIntegerField(null=True, blank=True, verbose_name="更新人 employee.id")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="删除时间")

    class Meta:
        abstract = True
        verbose_name = "月度工资计算"
        verbose_name_plural = "月度工资计算"

    @classmethod
    def _resolve_year_suffix(cls, value):
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            return str(value.year)
        try:
            return str(int(value))
        except (TypeError, ValueError):
            raise ValueError("Expected date, datetime, or year for payroll yearly table resolution")

    @classmethod
    def model_for_period(cls, value):
        suffix = cls._resolve_year_suffix(value)
        model = _get_payroll_monthly_calculation_model_for_year(suffix)
        _ensure_payroll_yearly_table_exists(model._meta.db_table, cls._meta.db_table, model)
        return model

    @classmethod
    def objects_for_period(cls, value):
        return cls.model_for_period(value).objects

    @classmethod
    def create_for_period(cls, value, **kwargs):
        return cls.objects_for_period(value).create(**kwargs)

    @classmethod
    def build_for_period(cls, value, **kwargs):
        return cls.model_for_period(value)(**kwargs)

    @classmethod
    def bulk_create_for_period(cls, value, items, **kwargs):
        model = cls.model_for_period(value)
        yearly_items = [
            item if isinstance(item, model) else model(**_copy_payroll_monthly_values(item))
            for item in items
        ]
        return model.objects.bulk_create(yearly_items, **kwargs)

    @staticmethod
    def serialize(item):
        contract_labels = {
            0: "正社员",
            1: "契约社员",
            2: "フリーランス",
        }
        status_labels = {
            0: "未确认",
            1: "已确认",
            2: "已发放",
        }
        return {
            "id": item.id,
            "month": item.payroll_month.strftime("%Y-%m") if item.payroll_month else "",
            "payroll_month": item.payroll_month.isoformat() if item.payroll_month else "",
            "employee_id": item.employee_id,
            "employee_name": item.employee_name,
            "contract_type": item.contract_type,
            "contract_label": contract_labels.get(item.contract_type, ""),
            "attendance_days": str(item.attendance_days),
            "base_salary": str(item.base_salary),
            "allowance_amount": str(item.allowance_amount),
            "deduction_amount": str(item.deduction_amount),
            "social_insurance_amount": str(item.social_insurance_amount),
            "net_salary": str(item.net_salary),
            "bank_info": item.bank_info,
            "status": item.status,
            "status_label": status_labels.get(item.status, ""),
            "remark": item.remark or "",
        }


class PayrollMonthlyCalculation(PayrollMonthlyCalculationBase):
    class Meta:
        managed = False
        db_table = "payroll_monthly_calculation"
        verbose_name = "月度工资计算"
        verbose_name_plural = "月度工资计算"


def _copy_payroll_monthly_values(item):
    return {
        field.name: getattr(item, field.name)
        for field in PayrollMonthlyCalculation._meta.fields
        if field.name != "id"
    }


def _build_payroll_monthly_calculation_year_model(table_name, suffix):
    class Meta:
        db_table = table_name
        managed = False
        app_label = PayrollMonthlyCalculation._meta.app_label
        verbose_name = PayrollMonthlyCalculation._meta.verbose_name
        verbose_name_plural = PayrollMonthlyCalculation._meta.verbose_name_plural

    attrs = {
        "Meta": Meta,
        "__module__": PayrollMonthlyCalculation.__module__,
    }
    return type(f"{PayrollMonthlyCalculation.__name__}{suffix}", (PayrollMonthlyCalculationBase,), attrs)


@lru_cache(maxsize=32)
def _get_payroll_monthly_calculation_model_for_year(suffix):
    table_name = f"{PayrollMonthlyCalculation._meta.db_table}_{suffix}"
    return _build_payroll_monthly_calculation_year_model(table_name, suffix)


def _ensure_payroll_yearly_table_exists(table_name, template_table, model):
    existing_tables = set(connection.introspection.table_names())
    if table_name in existing_tables:
        return

    if connection.vendor == "mysql" and template_table in existing_tables:
        quoted_table = connection.ops.quote_name(table_name)
        quoted_template = connection.ops.quote_name(template_table)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {quoted_table} LIKE {quoted_template}")
        return

    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(model)
