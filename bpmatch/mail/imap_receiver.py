import imaplib
from datetime import datetime, time, timedelta, timezone
from email import message_from_bytes, policy
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

from django.utils import timezone as django_timezone
from django.utils.dateparse import parse_date as django_parse_date

from bpmatch.models import MyMail

from .common import (
    MailToolError,
    decode_mime_header,
    extract_first_email,
    extract_mail_body,
    format_mail_datetime,
    normalize_security_mode,
    to_bool,
)
from .receiver_interface import ReceiverInterface


def resolve_imap_connection_config(send_config):
    smtp_user = str(send_config.get("email") or "").strip()
    smtp_password = str(send_config.get("password") or "")

    imap_host = str(send_config.get("imap_host") or "").strip()
    imap_port_raw = str(send_config.get("imap_port") or "").strip()
    security = normalize_security_mode(send_config.get("imap_security"))
    imap_folder = str(send_config.get("imap_folder") or "").strip()

    missing_fields = []
    if not imap_host:
        missing_fields.append("imap_host")
    if not imap_port_raw:
        missing_fields.append("imap_port")
    if not security:
        missing_fields.append("imap_security")
    if not imap_folder:
        missing_fields.append("imap_folder")
    if missing_fields:
        raise MailToolError("请先在系统设置中配置完整的 IMAP 参数")

    try:
        imap_port = int(imap_port_raw)
    except (TypeError, ValueError):
        raise MailToolError("Invalid IMAP port")
    if imap_port < 1 or imap_port > 65535:
        raise MailToolError("Invalid IMAP port")

    use_smtp_auth = to_bool(send_config.get("imap_use_smtp_auth"), default=True)
    explicit_imap_user = str(send_config.get("imap_user") or "").strip()
    explicit_imap_password = str(send_config.get("imap_password") or "")

    if use_smtp_auth:
        imap_user = smtp_user or explicit_imap_user
        imap_password = smtp_password or explicit_imap_password
    else:
        imap_user = explicit_imap_user
        imap_password = explicit_imap_password

    if use_smtp_auth and (not smtp_user or not smtp_password):
        raise MailToolError("请先在系统设置中配置完整的 SMTP 登录参数")
    if not use_smtp_auth and (not explicit_imap_user or not explicit_imap_password):
        raise MailToolError("请先在系统设置中配置 IMAP 用户名和密码")

    return {
        "host": imap_host,
        "port": imap_port,
        "security": security,
        "user": imap_user,
        "password": imap_password,
        "folder": imap_folder,
    }


