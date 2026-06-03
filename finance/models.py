from django.db import models


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


class PayrollMonthlyCalculation(models.Model):
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
        managed = False
        db_table = "payroll_monthly_calculation"
        verbose_name = "月度工资计算"
        verbose_name_plural = "月度工资计算"

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
