from django.db import models


class SentEmailLog(models.Model):
    """
    记录通过 Gmail API 发送的邮件，便于后续查询发送结果。
    """

    message_id = models.CharField(max_length=255, unique=True, db_index=True)
    to = models.CharField(max_length=512, blank=True, default="")
    cc = models.CharField(max_length=512, blank=True, default="")
    subject = models.CharField(max_length=512, blank=True, default="")
    body = models.TextField(blank=True, default="")
    attachments = models.TextField(blank=True, default="")  # JSON 序列化的附件名列表
    mail_type = models.IntegerField()  # 邮件类型 0:bp 1:技术者送信 2:案件送信
    sent_at = models.DateTimeField()

    created_by = models.BigIntegerField(null=True, blank=True, verbose_name="员工ID")

    created_at = models.DateTimeField(auto_now_add=True)

    updated_by = models.BigIntegerField(null=True, blank=True, verbose_name="员工ID")

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "sent_email_logs"
        ordering = ["-sent_at"]

    def __str__(self) -> str:
        return f"{self.message_id} @ {self.sent_at}"


class MailProjectInfo(models.Model):
    id = models.CharField(primary_key=True, unique=True, max_length=255, verbose_name="messageId")
    title = models.CharField("邮件标题", max_length=255)
    address = models.CharField("发件人", max_length=255)
    body = models.TextField("正文内容", blank=True, default="")
    files = models.TextField("附件信息", blank=True, default="")
    date = models.DateTimeField("日期", null=True, blank=True)
    remark = models.CharField("备注", max_length=500, blank=True, default="")
    country = models.CharField("国家", max_length=100, blank=True, default="")
    skills = models.CharField("技能要求", max_length=255, blank=True, default="")
    price = models.DecimalField("价格", max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = "mail_project_info"
        verbose_name = "案件邮件"


class MailTechnicianInfo(models.Model):
    id = models.CharField(primary_key=True, unique=True, max_length=255, verbose_name="messageId")
    title = models.CharField("邮件标题", max_length=255)
    address = models.CharField("发件人", max_length=255)
    body = models.TextField("正文内容", blank=True, default="")
    files = models.TextField("附件信息", blank=True, default="")
    date = models.DateTimeField("日期", null=True, blank=True)
    remark = models.CharField("备注", max_length=500, blank=True, default="")
    country = models.CharField("国家", max_length=100, blank=True, default="")
    skills = models.CharField("技能要求", max_length=255, blank=True, default="")
    price = models.DecimalField("价格", max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = "mail_technician_info"
        verbose_name = "技术者邮件"


class SavedMailInfo(models.Model):
    id = models.CharField(primary_key=True, unique=True, max_length=255, verbose_name="messageId")
    date = models.DateTimeField("日期", null=True, blank=True)

    class Meta:
        db_table = "saved_mail_info"
        verbose_name = "系统中存储的邮件列表"
