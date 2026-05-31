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
            "employee_name": employee.name if employee else "",
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
