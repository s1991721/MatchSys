from django.db import models


class SentEmailLog(models.Model):
    """
    记录通过 Gmail API 发送的邮件，便于后续查询发送结果。
    """

    message_id = models.CharField(max_length=255, unique=True, db_index=True)
    sent_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sent_email_logs"
        ordering = ["-sent_at"]

    def __str__(self) -> str:
        return f"{self.message_id} @ {self.sent_at}"
