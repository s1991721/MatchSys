import poplib
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
    extract_mail_files,
    format_mail_datetime,
    normalize_security_mode,
    to_bool,
)
from .receiver_interface import ReceiverInterface


def resolve_pop3_connection_config(send_config):
    smtp_user = str(send_config.get("email") or "").strip()
    smtp_password = str(send_config.get("password") or "")

    pop3_host = str(send_config.get("pop3_host") or send_config.get("imap_host") or "").strip()
    pop3_port_raw = str(send_config.get("pop3_port") or send_config.get("imap_port") or "").strip()
    security = normalize_security_mode(
        send_config.get("pop3_security") or send_config.get("imap_security")
    )

    missing_fields = []
    if not pop3_host:
        missing_fields.append("pop3_host")
    if not pop3_port_raw:
        missing_fields.append("pop3_port")
    if not security:
        missing_fields.append("pop3_security")
    if missing_fields:
        raise MailToolError("请先在系统设置中配置完整的 POP3 参数")

    try:
        pop3_port = int(pop3_port_raw)
    except (TypeError, ValueError):
        raise MailToolError("Invalid POP3 port")
    if pop3_port < 1 or pop3_port > 65535:
        raise MailToolError("Invalid POP3 port")

    use_smtp_auth = to_bool(
        send_config.get("pop3_use_smtp_auth", send_config.get("imap_use_smtp_auth")),
        default=True,
    )
    explicit_pop3_user = str(send_config.get("pop3_user") or send_config.get("imap_user") or "").strip()
    explicit_pop3_password = str(send_config.get("pop3_password") or send_config.get("imap_password") or "")

    if use_smtp_auth:
        pop3_user = smtp_user or explicit_pop3_user
        pop3_password = smtp_password or explicit_pop3_password
    else:
        pop3_user = explicit_pop3_user
        pop3_password = explicit_pop3_password

    if use_smtp_auth and (not smtp_user or not smtp_password):
        raise MailToolError("请先在系统设置中配置完整的 SMTP 登录参数")
    if not use_smtp_auth and (not explicit_pop3_user or not explicit_pop3_password):
        raise MailToolError("请先在系统设置中配置 POP3 用户名和密码")

    return {
        "host": pop3_host,
        "port": pop3_port,
        "security": security,
        "user": pop3_user,
        "password": pop3_password,
        "folder": "INBOX",
    }


