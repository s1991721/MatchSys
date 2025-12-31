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

    @staticmethod
    def serialize(menu):
        return {
            "id": menu.id,
            "menu_name": menu.menu_name or "",
            "menu_html": menu.menu_html or "",
            "sort_order": menu.sort_order or 0,
            "created_at": menu.created_at.strftime("%Y-%m-%d %H:%M")
            if menu.created_at
            else "",
        }

    @staticmethod
    def apply_payload(menu, payload):
        menu.menu_name = (payload.get("menu_name") or "").strip()
        menu.menu_html = (payload.get("menu_html") or "").strip()
        sort_value = payload.get("sort_order")
        try:
            menu.sort_order = int(sort_value)
        except (TypeError, ValueError):
            menu.sort_order = 0
        return menu


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

    @staticmethod
    def serialize(role):
        return {
            "id": role.id,
            "role_name": role.role_name or "",
            "description": role.description or "",
            "menu_list": role.menu_list or "",
            "created_at": role.created_at.strftime("%Y-%m-%d %H:%M")
            if role.created_at
            else "",
        }

    @staticmethod
    def apply_payload(role, payload):
        role.role_name = (payload.get("role_name") or "").strip()
        role.description = (payload.get("description") or "").strip()
        if "menu_list" in payload:
            role.menu_list = (payload.get("menu_list") or "").strip()
        return role
