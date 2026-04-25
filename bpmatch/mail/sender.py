import base64
import json
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import getaddresses, make_msgid
from typing import List, Optional

from .common import MailToolError, ensure_send_config_for_login
from project.common_tools import ss_storage_dir


class MailSender:
    """发信门面，当前底层实现仍然是 SMTP。"""

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
            raw_bytes = att.get("content") or b""
            if isinstance(raw_bytes, str):
                try:
                    raw_bytes = base64.b64decode(raw_bytes)
                except Exception:
                    raw_bytes = raw_bytes.encode("utf-8", errors="ignore")
            content_type = att.get("content_type") or "application/octet-stream"
            try:
                maintype, subtype = content_type.split("/", 1)
            except ValueError:
                maintype, subtype = "application", "octet-stream"
            message.add_attachment(
                raw_bytes,
                maintype=maintype,
                subtype=subtype,
                filename=att.get("filename") or "attachment",
            )

        recipients = self._collect_recipients(to, cc)
        self._send_via_smtp(message, recipients)
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

    def _send_via_smtp(self, message: EmailMessage, recipients: List[str]):
        if self.use_ssl:
            with smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout) as client:
                client.login(self.username, self.password)
                client.send_message(message, from_addr=self.username, to_addrs=recipients)
            return

        with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as client:
            client.ehlo()
            client.starttls()
            client.ehlo()
            client.login(self.username, self.password)
            client.send_message(message, from_addr=self.username, to_addrs=recipients)

    def _collect_recipients(self, to: str, cc: Optional[str]) -> List[str]:
        recipients = []
        for value in (to, cc or ""):
            if value:
                recipients.extend([addr for _, addr in getaddresses([value]) if addr])
        return recipients

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
            from bpmatch.models import SentEmailLog
        except Exception:
            return

        try:
            filenames = []
            for att in attachments or []:
                if not isinstance(att, dict):
                    continue
                if att.get("filename"):
                    filenames.append(str(att["filename"]))
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


SmtpMailSender = MailSender


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


def _parse_mail_type(raw_mail_type):
    if raw_mail_type in (None, ""):
        return None
    try:
        return int(raw_mail_type)
    except (TypeError, ValueError):
        raise MailToolError("Invalid field: mail_type")


def _normalize_attachments(attachments):
    normalized_atts = []
    for att in attachments or []:
        if not isinstance(att, dict):
            continue
        content = att.get("content") or ""
        path = str(att.get("path") or "").strip()
        if path and not content:
            base_dir = os.path.realpath(ss_storage_dir())
            safe_path = os.path.realpath(os.path.join(base_dir, path))
            if not safe_path.startswith(base_dir + os.sep):
                raise MailToolError("Invalid attachment path")
            if not os.path.exists(safe_path):
                raise MailToolError("Attachment file not found", status=404)
            with open(safe_path, "rb") as handle:
                content = handle.read()
        normalized_atts.append(
            {
                "filename": att.get("filename") or "attachment",
                "content_type": att.get("content_type") or "application/octet-stream",
                "content": content,
            }
        )
    return normalized_atts


def _build_mail_sender(login_id):
    send_config = ensure_send_config_for_login(login_id)
    smtp_host = str(send_config.get("smtp") or "").strip()
    smtp_port_raw = str(send_config.get("port") or "").strip()
    smtp_user = str(send_config.get("email") or "").strip()
    smtp_password = str(send_config.get("password") or "")

    if not smtp_host or not smtp_port_raw or not smtp_user or not smtp_password:
        raise MailToolError("Send config is incomplete")
    try:
        smtp_port = int(smtp_port_raw)
    except (TypeError, ValueError):
        raise MailToolError("Invalid SMTP port")

    sender = MailSender(
        host=smtp_host,
        port=smtp_port,
        username=smtp_user,
        password=smtp_password,
    )
    return sender, smtp_user


def _clean_display_name(value):
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace('"', "").replace("'", "")
    if "<" in text and ">" in text:
        text = text.split("<", 1)[0].strip()
    return " ".join(text.split()).strip()


def _build_bulk_salutation(recipient):
    if not isinstance(recipient, dict):
        return ""
    company_name = _clean_display_name(recipient.get("company_name"))
    contact_name = _clean_display_name(recipient.get("contact_name"))

    lines = []
    if company_name:
        lines.append(company_name)
    if contact_name:
        lines.append(f"{contact_name}様")
    elif company_name:
        lines.append("ご担当者様")
    return "\n".join(lines).strip()


def _build_bulk_body(body, recipient):
    base_body = str(body or "").strip()
    if not base_body:
        return ""
    salutation = _build_bulk_salutation(recipient)
    if not salutation:
        return base_body
    return f"{salutation}\n\n{base_body}"


# 根据登录ID获取用户的邮箱配置，从而送信
def send_mail_by_login(login_id, payload):
    to_addr = (payload.get("to") or "").strip()
    cc_addr = (payload.get("cc") or "").strip()
    subject = (payload.get("subject") or "送信页邮件").strip() or "送信页邮件"
    body = payload.get("body") or ""
    attachments = payload.get("attachments") or []
    mail_type = _parse_mail_type(payload.get("mail_type"))

    if not to_addr:
        raise MailToolError("Missing field: to")
    if not body.strip():
        raise MailToolError("Missing field: body")
    normalized_atts = _normalize_attachments(attachments)

    try:
        sender, smtp_user = _build_mail_sender(login_id)
        message_id = sender.send_message(
            to=to_addr,
            cc=cc_addr or None,
            subject=subject,
            body=body,
            sender=smtp_user,
            attachments=normalized_atts,
            in_reply_to=payload.get("in_reply_to"),
            references=payload.get("references"),
            mail_type=mail_type,
            created_by=login_id,
        )
    except Exception as exc:
        raise MailToolError(str(exc), status=500)

    return {"message_id": message_id}


def send_bulk_mail_by_login(login_id, payload):
    subject = (payload.get("subject") or "群发邮件").strip() or "群发邮件"
    body = payload.get("body") or ""
    cc_addr = (payload.get("cc") or "").strip()
    recipients = payload.get("recipients") or []
    attachments = payload.get("attachments") or []
    mail_type = _parse_mail_type(payload.get("mail_type"))

    if not isinstance(recipients, list) or not recipients:
        raise MailToolError("Missing field: recipients")
    if not str(body or "").strip():
        raise MailToolError("Missing field: body")

    normalized_atts = _normalize_attachments(attachments)
    try:
        sender, smtp_user = _build_mail_sender(login_id)
        items = []
        for recipient in recipients:
            if not isinstance(recipient, dict):
                continue
            to_addr = str(recipient.get("email") or "").strip()
            if not to_addr:
                continue
            final_body = _build_bulk_body(body, recipient)
            message_id = sender.send_message(
                to=to_addr,
                cc=cc_addr or None,
                subject=subject,
                body=final_body,
                sender=smtp_user,
                attachments=normalized_atts,
                mail_type=mail_type,
                created_by=login_id,
            )
            items.append(
                {
                    "email": to_addr,
                    "message_id": message_id,
                }
            )
    except MailToolError:
        raise
    except Exception as exc:
        raise MailToolError(str(exc), status=500)

    if not items:
        raise MailToolError("Missing valid recipient email")

    return {"items": items, "count": len(items)}