class ImapReceiver(ReceiverInterface):
    def __init__(self, send_config: Dict[str, Any]):
        self.imap_config = resolve_imap_connection_config(send_config)
        self.mail = None
        self.current_mailbox = ""

    def connect(self):
        host = str(self.imap_config.get("host") or "").strip()
        port = int(self.imap_config.get("port") or 0)
        security = normalize_security_mode(self.imap_config.get("security"))

        if security not in ("ssl", "starttls", "none"):
            raise MailToolError("Invalid IMAP security")

        if security == "ssl":
            self.mail = imaplib.IMAP4_SSL(host, port)
        else:
            self.mail = imaplib.IMAP4(host, port)
            if security == "starttls":
                if not hasattr(self.mail, "starttls"):
                    raise MailToolError("IMAP STARTTLS is not supported")
                self.mail.starttls()
        return self.mail

    def authenticate(self, username: str, password: str):
        if not self.mail:
            self.connect()
        self.mail.login(username, password)

    def open_mailbox(self, folder: str):
        client = self._require_mail_client()
        status, _select_data = client.select(folder)
        if status != "OK":
            raise MailToolError(f"Failed to open mailbox: {folder}", status=500)
        self.current_mailbox = folder

    def list_message_ids(self, criteria: Optional[Dict[str, Any]] = None) -> List[bytes]:
        client = self._require_mail_client()
        search_args = self._build_search_args(criteria)
        status, search_data = client.search(None, *search_args)
        if status != "OK":
            raise MailToolError("Failed to read mailbox", status=500)
        return search_data[0].split() if search_data and search_data[0] else []

    def fetch_headers(self, message_id: str, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        client = self._require_mail_client()
        safe_message_id = self.get_stable_remote_id(message_id)
        requested_fields = fields or ["SUBJECT", "FROM", "DATE"]
        fields_expr = " ".join(requested_fields)
        status, fetch_data = client.fetch(
            safe_message_id.encode("utf-8"),
            f"(BODY.PEEK[HEADER.FIELDS ({fields_expr})] FLAGS)",
        )
        if status != "OK" or not fetch_data:
            raise MailToolError("Mail not found", status=404)
        header_bytes, raw_meta = self._extract_fetch_parts(fetch_data)
        if not header_bytes:
            raise MailToolError("Mail not found", status=404)
        parsed = message_from_bytes(header_bytes, policy=policy.default)
        return {
            "message_id": safe_message_id,
            "headers": parsed,
            "flags": raw_meta,
        }

    def fetch_message(self, message_id: str) -> Dict[str, Any]:
        client = self._require_mail_client()
        safe_message_id = self.get_stable_remote_id(message_id)
        status, fetch_data = client.fetch(
            safe_message_id.encode("utf-8"),
            "(RFC822 FLAGS)",
        )
        if status != "OK" or not fetch_data:
            raise MailToolError("Mail not found", status=404)
        raw_message, raw_meta = self._extract_fetch_parts(fetch_data)
        if not raw_message:
            raise MailToolError("Mail not found", status=404)
        return {
            "message_id": safe_message_id,
            "message": message_from_bytes(raw_message, policy=policy.default),
            "flags": raw_meta,
        }

    def get_flags(self, message_id: str) -> Dict[str, Any]:
        header_result = self.fetch_headers(message_id, fields=["DATE"])
        raw_meta = header_result.get("flags") or b""
        return {"unread": b"\\Seen" not in raw_meta, "raw": raw_meta}

    def get_stable_remote_id(self, message_id: str) -> str:
        safe_message_id = str(message_id or "").strip()
        if not safe_message_id:
            raise MailToolError("Missing field: mail_id")
        return safe_message_id

    def supports_folders(self) -> bool:
        return True

    def supports_server_search(self) -> bool:
        return True

    def supports_server_flags(self) -> bool:
        return True

    def logout(self):
        if self.mail:
            try:
                self.mail.logout()
            except Exception:
                pass
            finally:
                self.mail = None

    def test_connection(self) -> Dict[str, Any]:
        try:
            self.login_from_config()
            self.open_configured_mailbox()
            return {
                "message": "连接成功",
                "protocol": "imap",
                "mailbox": str(self.imap_config.get("folder") or ""),
                "mailbox_email": str(self.imap_config.get("user") or "").strip(),
            }
        finally:
            self.logout()

    def sync_mails(self, owner_id, sync_limit=120):
        updated = 0
        now = django_timezone.now()
        start_date = django_timezone.localdate() - timedelta(days=1)
        start_at = django_timezone.make_aware(
            datetime.combine(start_date, time.min),
            django_timezone.get_current_timezone(),
        )
        since_str = start_date.strftime("%d-%b-%Y")
        try:
            self.login_from_config()
            self.open_configured_mailbox()
            all_ids = list(reversed(self.list_message_ids({"search_args": ["SINCE", since_str]})))
            if sync_limit > 0:
                all_ids = all_ids[:sync_limit]

            for uid_bytes in all_ids:
                uid = uid_bytes.decode("utf-8", errors="ignore")
                if not uid or MyMail.objects.filter(id=uid).exists():
                    continue
                header_result = self.fetch_headers(uid, fields=["SUBJECT", "FROM", "DATE"])
                parsed = header_result["headers"]
                raw_meta = header_result["flags"]

                subject = decode_mime_header(parsed.get("Subject")) or "(无标题)"
                from_raw = decode_mime_header(parsed.get("From"))
                received_at = self._parse_received_at(parsed.get("Date"))
                if not received_at:
                    continue

                received_local = django_timezone.localtime(received_at)
                if received_local < start_at or received_local > now:
                    continue

                unread = b"\\Seen" not in raw_meta
                MyMail.objects.create(
                    id=uid,
                    owner_id=owner_id,
                    subject=subject,
                    from_email=extract_first_email(from_raw),
                    received_at=received_at,
                    is_unread=bool(unread),
                )
                updated += 1
            return updated
        finally:
            self.logout()

    def sync_today_mails(self, owner_id, sync_limit=500, only_new=True):
        today = django_timezone.localdate()
        today_str = today.strftime("%d-%b-%Y")
        inserted = 0
        try:
            self.login_from_config()
            self.open_configured_mailbox()
            all_ids = list(reversed(self.list_message_ids({"search_args": ["SINCE", today_str]})))
            if sync_limit > 0:
                all_ids = all_ids[:sync_limit]

            for uid_bytes in all_ids:
                uid = uid_bytes.decode("utf-8", errors="ignore")
                if not uid:
                    continue
                if only_new and MyMail.objects.filter(id=uid).exists():
                    continue

                header_result = self.fetch_headers(uid, fields=["SUBJECT", "FROM", "DATE"])
                parsed = header_result["headers"]
                raw_meta = header_result["flags"]
                subject = decode_mime_header(parsed.get("Subject")) or "(无标题)"
                from_raw = decode_mime_header(parsed.get("From"))
                received_at = self._parse_received_at(parsed.get("Date"))

                if not received_at:
                    continue
                if django_timezone.localtime(received_at).date() != today:
                    continue
                if not only_new and MyMail.objects.filter(id=uid).exists():
                    continue

                unread = b"\\Seen" not in raw_meta
                MyMail.objects.create(
                    id=uid,
                    owner_id=owner_id,
                    subject=subject,
                    from_email=extract_first_email(from_raw),
                    received_at=received_at,
                    is_unread=bool(unread),
                )
                inserted += 1
            return inserted
        finally:
            self.logout()

    def query_mails(self, page=1, page_size=20, keyword="", send_date=""):
        imap_user = str(self.imap_config.get("user") or "").strip()
        page = self._safe_int(page, default=1)
        page_size = max(1, min(self._safe_int(page_size, default=20), 50))

        keyword_text = str(keyword or "").strip()
        send_date_text = str(send_date or "").strip()
        target_date = django_parse_date(send_date_text) if send_date_text else None
        if send_date_text and target_date is None:
            raise MailToolError("Invalid send_date")

        try:
            self.login_from_config()
            self.open_configured_mailbox()
            all_ids = list(reversed(self.list_message_ids({"search_args": ["ALL"]})))

            filtered_items = []
            for uid_bytes in all_ids:
                uid = uid_bytes.decode("utf-8", errors="ignore")
                if not uid:
                    continue
                header_result = self.fetch_headers(
                    uid,
                    fields=["SUBJECT", "FROM", "DATE", "MESSAGE-ID", "REFERENCES", "REPLY-TO"],
                )
                parsed = header_result["headers"]
                raw_meta = header_result["flags"]
                subject = decode_mime_header(parsed.get("Subject")) or "(无标题)"
                from_raw = decode_mime_header(parsed.get("From"))

                if keyword_text and keyword_text.lower() not in subject.lower():
                    continue

                parsed_dt = self._parse_received_at(parsed.get("Date"))
                if target_date:
                    if not parsed_dt:
                        continue
                    if django_timezone.localtime(parsed_dt).date() != target_date:
                        continue

                filtered_items.append(
                    {
                        "id": uid,
                        "subject": subject,
                        "from": from_raw,
                        "from_email": extract_first_email(from_raw),
                        "reply_to": decode_mime_header(parsed.get("Reply-To")),
                        "date": format_mail_datetime(parsed.get("Date")),
                        "unread": b"\\Seen" not in raw_meta,
                        "message_id": str(parsed.get("Message-ID") or "").strip(),
                        "references": str(parsed.get("References") or "").strip(),
                    }
                )

            total = len(filtered_items)
            total_pages = max((total + page_size - 1) // page_size, 1)
            if page > total_pages:
                page = total_pages
            offset = (page - 1) * page_size
            items = filtered_items[offset: offset + page_size]
            return {
                "mailbox_email": imap_user,
                "items": items,
            }, {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            }
        finally:
            self.logout()

    def get_mail_detail(self, mail_id):
        imap_user = str(self.imap_config.get("user") or "").strip()
        try:
            self.login_from_config()
            self.open_configured_mailbox()
            message_result = self.fetch_message(mail_id)
            parsed = message_result["message"]
            raw_meta = message_result["flags"]
            from_raw = decode_mime_header(parsed.get("From"))
            reply_to = decode_mime_header(parsed.get("Reply-To"))

            return {
                "id": self.get_stable_remote_id(mail_id),
                "subject": decode_mime_header(parsed.get("Subject")) or "(无标题)",
                "from": from_raw,
                "from_email": extract_first_email(from_raw),
                "to": decode_mime_header(parsed.get("To")),
                "to_email": extract_first_email(decode_mime_header(parsed.get("To"))),
                "cc": decode_mime_header(parsed.get("Cc")),
                "date": format_mail_datetime(parsed.get("Date")),
                "body": extract_mail_body(parsed),
                "unread": b"\\Seen" not in raw_meta,
                "message_id": str(parsed.get("Message-ID") or "").strip(),
                "references": str(parsed.get("References") or "").strip(),
                "in_reply_to": str(parsed.get("In-Reply-To") or "").strip(),
                "reply_to": reply_to,
                "reply_to_email": extract_first_email(reply_to) or extract_first_email(from_raw),
                "mailbox_email": imap_user,
            }
        finally:
            self.logout()

    def login_from_config(self):
        self.connect()
        self.authenticate(
            str(self.imap_config.get("user") or "").strip(),
            str(self.imap_config.get("password") or ""),
        )

    def open_configured_mailbox(self):
        self.open_mailbox(str(self.imap_config.get("folder") or ""))

    def _require_mail_client(self):
        if not self.mail:
            raise MailToolError("IMAP client is not connected", status=500)
        return self.mail

    def _build_search_args(self, criteria: Optional[Dict[str, Any]] = None) -> List[str]:
        if criteria and isinstance(criteria.get("search_args"), list) and criteria["search_args"]:
            return [str(item) for item in criteria["search_args"]]
        return ["ALL"]

    def _extract_fetch_parts(self, fetch_data):
        raw_message = b""
        raw_meta = b""
        for row in fetch_data:
            if isinstance(row, tuple):
                raw_meta = row[0] if isinstance(row[0], bytes) else raw_meta
                if isinstance(row[1], bytes):
                    raw_message = row[1]
        return raw_message, raw_meta

    def _parse_received_at(self, date_header):
        if not date_header:
            return None
        try:
            parsed_dt = parsedate_to_datetime(str(date_header or ""))
            if parsed_dt:
                if parsed_dt.tzinfo is None:
                    parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
                return parsed_dt
        except Exception:
            return None
        return None

    def _safe_int(self, value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
