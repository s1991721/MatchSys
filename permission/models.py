from django.db import models


class Menu(models.Model):
    menu_name = models.CharField(max_length=100)
    menu_html = models.CharField(max_length=200)
    sort_order = models.PositiveIntegerField(default=0)
    created_by = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.CharField(max_length=64, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "sys_menu"

    def __str__(self) -> str:
        return self.menu_name


class Role(models.Model):
    role_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    menu_list = models.TextField(blank=True)
    created_by = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.CharField(max_length=64, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "sys_role"

    def __str__(self) -> str:
        return self.role_name
