from django.db import models


class SysSettings(models.Model):
    name = models.CharField("配置名称（唯一）", max_length=255, unique=True)
    settings = models.JSONField("配置内容（JSON）")
    created_by = models.BigIntegerField("创建人ID", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_by = models.BigIntegerField("更新人ID", null=True, blank=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    deleted_at = models.DateTimeField("删除时间（软删）", null=True, blank=True, db_index=True)

    class Meta:
        db_table = "sys_settings"
        verbose_name = "系统设置"
        verbose_name_plural = "系统设置"
