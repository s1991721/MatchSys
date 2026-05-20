from django.db import models


class PurchaseOrder(models.Model):
    order_no = models.CharField(max_length=50)
    person_in_charge = models.CharField(max_length=100)
    person_in_charge_id = models.BigIntegerField(null=True, blank=True)
    work_content = models.CharField(max_length=500, null=True, blank=True)
    work_place = models.CharField(max_length=255, null=True, blank=True)
    contract_type = models.CharField(max_length=100, null=True, blank=True)
    payment_terms = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=50)
    project_name = models.CharField(max_length=255)
    customer_id = models.BigIntegerField()
    customer_name = models.CharField(max_length=255)
    line_items = models.JSONField(null=True, blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    remark = models.TextField(null=True, blank=True)
    pdf_file = models.CharField(max_length=255, null=True, blank=True)
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
    person_in_charge_id = models.BigIntegerField(null=True, blank=True)
    person_in_charge = models.CharField(max_length=100)
    status = models.CharField(max_length=50)
    purchase_id = models.BigIntegerField(null=True, blank=True)
    project_name = models.CharField(max_length=255)
    customer_id = models.BigIntegerField()
    customer_name = models.CharField(max_length=255)
    technician_id = models.BigIntegerField(null=True, blank=True)
    technician_name = models.CharField(max_length=255, null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_items = models.JSONField(null=True, blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    remark = models.TextField(null=True, blank=True)
    pdf_file = models.CharField(max_length=255, null=True, blank=True)
    created_by = models.CharField(max_length=100)
    created_at = models.DateTimeField()
    updated_by = models.CharField(max_length=100, null=True, blank=True)
    updated_at = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "sales_order"

    def __str__(self) -> str:
        return f"{self.id}:{self.order_no}"


class PayRequest(models.Model):
    request_no = models.CharField(max_length=50)
    order_no = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=50)
    customer_id = models.BigIntegerField()
    customer_name = models.CharField(max_length=255)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    request_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    details = models.TextField(null=True, blank=True)
    tax_breakdown = models.TextField(null=True, blank=True)
    attachments = models.TextField(null=True, blank=True)
    remark = models.TextField(null=True, blank=True)
    created_by = models.CharField(max_length=100)
    created_at = models.DateTimeField()
    updated_by = models.CharField(max_length=100, null=True, blank=True)
    updated_at = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "pay_request"

    def __str__(self) -> str:
        return f"{self.id}:{self.request_no}"
