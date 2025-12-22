from django.db import models

# Create your models here.
class UserLogin(models.Model):
    employee = models.OneToOneField(
        'Employee',
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='employee_id',
        related_name='user_login'
    )

    user_name = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=255)

    created_by = models.ForeignKey(
        'Employee',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_user_logins',
        db_column='created_by'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_by = models.ForeignKey(
        'Employee',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='updated_user_logins',
        db_column='updated_by'
    )

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'user_login'

class Employee(models.Model):
    # 基本信息
    name = models.CharField(max_length=100)
    gender = models.SmallIntegerField(null=True, blank=True)  # 0/1/2...
    birthday = models.DateField(null=True, blank=True)

    phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(max_length=254, null=True, blank=True)

    address = models.CharField(max_length=255, null=True, blank=True)

    # 紧急联系人
    emergency_contact_name = models.CharField(max_length=100, null=True, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, null=True, blank=True)
    emergency_contact_relationship = models.CharField(max_length=50, null=True, blank=True)

    # 在职信息
    hire_date = models.DateField(null=True, blank=True)
    leave_date = models.DateField(null=True, blank=True)

    # 组织信息（按你当前设计：直接存名称）
    department_name = models.CharField(max_length=100, null=True, blank=True)
    position_name = models.CharField(max_length=100, null=True, blank=True)

    status = models.SmallIntegerField(default=1)  # 1在职/0离职/2停用...

    # 审计字段（谁创建/更新）
    created_by = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='created_by',
        related_name='created_employees',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')

    updated_by = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='updated_by',
        related_name='updated_employees',
    )
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'employee'
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['email']),
            models.Index(fields=['department_name']),
            models.Index(fields=['position_name']),
            models.Index(fields=['status']),
            models.Index(fields=['deleted_at']),
        ]

    def __str__(self) -> str:
        return f"{self.id}:{self.name}"


from django.db import models


class Technician(models.Model):
    CONTRACT_TYPE_CHOICES = (
        (0, "未定"),
        (1, "长期"),
        (2, "短期"),
        (3, "现场"),
    )

    BUSINESS_STATUS_CHOICES = (
        (0, "待机"),
        (1, "可用"),
        (2, "忙碌"),
        (3, "不可用"),
    )

    employee_id = models.BigIntegerField(
        unique=True,
        verbose_name="员工ID"
    )

    name = models.CharField(
        max_length=100,
        verbose_name="姓名"
    )

    name_mask = models.CharField(
        max_length=100,
        verbose_name="姓名掩码"
    )

    birthday = models.DateField(
        null=True,
        blank=True,
        verbose_name="生日"
    )

    nationality = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="国籍"
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="报价"
    )

    introduction = models.TextField(
        null=True,
        blank=True,
        verbose_name="简介"
    )

    contract_type = models.SmallIntegerField(
        choices=CONTRACT_TYPE_CHOICES,
        default=0,
        verbose_name="合同类型"
    )

    spot_contract_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="现场合同截止日"
    )

    business_status = models.SmallIntegerField(
        choices=BUSINESS_STATUS_CHOICES,
        default=0,
        verbose_name="业务状态"
    )

    ss = models.SmallIntegerField(
        null=True,
        blank=True,
        verbose_name="技能等级/状态"
    )

    remark = models.TextField(
        null=True,
        blank=True,
        verbose_name="备注"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间"
    )

    class Meta:
        managed = False
        db_table = "technician"
        verbose_name = "技术人员"
        verbose_name_plural = "技术人员"

    def __str__(self):
        return f"{self.employee_id} - {self.name_mask}"
