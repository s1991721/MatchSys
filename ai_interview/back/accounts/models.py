from django.db import models


class UserAccount(models.Model):
    """Account stored in the table created by database/init_mysql.sql."""

    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=255)
    display_name = models.CharField(max_length=100)
    company_name = models.CharField(max_length=200)
    company_code = models.CharField(max_length=100, null=True, blank=True)
    created_by = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField()
    updated_by = models.BigIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "user_account"
