import base64
import json
import re
import imaplib
import smtplib
from datetime import datetime, timezone
from email import message_from_bytes, policy
from email.header import decode_header
from email.message import EmailMessage
from email.utils import getaddresses, make_msgid, parsedate_to_datetime
from typing import List, Optional

from django.utils import timezone as django_timezone
from employee.models import UserLogin
from settings.models import SysSettings

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


def _decode_mime_header(value):
    text = str(value or "")
    if not text:
        return ""
    parts = []
    for chunk, encoding in decode_header(text):
        if isinstance(chunk, bytes):
            enc = encoding or "utf-8"
            try:
                parts.append(chunk.decode(enc, errors="replace"))
            except Exception:
                parts.append(chunk.decode("utf-8", errors="replace"))
        else:
            parts.append(str(chunk))
    return "".join(parts).strip()


def _extract_first_email(value):
    pairs = getaddresses([str(value or "")])
    if not pairs:
        return ""
    return (pairs[0][1] or "").strip()


def _resolve_imap_host(smtp_host):
    # 优先按常见服务商做精确映射，其余再按 smtp->imap 规则推导。
    host = str(smtp_host or "").strip().lower()
    if not host:
        return ""
    if "gmail" in host:
        return "imap.gmail.com"
    if "office365" in host or "outlook" in host or "hotmail" in host or "live.com" in host:
        return "outlook.office365.com"
    if host.startswith("smtp."):
        return f"imap.{host[5:]}"
    if "smtp" in host:
        return host.replace("smtp", "imap", 1)
    return host


def _extract_mail_body(mail):
    if mail.is_multipart():
        plain_parts = []
        html_parts = []
        for part in mail.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get_filename():
                continue
            content_type = (part.get_content_type() or "").lower()
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except Exception:
                text = payload.decode("utf-8", errors="replace")
            if content_type == "text/plain":
                plain_parts.append(text)
            elif content_type == "text/html":
                html_parts.append(text)
        if plain_parts:
            return "\n".join(plain_parts).strip()
        if html_parts:
            raw_html = "\n".join(html_parts)
            stripped = re.sub(r"<[^>]+>", "", raw_html)
            return stripped.strip()
        return ""

    payload = mail.get_payload(decode=True) or b""
    charset = mail.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace").strip()
    except Exception:
        return payload.decode("utf-8", errors="replace").strip()


def _format_mail_datetime(date_header):
    raw = str(date_header or "").strip()
    if not raw:
        return ""
    try:
        dt = parsedate_to_datetime(raw)
        if dt is None:
            return raw
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return django_timezone.localtime(dt).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return raw


def _find_send_config_for_login(login_id):
    # sendmsg 的 user 字段支持三种匹配：登录账号、员工名、employee_id。
    user_login = UserLogin.objects.filter(
        employee_id=login_id,
        deleted_at__isnull=True,
    ).first()
    if not user_login:
        return None, "User login not found"

    send_settings = SysSettings.objects.filter(
        name="sendmsg",
        deleted_at__isnull=True,
    ).first()
    send_configs = send_settings.settings if send_settings else []
    if not isinstance(send_configs, list):
        send_configs = []
    target_users = {
        str(user_login.user_name or "").strip(),
        str(user_login.employee_name or "").strip(),
        str(login_id),
    }
    for item in send_configs:
        if not isinstance(item, dict):
            continue
        item_user = str(item.get("user") or "").strip()
        if item_user and item_user in target_users:
            return item, None
    return None, "No send config for current user"


