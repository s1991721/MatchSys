from functools import lru_cache
from datetime import date, datetime

from django.db import connection, models

from employee.models import Employee


class AttendancePunchBase(models.Model):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        db_column="employee_id",
        related_name="attendance_punches",
    )
    punch_date = models.DateField(db_column="punch_date")
    punch_time = models.TimeField(db_column="punch_time")
    punch_type = models.SmallIntegerField(db_column="punch_type")
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    location_text = models.CharField(max_length=255, null=True, blank=True)
    created_by = models.ForeignKey(
        Employee,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_attendance_punches",
        db_column="created_by",
    )
    created_at = models.DateTimeField(db_column="created_at")
    updated_by = models.ForeignKey(
        Employee,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_attendance_punches",
        db_column="updated_by",
    )
    updated_at = models.DateTimeField(db_column="updated_at")
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"{self.employee_id} {self.punch_date} {self.punch_time}"


class AttendancePunch(AttendancePunchBase):
    class Meta:
        managed = False
        db_table = "attendance_punch"


class AttendanceRecordBase(models.Model):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        db_column="employee_id",
        related_name="attendance_records",
    )
    punch_date = models.DateField(db_column="punch_date")
    start_time = models.TimeField(db_column="start_time")
    end_time = models.TimeField(db_column="end_time")
    remark = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        Employee,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_attendance_records",
        db_column="created_by",
    )
    created_at = models.DateTimeField(db_column="created_at")
    updated_by = models.ForeignKey(
        Employee,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_attendance_records",
        db_column="updated_by",
    )
    updated_at = models.DateTimeField(db_column="updated_at")
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"{self.employee_id} {self.punch_date}"


class AttendanceRecord(AttendanceRecordBase):
    class Meta:
        managed = False
        db_table = "attendance_record"


class AttendancePolicy(models.Model):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        db_column="employee_id",
        related_name="attendance_policies",
    )
    work_start_time = models.TimeField(db_column="work_start_time")
    work_end_time = models.TimeField(db_column="work_end_time")
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    location_name = models.CharField(max_length=255)
    radius_meters = models.IntegerField()
    remark = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        Employee,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_attendance_policies",
        db_column="created_by",
    )
    created_at = models.DateTimeField(db_column="created_at")
    updated_by = models.ForeignKey(
        Employee,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_attendance_policies",
        db_column="updated_by",
    )
    updated_at = models.DateTimeField(db_column="updated_at")
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "attendance_policy"

    def __str__(self) -> str:
        return f"{self.employee_id} {self.location_name}"


def _resolve_month_suffix(value):
    if isinstance(value, datetime):
        value = value.date()
    if not isinstance(value, date):
        raise ValueError("Expected date or datetime for attendance month resolution")
    return value.strftime("%Y%m")


def _build_monthly_model(base_model, table_name, suffix):
    class Meta:
        db_table = table_name
        managed = False
        app_label = base_model._meta.app_label

    attrs = {
        "Meta": Meta,
        "__module__": base_model.__module__,
    }
    return type(f"{base_model.__name__}{suffix}", (base_model,), attrs)


@lru_cache(maxsize=120)
def _get_attendance_punch_model_for_suffix(suffix):
    table_name = f"{AttendancePunch._meta.db_table}_{suffix}"
    return _build_monthly_model(AttendancePunchBase, table_name, suffix)


@lru_cache(maxsize=120)
def _get_attendance_record_model_for_suffix(suffix):
    table_name = f"{AttendanceRecord._meta.db_table}_{suffix}"
    return _build_monthly_model(AttendanceRecordBase, table_name, suffix)


def get_attendance_punch_model(value):
    suffix = _resolve_month_suffix(value)
    return _get_attendance_punch_model_for_suffix(suffix)


def get_attendance_record_model(value):
    suffix = _resolve_month_suffix(value)
    return _get_attendance_record_model_for_suffix(suffix)


def _ensure_table_exists(table_name, template_table, model):
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


def get_monthly_attendance_models(value):
    punch_model = get_attendance_punch_model(value)
    record_model = get_attendance_record_model(value)
    _ensure_table_exists(punch_model._meta.db_table, AttendancePunch._meta.db_table, punch_model)
    _ensure_table_exists(record_model._meta.db_table, AttendanceRecord._meta.db_table, record_model)
    return punch_model, record_model
