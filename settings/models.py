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


class ScheduledTask(models.Model):
    name = models.CharField("任务名称", max_length=255, blank=True, default="")
    time = models.TimeField("执行时间", null=True, blank=True)
    frequency = models.CharField("执行频率", max_length=50, blank=True, default="")
    cron_expr = models.CharField("Cron 表达式", max_length=100, blank=True, default="")
    method = models.CharField("请求方式", max_length=10, blank=True, default="POST")
    api = models.CharField("API 地址", max_length=500, blank=True, default="")
    body = models.TextField("请求参数 / Body", blank=True, default="")
    enabled = models.BooleanField("是否启用", default=True)
    last_run_at = models.DateTimeField("上次执行时间", null=True, blank=True)
    next_run_at = models.DateTimeField("下次执行时间", null=True, blank=True)
    last_status = models.CharField("上次执行状态", max_length=50, blank=True, default="")
    last_error = models.TextField("上次错误信息", blank=True, default="")
    created_by = models.BigIntegerField("创建人ID", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_by = models.BigIntegerField("更新人ID", null=True, blank=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    deleted_at = models.DateTimeField("删除时间（软删）", null=True, blank=True, db_index=True)

    class Meta:
        db_table = "sys_tasks"
        verbose_name = "定时任务"
        verbose_name_plural = "定时任务"