class SmtpToolError(Exception):
    """SMTP/IMAP 业务异常，供视图层转换为统一 API 响应。"""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def send_mail_by_login(login_id, payload):
    to_addr = (payload.get("to") or "").strip()
    cc_addr = (payload.get("cc") or "").strip()
    subject = (payload.get("subject") or "送信页邮件").strip() or "送信页邮件"
    body = payload.get("body") or ""
    attachments = payload.get("attachments") or []
    raw_mail_type = payload.get("mail_type")
    mail_type = None
    if raw_mail_type not in (None, ""):
        try:
            mail_type = int(raw_mail_type)
        except (TypeError, ValueError):
            raise SmtpToolError("Invalid field: mail_type")

    if not to_addr:
        raise SmtpToolError("Missing field: to")
    if not body.strip():
        raise SmtpToolError("Missing field: body")

    send_config, config_error = _find_send_config_for_login(login_id)
    if config_error:
        status = 404 if config_error == "User login not found" else 400
        raise SmtpToolError(config_error, status=status)
    if not send_config:
        raise SmtpToolError("No send config for current user")

    smtp_host = str(send_config.get("smtp") or "").strip()
    smtp_port_raw = str(send_config.get("port") or "").strip()
    smtp_user = str(send_config.get("email") or "").strip()
    smtp_password = str(send_config.get("password") or "")

    if not smtp_host or not smtp_port_raw or not smtp_user or not smtp_password:
        raise SmtpToolError("Send config is incomplete")
    try:
        smtp_port = int(smtp_port_raw)
    except (TypeError, ValueError):
        raise SmtpToolError("Invalid SMTP port")

    # 标准化附件结构
    normalized_atts = []
    for att in attachments:
        if not isinstance(att, dict):
            continue
        normalized_atts.append(
            {
                "filename": att.get("filename") or "attachment",
                "content_type": att.get("content_type") or "application/octet-stream",
                "content": att.get("content") or "",
            }
        )

    try:
        sender = SmtpMailSender(
            host=smtp_host,
            port=smtp_port,
            username=smtp_user,
            password=smtp_password,
        )
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
        raise SmtpToolError(str(exc), status=500)

    return {"message_id": message_id}


