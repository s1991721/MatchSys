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
