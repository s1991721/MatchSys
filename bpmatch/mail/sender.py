import base64
import binascii
import json
import smtplib
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import getaddresses, make_msgid
from pathlib import Path
from typing import List, Optional

from django.db import close_old_connections, transaction

from .common import MailToolError, ensure_send_config_for_login
from project import storage
from project.storage import StorageArea


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
        smtp_client=None,
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
        self._send_via_smtp(message, recipients, smtp_client=smtp_client)
        self._persist_sent_log(
            message_id=message_id,
            sent_at=datetime.now(tz=timezone.utc),
            to=to,
            cc=cc,
            subject=subject,
            body=body,
            attachments=attachments,
            in_reply_to=in_reply_to,
            references=ref_to_use,
            mail_type=mail_type,
            created_by=created_by,
        )
        return message_id

    @contextmanager
    def smtp_session(self):
        if self.use_ssl:
            client = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout)
        else:
            client = smtplib.SMTP(self.host, self.port, timeout=self.timeout)

        try:
            if not self.use_ssl:
                client.ehlo()
                client.starttls()
                client.ehlo()
            client.login(self.username, self.password)
            yield client
        finally:
            try:
                client.quit()
            except Exception:
                client.close()

    def _send_via_smtp(
        self,
        message: EmailMessage,
        recipients: List[str],
        smtp_client=None,
    ):
        if smtp_client is not None:
            smtp_client.send_message(
                message,
                from_addr=self.username,
                to_addrs=recipients,
            )
            return

        with self.smtp_session() as client:
            client.send_message(
                message,
                from_addr=self.username,
                to_addrs=recipients,
            )

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
        in_reply_to: Optional[str],
        references: Optional[str],
        mail_type: Optional[int],
        created_by: Optional[int],
    ):
        if not message_id:
            return

        from bpmatch.models import SentEmailLog

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
            "in_reply_to": in_reply_to or "",
            "references": references or "",
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
            try:
                storage.path(StorageArea.SS, path)
            except ValueError:
                raise MailToolError("Invalid attachment path")
            if not storage.exists(StorageArea.SS, path):
                raise MailToolError("Attachment file not found", status=404)
            with storage.open_file(StorageArea.SS, path) as handle:
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


def _validate_task_text(value, field, max_length, required=False):
    text = str(value or "").strip()
    if required and not text:
        raise MailToolError(f"Missing field: {field}")
    if len(text) > max_length:
        raise MailToolError(f"Field too long: {field}")
    return text


def _persist_task_attachments(attachments):
    """将请求内附件转换为可供异步任务读取的持久化引用。"""
    if attachments in (None, ""):
        return []
    if not isinstance(attachments, list):
        raise MailToolError("Invalid field: attachments")

    persisted = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            raise MailToolError("Invalid attachment")

        original_name = Path(str(attachment.get("filename") or "attachment")).name
        content_type = str(
            attachment.get("content_type") or "application/octet-stream"
        ).strip()
        source_path = str(attachment.get("path") or "").strip()
        encoded_content = attachment.get("content") or ""

        if source_path and not encoded_content:
            try:
                storage.path(StorageArea.SS, source_path)
            except ValueError:
                raise MailToolError("Invalid attachment path")
            if not storage.exists(StorageArea.SS, source_path):
                raise MailToolError("Attachment file not found", status=404)
            task_path = source_path
        elif encoded_content:
            try:
                content = base64.b64decode(encoded_content, validate=True)
            except (binascii.Error, ValueError, TypeError):
                raise MailToolError("Invalid attachment content")
            suffix = Path(original_name).suffix
            task_path = (
                f"mail_send_tasks/{datetime.now(tz=timezone.utc):%Y/%m/%d}/"
                f"{uuid.uuid4().hex}{suffix}"
            )
            storage.save_bytes(StorageArea.SS, task_path, content)
        else:
            raise MailToolError("Missing attachment content")

        persisted.append(
            {
                "filename": original_name,
                "path": task_path,
                "content_type": content_type,
            }
        )
    return persisted


def queue_bulk_mail_by_login(login_id, payload):
    """校验群发请求并按收件人拆分写入 mail_send_tasks。"""
    from bpmatch.models import MailSendTask

    if not isinstance(payload, dict):
        raise MailToolError("Invalid request payload")

    subject = _validate_task_text(
        payload.get("subject") or "群发邮件", "subject", 512, required=True
    )
    body = str(payload.get("body") or "").strip()
    if not body:
        raise MailToolError("Missing field: body")
    cc_addr = _validate_task_text(payload.get("cc"), "cc", 1024)
    mail_type = _parse_mail_type(payload.get("mail_type"))
    if mail_type is None:
        mail_type = -1

    recipients = payload.get("recipients") or []
    if not isinstance(recipients, list) or not recipients:
        raise MailToolError("Missing field: recipients")

    valid_recipients = []
    for recipient in recipients:
        if not isinstance(recipient, dict):
            continue
        to_email = _validate_task_text(
            recipient.get("email"), "recipient.email", 320
        )
        if not to_email:
            continue
        company_name = _validate_task_text(
            recipient.get("company_name"), "recipient.company_name", 255
        )
        contact_name = _validate_task_text(
            recipient.get("contact_name"), "recipient.contact_name", 255
        )
        valid_recipients.append(
            (recipient, to_email, company_name, contact_name)
        )

    if not valid_recipients:
        raise MailToolError("Missing valid recipient email")

    persisted_attachments = _persist_task_attachments(payload.get("attachments"))
    tasks = [
        MailSendTask(
            id=uuid.uuid4().hex,
            to_email=to_email,
            cc=cc_addr,
            subject=subject,
            body=_build_bulk_body(body, recipient),
            attachments=persisted_attachments,
            mail_type=mail_type,
            company_name=company_name,
            contact_name=contact_name,
            error_message=None,
            created_by=login_id,
        )
        for recipient, to_email, company_name, contact_name in valid_recipients
    ]
    with transaction.atomic():
        MailSendTask.objects.bulk_create(tasks)
        send_thread = threading.Thread(
            target=_consume_mail_send_tasks,
            args=(int(login_id), tasks),
            name=f"mail-send-{login_id}",
            daemon=True,
        )
        transaction.on_commit(send_thread.start)

    return {"queued_count": len(tasks)}


