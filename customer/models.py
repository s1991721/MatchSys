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

    def serialize(customer):
        return {
            "id": customer.id,
            "company_name": customer.company_name or "",
            "company_address": customer.company_address or "",
            "contract": customer.contract or "",
            "remark": customer.remark or "",
            "contact1_name": customer.contact1_name or "",
            "contact1_position": customer.contact1_position or "",
            "contact1_email": customer.contact1_email or "",
            "contact1_phone": customer.contact1_phone or "",
            "contact2_name": customer.contact2_name or "",
            "contact2_position": customer.contact2_position or "",
            "contact2_email": customer.contact2_email or "",
            "contact2_phone": customer.contact2_phone or "",
            "contact3_name": customer.contact3_name or "",
            "contact3_position": customer.contact3_position or "",
            "contact3_email": customer.contact3_email or "",
            "contact3_phone": customer.contact3_phone or "",
            "person_in_charge": customer.person_in_charge or "",
            "created_at": customer.created_at.strftime("%Y-%m-%d %H:%M")
            if customer.created_at
            else "",
        }

    def get_customer_by_payload(customer,payload):
        customer.company_name = (payload.get("company_name") or "").strip()
        customer.company_address = (payload.get("company_address") or "").strip()
        customer.remark = (payload.get("remark") or "").strip()
        customer.contact1_name = (payload.get("contact1_name") or "").strip()
        customer.contact1_position = (payload.get("contact1_position") or "").strip()
        customer.contact1_email = (payload.get("contact1_email") or "").strip()
        customer.contact1_phone = (payload.get("contact1_phone") or "").strip()
        customer.contact2_name = (payload.get("contact2_name") or "").strip()
        customer.contact2_position = (payload.get("contact2_position") or "").strip()
        customer.contact2_email = (payload.get("contact2_email") or "").strip()
        customer.contact2_phone = (payload.get("contact2_phone") or "").strip()
        customer.contact3_name = (payload.get("contact3_name") or "").strip()
        customer.contact3_position = (payload.get("contact3_position") or "").strip()
        customer.contact3_email = (payload.get("contact3_email") or "").strip()
        customer.contact3_phone = (payload.get("contact3_phone") or "").strip()
        customer.person_in_charge = (payload.get("person_in_charge") or "").strip()
        if "contract" in payload:
            customer.contract = (payload.get("contract") or "").strip()

        return customer