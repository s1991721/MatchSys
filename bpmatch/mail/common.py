import re
from datetime import timezone
from email.header import decode_header
from email.utils import getaddresses, parsedate_to_datetime

from django.db.models import Q
from django.utils import timezone as django_timezone
from django.utils.dateparse import parse_date as django_parse_date

from employee.models import UserLogin
from settings.models import SysSettings

from bpmatch.models import MyMail


class MailToolError(Exception):
    """邮件业务异常，供视图层转换为统一 API 响应。"""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def decode_mime_header(value):
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


def extract_first_email(value):
    pairs = getaddresses([str(value or "")])
    if not pairs:
        return ""
    return (pairs[0][1] or "").strip()


def normalize_security_mode(value):
    mode = str(value or "").strip().lower()
    if mode in ("ssl", "tls", "ssl/tls"):
        return "ssl"
    if mode in ("starttls", "start_tls"):
        return "starttls"
    if mode in ("none", "plain", "no", "off"):
        return "none"
    return ""


def to_bool(value, default=True):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in ("0", "false", "no", "off")
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def extract_mail_body(mail):
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


def format_mail_datetime(date_header):
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


# systemSetting 中配置的用户邮箱信息
def find_send_config_for_login(login_id):
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


def format_received_label(value):
    if not value:
        return ""
    try:
        return django_timezone.localtime(value).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(value)


def resolve_owner_id_from_send_user(send_user):
    user_text = str(send_user or "").strip()
    if not user_text:
        return None

    owner = UserLogin.objects.filter(
        deleted_at__isnull=True,
    ).filter(
        Q(user_name=user_text) | Q(employee_name=user_text)
    ).first()
    if owner:
        return owner.employee_id

    try:
        employee_id = int(user_text)
    except (TypeError, ValueError):
        return None

    owner = UserLogin.objects.filter(
        employee_id=employee_id,
        deleted_at__isnull=True,
    ).first()
    return owner.employee_id if owner else None


def resolve_sendmsg_sync_targets():
    send_settings = SysSettings.objects.filter(
        name="sendmsg",
        deleted_at__isnull=True,
    ).first()
    raw_configs = send_settings.settings if send_settings else []
    if not isinstance(raw_configs, list):
        raw_configs = []

    targets = []
    skipped = []
    seen = set()
    for item in raw_configs:
        if not isinstance(item, dict):
            continue
        owner_id = resolve_owner_id_from_send_user(item.get("user"))
        if not owner_id:
            skipped.append(
                {
                    "user": str(item.get("user") or "").strip(),
                    "reason": "owner_not_found",
                }
            )
            continue
        key = (owner_id, str(item.get("email") or "").strip())
        if key in seen:
            continue
        seen.add(key)
        targets.append({"owner_id": owner_id, "send_config": item})
    return targets, skipped


# 从数据库加载我的邮件，邮件的来源：定时任务
def list_my_mails_from_db(
    owner_id,
    page=1,
    page_size=20,
    mailbox_email="",
    keyword="",
    send_date="",
):
    queryset = MyMail.objects.filter(owner_id=owner_id)
    keyword_text = str(keyword or "").strip()
    send_date_text = str(send_date or "").strip()

    if keyword_text:
        queryset = queryset.filter(subject__icontains=keyword_text)
    if send_date_text:
        target_date = django_parse_date(send_date_text)
        if target_date:
            queryset = queryset.filter(received_at__date=target_date)

    queryset = queryset.order_by("-received_at", "-id")
    total = queryset.count()
    total_pages = max((total + page_size - 1) // page_size, 1)
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * page_size
    rows = queryset[offset: offset + page_size]
    items = []
    for row in rows:
        items.append(
            {
                "id": row.id,
                "subject": row.subject or "(无标题)",
                "from": row.from_email or "",
                "from_email": row.from_email or "",
                "reply_to": "",
                "date": format_received_label(row.received_at),
                "unread": bool(row.is_unread),
                "message_id": row.id,
                "references": "",
            }
        )

    data = {"mailbox_email": str(mailbox_email or ""), "items": items}
    meta = {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }
    return data, meta


# 用户未读数
def count_unread_mails_from_db(owner_id):
    return MyMail.objects.filter(owner_id=owner_id, is_unread=True).count()


# 确保存在用户设置的邮箱信息
def ensure_send_config_for_login(login_id):
    send_config, config_error = find_send_config_for_login(login_id)
    if config_error:
        status = 404 if config_error == "User login not found" else 400
        raise MailToolError(config_error, status=status)
    if not send_config:
        raise MailToolError("No send config for current user")
    return send_config