def queue_mail_by_login(login_id, payload):
    """校验一封邮件并创建独立发送任务；实际发送由后台消费者完成。"""
    from bpmatch.models import MailSendTask

    if not isinstance(payload, dict):
        raise MailToolError("Invalid request payload")

    to_addr = _validate_task_text(payload.get("to"), "to", 320, required=True)
    cc_addr = _validate_task_text(payload.get("cc"), "cc", 1024)
    subject = _validate_task_text(
        payload.get("subject") or "送信页邮件", "subject", 512, required=True
    )
    body = str(payload.get("body") or "").strip()
    if not body:
        raise MailToolError("Missing field: body")
    mail_type = _parse_mail_type(payload.get("mail_type"))
    if mail_type is None:
        mail_type = -1
    in_reply_to = _validate_task_text(
        payload.get("in_reply_to"), "in_reply_to", 998
    )
    references = _validate_task_text(payload.get("references"), "references", 8000)
    persisted_attachments = _persist_task_attachments(payload.get("attachments"))

    task = MailSendTask(
        id=uuid.uuid4().hex,
        to_email=to_addr,
        cc=cc_addr,
        subject=subject,
        body=body,
        attachments=persisted_attachments,
        mail_type=mail_type,
        in_reply_to=in_reply_to,
        references=references,
        error_message=None,
        created_by=login_id,
    )
    with transaction.atomic():
        task.save(force_insert=True)
        send_thread = threading.Thread(
            target=_consume_mail_send_tasks,
            args=(int(login_id), [task]),
            name=f"mail-send-{login_id}-{task.id}",
            daemon=True,
        )
        transaction.on_commit(send_thread.start)

    return {"task_id": task.id, "queued_count": 1}


def _consume_mail_send_tasks(created_by, tasks):
    """直接消费内存中的整批任务并复用一个 SMTP 连接串行发送。"""
    from bpmatch.models import MailSendTask

    close_old_connections()
    try:
        if not tasks:
            return

        try:
            sender, smtp_user = _build_mail_sender(created_by)
            normalized_atts = _normalize_attachments(tasks[0].attachments or [])
        except Exception as exc:
            _mark_mail_tasks_failed(tasks, exc)
            return

        succeeded_ids = []
        failed_tasks = []
        try:
            with sender.smtp_session() as smtp_client:
                for task in tasks:
                    try:
                        sender.send_message(
                            to=task.to_email,
                            cc=task.cc or None,
                            subject=task.subject,
                            body=task.body,
                            sender=smtp_user,
                            attachments=normalized_atts,
                            in_reply_to=task.in_reply_to or None,
                            references=task.references or None,
                            mail_type=task.mail_type,
                            created_by=task.created_by,
                            smtp_client=smtp_client,
                        )
                        succeeded_ids.append(task.pk)
                    except Exception as exc:
                        task.error_message = _format_task_error(exc)
                        failed_tasks.append(task)
        except Exception as exc:
            processed_ids = set(succeeded_ids)
            failed_ids = {task.pk for task in failed_tasks}
            for task in tasks:
                if task.pk not in processed_ids and task.pk not in failed_ids:
                    task.error_message = _format_task_error(exc)
                    failed_tasks.append(task)

        with transaction.atomic():
            if succeeded_ids:
                MailSendTask.objects.filter(
                    pk__in=succeeded_ids,
                    created_by=created_by,
                ).delete()
            if failed_tasks:
                MailSendTask.objects.bulk_update(failed_tasks, ["error_message"])
    finally:
        close_old_connections()


def _mark_mail_tasks_failed(tasks, exc):
    from bpmatch.models import MailSendTask

    error_message = _format_task_error(exc)
    for task in tasks:
        task.error_message = error_message
    MailSendTask.objects.bulk_update(tasks, ["error_message"])


def _format_task_error(exc):
    message = str(exc).strip() or exc.__class__.__name__
    return f"{exc.__class__.__name__}: {message}"[:8000]


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
        valid_recipients = [
            (recipient, str(recipient.get("email") or "").strip())
            for recipient in recipients
            if isinstance(recipient, dict)
            and str(recipient.get("email") or "").strip()
        ]
        if valid_recipients:
            with sender.smtp_session() as smtp_client:
                for recipient, to_addr in valid_recipients:
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
                        smtp_client=smtp_client,
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
