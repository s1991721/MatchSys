from django.db import models


# 登录实体
class UserLogin(models.Model):
    employee_id = models.BigIntegerField(primary_key=True, unique=True, verbose_name="员工ID")

    employee_name = models.CharField(max_length=100, verbose_name="员工姓名")
    user_name = models.CharField(max_length=100, unique=True, verbose_name="登录账号")
    password = models.CharField(max_length=255, verbose_name="密码")
    role_id = models.BigIntegerField(null=True, blank=True, verbose_name="角色ID")
    menu_list = models.TextField(blank=True, verbose_name="菜单列表")

    created_by = models.CharField(max_length=100)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_by = models.CharField(max_length=100)

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'user_login'
        verbose_name = "登录表"


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
    created_by = models.BigIntegerField(unique=True, verbose_name="员工ID")
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')

    updated_by = models.BigIntegerField(unique=True, verbose_name="员工ID")
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'employee'

    def __str__(self) -> str:
        return f"{self.id}:{self.name}"

    def serialize(emp):
        return {
            "id": emp.id,
            "name": emp.name,
            "gender": emp.gender,
            "birthday": emp.birthday.isoformat() if emp.birthday else "",
            "department_name": emp.department_name or "",
            "position_name": emp.position_name or "",
            "phone": emp.phone or "",
            "email": emp.email or "",
            "address": emp.address or "",
            "emergency_contact_name": emp.emergency_contact_name or "",
            "emergency_contact_phone": emp.emergency_contact_phone or "",
            "emergency_contact_relationship": emp.emergency_contact_relationship or "",
            "hire_date": emp.hire_date.isoformat() if emp.hire_date else "",
            "leave_date": emp.leave_date.isoformat() if emp.leave_date else "",
        }


class Technician(models.Model):
    CONTRACT_TYPE_CHOICES = (
        (0, "正社员"),
        (1, "契约社员"),
        (2, "フリーランス"),
    )

    BUSINESS_STATUS_CHOICES = (
        (0, "营业中"),
        (1, "营业中1/2等待"),
        (2, "营业中结果等待"),
        (3, "现场中"),
        (4, "现场已确定"),
    )

    employee_id = models.BigIntegerField(primary_key=True, unique=True, verbose_name="员工ID")

    name = models.CharField(max_length=100, verbose_name="姓名")

    name_mask = models.CharField(max_length=100, verbose_name="姓名掩码")

    birthday = models.DateField(null=True, blank=True, verbose_name="生日")

    nationality = models.CharField(max_length=50, null=True, blank=True, verbose_name="国籍")

    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="报价")

    introduction = models.TextField(null=True, blank=True, verbose_name="简介")

    contract_type = models.SmallIntegerField(choices=CONTRACT_TYPE_CHOICES, default=0, verbose_name="合同类型")

    spot_contract_deadline = models.DateField(null=True, blank=True, verbose_name="现场合同截止日")

    business_status = models.SmallIntegerField(choices=BUSINESS_STATUS_CHOICES, default=0, verbose_name="业务状态")

    ss = models.CharField(max_length=255, null=True, blank=True, verbose_name="SS文件路径")

    remark = models.TextField(null=True, blank=True, verbose_name="备注")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        managed = False
        db_table = "technician"
        verbose_name = "技术人员"
        verbose_name_plural = "技术人员"

    def __str__(self):
        return f"{self.employee_id} - {self.name_mask}"

    # 序列化技术者实体
    def serialize(tech):
        contract_labels = {
            0: "正社员",
            1: "契约社员",
            2: "フリーランス",
        }
        business_labels = {
            0: "营业中",
            1: "现场中",
            2: "现场已确定",
        }
        ss_path = tech.ss or ""
        ss_url = f"/api/ss/{ss_path}" if ss_path else ""
        return {
            "employee_id": tech.employee_id,
            "name": tech.name,
            "name_mask": tech.name_mask,
            "birthday": tech.birthday.isoformat() if tech.birthday else "",
            "nationality": tech.nationality or "",
            "price": str(tech.price) if tech.price is not None else "",
            "introduction": tech.introduction or "",
            "contract_type": tech.contract_type,
            "contract_label": contract_labels.get(tech.contract_type, ""),
            "spot_contract_deadline": tech.spot_contract_deadline.isoformat() if tech.spot_contract_deadline else "",
            "business_status": tech.business_status,
            "business_label": business_labels.get(tech.business_status, ""),
            "ss": ss_path,
            "ss_url": ss_url,
            "remark": tech.remark or "",
        }