class Pop3Receiver(ReceiverInterface):
    def __init__(self, send_config: Dict[str, Any]):
        self.pop3_config = resolve_pop3_connection_config(send_config)
        self.mail = None
        self.current_mailbox = "INBOX"
        self._uidl_map = None

    # 创立连接
    def connect(self):
        host = str(self.pop3_config.get("host") or "").strip()
        port = int(self.pop3_config.get("port") or 0)
        security = normalize_security_mode(self.pop3_config.get("security"))

        if security not in ("ssl", "starttls", "none"):
            raise MailToolError("Invalid POP3 security")

        if security == "ssl":
            self.mail = poplib.POP3_SSL(host, port)
        else:
            self.mail = poplib.POP3(host, port)
            if security == "starttls":
                if not hasattr(self.mail, "stls"):
                    raise MailToolError("POP3 STARTTLS is not supported")
                self.mail.stls()
        return self.mail

    # 登录
    def authenticate(self, username: str, password: str):
        if not self.mail:
            self.connect()
        self.mail.user(username)
        self.mail.pass_(password)

    def open_mailbox(self, folder: str):
        # POP3 只有单邮箱语义，这里保留接口兼容，忽略传入 folder。
        self.current_mailbox = folder or "INBOX"

    def list_message_ids(self, criteria: Optional[Dict[str, Any]] = None) -> List[bytes]:
        _criteria = criteria or {}
        return [uidl.encode("utf-8") for uidl in self._get_uidl_map().keys()]

    def fetch_headers(self, message_id: str, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        _fields = fields or ["SUBJECT", "FROM", "DATE"]
        client = self._require_mail_client()
        safe_message_id = self.get_stable_remote_id(message_id)
        message_number = self._get_message_number(safe_message_id)
        try:
            response = client.top(message_number, 0)
            lines = response[1]
        except Exception:
            response = client.retr(message_number)
            lines = self._extract_header_lines(response[1])

        header_bytes = b"\r\n".join(lines)
        if not header_bytes:
            raise MailToolError("Mail not found", status=404)

        return {
            "message_id": safe_message_id,
            "headers": message_from_bytes(header_bytes, policy=policy.default),
            "flags": b"",
        }

    def fetch_message(self, message_id: str) -> Dict[str, Any]:
        client = self._require_mail_client()
        safe_message_id = self.get_stable_remote_id(message_id)
        message_number = self._get_message_number(safe_message_id)
        try:
            _response, lines, _octets = client.retr(message_number)
        except Exception as exc:
            raise MailToolError(str(exc), status=404)

        raw_message = b"\r\n".join(lines)
        if not raw_message:
            raise MailToolError("Mail not found", status=404)

        return {
            "message_id": safe_message_id,
            "message": message_from_bytes(raw_message, policy=policy.default),
            "flags": b"",
        }

    def get_flags(self, message_id: str) -> Dict[str, Any]:
        safe_message_id = self.get_stable_remote_id(message_id)
        local_mail = MyMail.objects.filter(id=safe_message_id).only("is_unread").first()
        unread = bool(local_mail.is_unread) if local_mail else True
        return {"unread": unread, "raw": b""}

    def get_stable_remote_id(self, message_id: str) -> str:
        safe_message_id = str(message_id or "").strip()
        if not safe_message_id:
            raise MailToolError("Missing field: mail_id")
        return safe_message_id

    def supports_folders(self) -> bool:
        return False

    def supports_server_search(self) -> bool:
        return False

    def supports_server_flags(self) -> bool:
        return False

    def logout(self):
        if self.mail:
            try:
                self.mail.quit()
            except Exception:
                pass
            finally:
                self.mail = None
                self._uidl_map = None

    def test_connection(self) -> Dict[str, Any]:
        try:
            self.login_from_config()
            client = self._require_mail_client()
            message_count, mailbox_size = client.stat()
            return {
                "message": "连接成功",
                "protocol": "pop3",
                "mailbox": "INBOX",
                "mailbox_email": str(self.pop3_config.get("user") or "").strip(),
                "message_count": int(message_count or 0),
                "mailbox_size": int(mailbox_size or 0),
            }
        finally:
            self.logout()

    # 同步本地邮件
    def sync_mails(self, owner_id):
        updated = 0
        now = django_timezone.now()
        start_date = django_timezone.localdate() - timedelta(days=1)
        start_at = django_timezone.make_aware(
            datetime.combine(start_date, time.min),
            django_timezone.get_current_timezone(),
        )
        try:
            self.login_from_config()
            self.open_configured_mailbox()
            all_ids = list(reversed(self.list_message_ids({"search_args": ["ALL"]})))
            remote_ids = []
            for uid_bytes in all_ids:
                uid = uid_bytes.decode("utf-8", errors="ignore")
                if uid:
                    remote_ids.append(uid)
            existing_ids = set(
                MyMail.objects.filter(id__in=remote_ids).values_list("id", flat=True)
            )

            for uid in remote_ids:
                if uid in existing_ids:
                    continue
                message_result = self.fetch_message(uid)
                parsed = message_result["message"]
                received_at = self._parse_received_at(parsed.get("Date"))
                if not received_at:
                    continue

                received_local = django_timezone.localtime(received_at)
                if received_local < start_at or received_local > now:
                    continue

                from_raw = decode_mime_header(parsed.get("From"))
                MyMail.objects.create(
                    id=uid,
                    owner_id=owner_id,
                    subject=decode_mime_header(parsed.get("Subject")) or "(无标题)",
                    from_email=extract_first_email(from_raw),
                    body=extract_mail_body(parsed),
                    files=extract_mail_files(parsed),
                    received_at=received_at,
                    is_unread=True,
                )
                updated += 1
            return updated
        finally:
            self.logout()

    # 根据keyword、send_date查询邮件
    def query_mails(self, owner_id=None, page=1, page_size=20, keyword="", send_date=""):
        pop3_user = str(self.pop3_config.get("user") or "").strip()
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

                flags = self.get_flags(uid)
                filtered_items.append(
                    {
                        "id": uid,
                        "subject": subject,
                        "from": from_raw,
                        "from_email": extract_first_email(from_raw),
                        "reply_to": decode_mime_header(parsed.get("Reply-To")),
                        "date": format_mail_datetime(parsed.get("Date")),
                        "unread": bool(flags.get("unread")),
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
            if owner_id and items:
                page_ids = [str(item.get("id") or "").strip() for item in items if item.get("id")]
                existing_ids = set(
                    MyMail.objects.filter(id__in=page_ids).values_list("id", flat=True)
                )
                for item in items:
                    uid = str(item.get("id") or "").strip()
                    if not uid or uid in existing_ids:
                        continue
                    message_result = self.fetch_message(uid)
                    parsed = message_result["message"]
                    from_raw = decode_mime_header(parsed.get("From"))
                    received_at = self._parse_received_at(parsed.get("Date"))
                    MyMail.objects.create(
                        id=uid,
                        owner_id=owner_id,
                        subject=decode_mime_header(parsed.get("Subject")) or "(无标题)",
                        from_email=extract_first_email(from_raw),
                        body=extract_mail_body(parsed),
                        files=extract_mail_files(parsed),
                        received_at=received_at,
                        is_unread=True,
                    )
                    existing_ids.add(uid)
            return {
                "mailbox_email": pop3_user,
                "items": items,
            }, {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            }
        finally:
            self.logout()

    # 根据配置登录
    def login_from_config(self):
        self.connect()
        self.authenticate(
            str(self.pop3_config.get("user") or "").strip(),
            str(self.pop3_config.get("password") or ""),
        )

    # 指定文件夹
    def open_configured_mailbox(self):
        self.open_mailbox(str(self.pop3_config.get("folder") or "INBOX"))

    def _require_mail_client(self):
        if not self.mail:
            raise MailToolError("POP3 client is not connected", status=500)
        return self.mail

    def _get_uidl_map(self):
        if self._uidl_map is not None:
            return self._uidl_map

        client = self._require_mail_client()
        try:
            _response, lines, _octets = client.uidl()
        except Exception as exc:
            raise MailToolError(str(exc), status=500)

        uidl_map = {}
        for line in lines:
            text = line.decode("utf-8", errors="ignore").strip()
            if not text:
                continue
            parts = text.split()
            if len(parts) < 2:
                continue
            try:
                message_number = int(parts[0])
            except (TypeError, ValueError):
                continue
            uidl_map[parts[1]] = message_number
        self._uidl_map = uidl_map
        return uidl_map

    def _get_message_number(self, message_id: str) -> int:
        uidl_map = self._get_uidl_map()
        try:
            return int(uidl_map[message_id])
        except KeyError:
            raise MailToolError("Mail not found", status=404)

    def _extract_header_lines(self, lines: List[bytes]) -> List[bytes]:
        header_lines = []
        for line in lines:
            if line in (b"", b"\r\n", b"\n"):
                break
            header_lines.append(line)
        return header_lines

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
