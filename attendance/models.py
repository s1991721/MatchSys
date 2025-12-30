from datetime import date, datetime
from functools import lru_cache

from django.db import connection, models

from employee.models import Employee

# 打卡实体
class AttendancePunchBase(models.Model):
    id = models.BigIntegerField(primary_key=True, unique=True, verbose_name="ID")
    employee_id = models.BigIntegerField(unique=True, verbose_name="员工ID")
    punch_date = models.DateField(db_column="punch_date")
    punch_time = models.TimeField(db_column="punch_time")
    punch_type = models.SmallIntegerField(db_column="punch_type")
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    location_text = models.CharField(max_length=255, null=True, blank=True)
    remark = models.TextField(null=True, blank=True)
    # 审计字段（谁创建/更新）
    created_by = models.BigIntegerField(unique=True, verbose_name="员工ID")
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')

    updated_by = models.BigIntegerField(unique=True, verbose_name="员工ID")
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"{self.employee_id} {self.punch_date} {self.punch_time}"


class AttendancePunch(AttendancePunchBase):
    class Meta:
        managed = False
        db_table = "attendance_punch"

# 每日考勤实体
class AttendanceRecordBase(models.Model):
    id = models.BigIntegerField(primary_key=True, unique=True, verbose_name="ID")
    employee_id = models.BigIntegerField(unique=True, verbose_name="员工ID")
    punch_date = models.DateField(db_column="punch_date")
    start_time = models.TimeField(db_column="start_time", null=True, blank=True)
    end_time = models.TimeField(db_column="end_time", null=True, blank=True)
    remark = models.TextField(null=True, blank=True)
    # 审计字段（谁创建/更新）
    created_by = models.BigIntegerField(unique=True, verbose_name="员工ID")
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')

    updated_by = models.BigIntegerField(unique=True, verbose_name="员工ID")
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"{self.employee_id} {self.punch_date}"


class AttendanceRecord(AttendanceRecordBase):
    class Meta:
        managed = False
        db_table = "attendance_record"

# 每个人的考勤规则
class AttendancePolicy(models.Model):
    id = models.BigIntegerField(primary_key=True, unique=True, verbose_name="ID")
    employee_id = models.BigIntegerField(unique=True, verbose_name="员工ID")
    annual_leave = models.IntegerField()
    work_start_time = models.TimeField(db_column="work_start_time")
    work_end_time = models.TimeField(db_column="work_end_time")
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    location_name = models.CharField(max_length=255)
    radius_meters = models.IntegerField()
    remark = models.TextField(null=True, blank=True)
    # 审计字段（谁创建/更新）
    created_by = models.BigIntegerField(unique=True, verbose_name="员工ID")
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')

    updated_by = models.BigIntegerField(unique=True, verbose_name="员工ID")
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "attendance_policy"

    def __str__(self) -> str:
        return f"{self.employee_id} {self.location_name}"


# 月份后缀
def _resolve_month_suffix(value):
    if isinstance(value, datetime):
        value = value.date()
    if not isinstance(value, date):
        raise ValueError("Expected date or datetime for attendance month resolution")
    return value.strftime("%Y%m")


# 构建月份model
def _build_monthly_model(base_model, table_name, suffix):
    class Meta:
        db_table = table_name
        managed = False
        app_label = base_model._meta.app_label

    attrs = {
        "Meta": Meta,
        "__module__": base_model.__module__,
    }
    # 动态创建一个新类
    return type(f"{base_model.__name__}{suffix}", (base_model,), attrs)


@lru_cache(maxsize=120)
# 获取 带后缀的attendance_punch_model
def _get_attendance_punch_model_for_suffix(suffix):
    table_name = f"{AttendancePunch._meta.db_table}_{suffix}"
    return _build_monthly_model(AttendancePunchBase, table_name, suffix)


@lru_cache(maxsize=120)
# 获取 带后缀的attendance_record_model
def _get_attendance_record_model_for_suffix(suffix):
    table_name = f"{AttendanceRecord._meta.db_table}_{suffix}"
    return _build_monthly_model(AttendanceRecordBase, table_name, suffix)


# 获取月份attendance_punch_model
def get_attendance_punch_model(value):
    suffix = _resolve_month_suffix(value)
    return _get_attendance_punch_model_for_suffix(suffix)


# 获取月份attendance_record_model
def get_attendance_record_model(value):
    suffix = _resolve_month_suffix(value)
    return _get_attendance_record_model_for_suffix(suffix)


# 确保表存在
def _ensure_table_exists(table_name, template_table, model):
    # 现有所有表
    existing_tables = set(connection.introspection.table_names())
    if table_name in existing_tables:
        return

    # mysql情况下，创建表
    if connection.vendor == "mysql" and template_table in existing_tables:
        quoted_table = connection.ops.quote_name(table_name)
        quoted_template = connection.ops.quote_name(template_table)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {quoted_table} LIKE {quoted_template}")
        return

    # 非mysql情况下，创建表
    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(model)


# 获取当前月份的model
def get_monthly_attendance_models(value):
    punch_model = get_attendance_punch_model(value)
    record_model = get_attendance_record_model(value)
    _ensure_table_exists(punch_model._meta.db_table, AttendancePunch._meta.db_table, punch_model)
    _ensure_table_exists(record_model._meta.db_table, AttendanceRecord._meta.db_table, record_model)
    return punch_model, record_model
