import base64
import json
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import getaddresses, make_msgid
from typing import List, Optional


class SmtpMailSender:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_ssl: Optional[bool] = None,
        timeout: int = 15,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        if use_ssl is None:
            use_ssl = port == 465
        self.use_ssl = use_ssl

    def send_message(
        self,
        to: str,
        subject: str,
        body: str,
        sender: Optional[str] = None,
        cc: Optional[str] = None,
        attachments: Optional[List[dict]] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
        mail_type: Optional[int] = None,
        created_by: Optional[int] = None,
    ) -> str:
        message = EmailMessage()
        message.set_content(body or "")

        message_id = make_msgid()
        message["Message-ID"] = message_id

        message["From"] = sender or self.username
        message["To"] = to
        if cc:
            message["Cc"] = cc
        message["Subject"] = subject
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
        ref_to_use = references or ""
        if not ref_to_use and in_reply_to:
            ref_to_use = in_reply_to
        if ref_to_use:
            message["References"] = ref_to_use

        for att in attachments or []:
            if not isinstance(att, dict):
                continue
            fname = att.get("filename") or "attachment"
            ctype = att.get("content_type") or "application/octet-stream"
            raw_bytes = att.get("content") or b""
            if isinstance(raw_bytes, str):
                try:
                    raw_bytes = base64.b64decode(raw_bytes)
                except Exception:
                    raw_bytes = raw_bytes.encode("utf-8", errors="ignore")
            try:
                maintype, subtype = ctype.split("/", 1)
            except ValueError:
                maintype, subtype = "application", "octet-stream"
            message.add_attachment(
                raw_bytes,
                maintype=maintype,
                subtype=subtype,
                filename=fname,
            )

        recipients = self._collect_recipients(to, cc)

        if self.use_ssl:
            with smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout) as client:
                client.login(self.username, self.password)
                client.send_message(message, from_addr=self.username, to_addrs=recipients)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as client:
                client.ehlo()
                client.starttls()
                client.ehlo()
                client.login(self.username, self.password)
                client.send_message(message, from_addr=self.username, to_addrs=recipients)

        self._persist_sent_log(
            message_id=message_id,
            sent_at=datetime.now(tz=timezone.utc),
            to=to,
            cc=cc,
            subject=subject,
            body=body,
            attachments=attachments,
            mail_type=mail_type,
            created_by=created_by,
        )

        return message_id

    def _collect_recipients(self, to: str, cc: Optional[str]) -> List[str]:
        all_addrs = []
        for value in (to, cc or ""):
            if value:
                all_addrs.extend([addr for _, addr in getaddresses([value]) if addr])
        return all_addrs

    def _persist_sent_log(
        self,
        message_id: Optional[str],
        sent_at: datetime,
        to: Optional[str],
        cc: Optional[str],
        subject: Optional[str],
        body: Optional[str],
        attachments: Optional[List[dict]],
        mail_type: Optional[int],
        created_by: Optional[int],
    ):
        if not message_id:
            return

        try:
            from .models import SentEmailLog
        except Exception:
            return

        try:
            filenames = []
            for att in attachments or []:
                if not isinstance(att, dict):
                    continue
                fname = att.get("filename")
                if fname:
                    filenames.append(str(fname))

            defaults = {
                "sent_at": sent_at,
                "to": to or "",
                "cc": cc or "",
                "subject": subject or "",
                "body": body or "",
                "attachments": json.dumps(filenames, ensure_ascii=False),
            }
            if mail_type is not None:
                defaults["mail_type"] = mail_type
            if created_by is not None:
                defaults["created_by"] = created_by
                defaults["updated_by"] = created_by

            SentEmailLog.objects.update_or_create(
                message_id=message_id,
                defaults=defaults,
            )
        except Exception as exc:
            print(f"[smtp] 保存发送记录失败: {exc}")


def test_smtp_connection(
    host: str,
    port: int,
    username: str,
    password: str,
    use_ssl: Optional[bool] = None,
    timeout: int = 15,
) -> dict:
    if use_ssl is None:
        use_ssl = port == 465

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=timeout) as client:
            client.login(username, password)
    else:
        with smtplib.SMTP(host, port, timeout=timeout) as client:
            client.ehlo()
            client.starttls()
            client.ehlo()
            client.login(username, password)

    return {"message": "连接成功"}