def list_my_mails_by_login(login_id, page=1, page_size=20):
    send_config, config_error = _find_send_config_for_login(login_id)
    if config_error:
        status = 404 if config_error == "User login not found" else 400
        raise SmtpToolError(config_error, status=status)

    smtp_host = str(send_config.get("smtp") or "").strip()
    smtp_user = str(send_config.get("email") or "").strip()
    smtp_password = str(send_config.get("password") or "")
    if not smtp_host or not smtp_user or not smtp_password:
        raise SmtpToolError("Send config is incomplete")

    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(page_size)
    except (TypeError, ValueError):
        page_size = 20
    page = max(1, page)
    page_size = max(1, min(page_size, 50))

    imap_host = _resolve_imap_host(smtp_host)
    if not imap_host:
        raise SmtpToolError("Cannot resolve IMAP host from SMTP config")

    mail = None
    try:
        mail = imaplib.IMAP4_SSL(imap_host, 993)
        mail.login(smtp_user, smtp_password)
        status, _select_data = mail.select("INBOX")
        if status != "OK":
            raise SmtpToolError("Failed to open INBOX", status=500)

        status, search_data = mail.search(None, "ALL")
        if status != "OK":
            raise SmtpToolError("Failed to read mailbox", status=500)

        # IMAP SEARCH 返回升序 UID，这里倒序后按页截取实现“最新在前”。
        all_ids = search_data[0].split() if search_data and search_data[0] else []
        all_ids = list(reversed(all_ids))
        total = len(all_ids)
        total_pages = max((total + page_size - 1) // page_size, 1)
        if page > total_pages:
            page = total_pages
        offset = (page - 1) * page_size
        page_ids = all_ids[offset: offset + page_size]

        items = []
        for uid_bytes in page_ids:
            uid = uid_bytes.decode("utf-8", errors="ignore")
            status, fetch_data = mail.fetch(
                uid_bytes,
                "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE MESSAGE-ID REFERENCES REPLY-TO)] FLAGS)",
            )
            if status != "OK" or not fetch_data:
                continue
            header_bytes = b""
            raw_meta = b""
            for row in fetch_data:
                if isinstance(row, tuple):
                    raw_meta = row[0] if isinstance(row[0], bytes) else raw_meta
                    if isinstance(row[1], bytes):
                        header_bytes = row[1]
            if not header_bytes:
                continue
            # 列表页只拉取头信息，避免一次性下载完整正文造成慢查询。
            parsed = message_from_bytes(header_bytes, policy=policy.default)
            subject = _decode_mime_header(parsed.get("Subject"))
            from_raw = _decode_mime_header(parsed.get("From"))
            reply_to = _decode_mime_header(parsed.get("Reply-To"))
            date_text = _format_mail_datetime(parsed.get("Date"))
            message_id = str(parsed.get("Message-ID") or "").strip()
            references = str(parsed.get("References") or "").strip()
            unread = b"\\Seen" not in raw_meta
            items.append(
                {
                    "id": uid,
                    "subject": subject or "(无标题)",
                    "from": from_raw,
                    "from_email": _extract_first_email(from_raw),
                    "reply_to": reply_to,
                    "date": date_text,
                    "unread": unread,
                    "message_id": message_id,
                    "references": references,
                }
            )

        data = {
            "mailbox_email": smtp_user,
            "items": items,
        }
        meta = {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }
        return data, meta
    except Exception as exc:
        if isinstance(exc, SmtpToolError):
            raise
        raise SmtpToolError(str(exc), status=500)
    finally:
        if mail:
            try:
                mail.logout()
            except Exception:
                pass


def get_my_mail_detail_by_login(login_id, mail_id):
    send_config, config_error = _find_send_config_for_login(login_id)
    if config_error:
        status = 404 if config_error == "User login not found" else 400
        raise SmtpToolError(config_error, status=status)

    smtp_host = str(send_config.get("smtp") or "").strip()
    smtp_user = str(send_config.get("email") or "").strip()
    smtp_password = str(send_config.get("password") or "")
    if not smtp_host or not smtp_user or not smtp_password:
        raise SmtpToolError("Send config is incomplete")

    imap_host = _resolve_imap_host(smtp_host)
    if not imap_host:
        raise SmtpToolError("Cannot resolve IMAP host from SMTP config")

    safe_mail_id = str(mail_id or "").strip()
    if not safe_mail_id:
        raise SmtpToolError("Missing field: mail_id")

    mail = None
    try:
        mail = imaplib.IMAP4_SSL(imap_host, 993)
        mail.login(smtp_user, smtp_password)
        status, _select_data = mail.select("INBOX")
        if status != "OK":
            raise SmtpToolError("Failed to open INBOX", status=500)

        # 详情页再按 UID 拉整封 RFC822 原文，保证正文与回复链字段完整。
        status, fetch_data = mail.fetch(
            safe_mail_id.encode("utf-8"),
            "(RFC822 FLAGS)",
        )
        if status != "OK" or not fetch_data:
            raise SmtpToolError("Mail not found", status=404)

        raw_message = b""
        raw_meta = b""
        for row in fetch_data:
            if isinstance(row, tuple):
                raw_meta = row[0] if isinstance(row[0], bytes) else raw_meta
                if isinstance(row[1], bytes):
                    raw_message = row[1]
        if not raw_message:
            raise SmtpToolError("Mail not found", status=404)

        parsed = message_from_bytes(raw_message, policy=policy.default)
        subject = _decode_mime_header(parsed.get("Subject")) or "(无标题)"
        from_raw = _decode_mime_header(parsed.get("From"))
        to_raw = _decode_mime_header(parsed.get("To"))
        cc_raw = _decode_mime_header(parsed.get("Cc"))
        date_text = _format_mail_datetime(parsed.get("Date"))
        message_id = str(parsed.get("Message-ID") or "").strip()
        references = str(parsed.get("References") or "").strip()
        in_reply_to = str(parsed.get("In-Reply-To") or "").strip()
        reply_to = _decode_mime_header(parsed.get("Reply-To"))
        body = _extract_mail_body(parsed)
        unread = b"\\Seen" not in raw_meta

        return {
            "id": safe_mail_id,
            "subject": subject,
            "from": from_raw,
            "from_email": _extract_first_email(from_raw),
            "to": to_raw,
            "to_email": _extract_first_email(to_raw),
            "cc": cc_raw,
            "date": date_text,
            "body": body,
            "unread": unread,
            "message_id": message_id,
            "references": references,
            "in_reply_to": in_reply_to,
            "reply_to": reply_to,
            "reply_to_email": _extract_first_email(reply_to) or _extract_first_email(from_raw),
            "mailbox_email": smtp_user,
        }
    except Exception as exc:
        if isinstance(exc, SmtpToolError):
            raise
        raise SmtpToolError(str(exc), status=500)
    finally:
        if mail:
            try:
                mail.logout()
            except Exception:
                pass
