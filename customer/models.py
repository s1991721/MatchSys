from django.db import models


class Customer(models.Model):
    company_name = models.CharField(max_length=255)
    company_address = models.CharField(max_length=255, null=True, blank=True)
    contract = models.TextField(null=True, blank=True)
    remark = models.TextField(null=True, blank=True)

    contact1_name = models.CharField(max_length=100, null=True, blank=True)
    contact1_position = models.CharField(max_length=100, null=True, blank=True)
    contact1_email = models.EmailField(max_length=254, null=True, blank=True)
    contact1_phone = models.CharField(max_length=50, null=True, blank=True)

    contact2_name = models.CharField(max_length=100, null=True, blank=True)
    contact2_phone = models.CharField(max_length=50, null=True, blank=True)
    contact2_email = models.EmailField(max_length=254, null=True, blank=True)
    contact2_position = models.CharField(max_length=100, null=True, blank=True)

    contact3_name = models.CharField(max_length=100, null=True, blank=True)
    contact3_position = models.CharField(max_length=100, null=True, blank=True)
    contact3_email = models.EmailField(max_length=254, null=True, blank=True)
    contact3_phone = models.CharField(max_length=50, null=True, blank=True)

    person_in_charge = models.CharField(max_length=100, null=True, blank=True)
    created_by = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.BigIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "customer"

    def __str__(self) -> str:
        return f"{self.id}:{self.company_name}"
