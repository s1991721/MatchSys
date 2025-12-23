from django.db import models

from employee.models import Employee


class AttendancePunch(models.Model):
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
        managed = False
        db_table = "attendance_punch"

    def __str__(self) -> str:
        return f"{self.employee_id} {self.punch_date} {self.punch_time}"


class AttendanceRecord(models.Model):
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
        managed = False
        db_table = "attendance_record"

    def __str__(self) -> str:
        return f"{self.employee_id} {self.punch_date}"


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
