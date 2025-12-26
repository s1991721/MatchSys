from django.db import models


class PurchaseOrder(models.Model):
    order_no = models.CharField(max_length=50)
    person_in_charge = models.CharField(max_length=100)
    status = models.CharField(max_length=50)
    project_name = models.CharField(max_length=255)
    customer_id = models.BigIntegerField()
    customer_name = models.CharField(max_length=255)
    technician_name = models.CharField(max_length=255, null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    working_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    period_start = models.DateField()
    period_end = models.DateField()
    created_by = models.CharField(max_length=100)
    created_at = models.DateTimeField()
    updated_by = models.CharField(max_length=100, null=True, blank=True)
    updated_at = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "purchase_order"

    def __str__(self) -> str:
        return f"{self.id}:{self.order_no}"


class SalesOrder(models.Model):
    order_no = models.CharField(max_length=50)
    person_in_charge = models.CharField(max_length=100)
    status = models.CharField(max_length=50)
    purchase_id = models.BigIntegerField()
    project_name = models.CharField(max_length=255)
    customer_id = models.BigIntegerField()
    customer_name = models.CharField(max_length=255)
    technician_id = models.BigIntegerField(null=True, blank=True)
    technician_name = models.CharField(max_length=255, null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    working_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    period_start = models.DateField()
    period_end = models.DateField()
    created_by = models.CharField(max_length=100)
    created_at = models.DateTimeField()
    updated_by = models.CharField(max_length=100, null=True, blank=True)
    updated_at = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "sales_order"

    def __str__(self) -> str:
        return f"{self.id}:{self.order_no}"
