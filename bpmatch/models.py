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
    status = models.CharField(max_length=20, default="sent", db_index=True)
    sent_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sent_email_logs"
        ordering = ["-sent_at"]

    def __str__(self) -> str:
        return f"{self.message_id} @ {self.sent_at}"
