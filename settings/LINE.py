import base64
import hashlib
import hmac
from typing import Any, Dict, List, Optional

import requests

# ---------------------------- LINE 配置项 ----------------------------
# sys_settings 中的 section 名（新增系统设置项目：LINE通知）
LINE_SETTING_SECTION = "line-notify"
# sys_settings.settings 的字段名
LINE_SETTING_KEY_ACCESS_TOKEN = "channel_access_token"
LINE_SETTING_KEY_TO_USER_ID = "to_user_id"
LINE_SETTING_KEY_CHANNEL_SECRET = "channel_secret"

# API 基础地址（一般无需修改）
LINE_API_BASE_URL = "https://api.line.me"
LINE_DATA_API_BASE_URL = "https://api-data.line.me"
LINE_REQUEST_TIMEOUT_SECONDS = 10


class LineSendError(Exception):
    """LINE 送信错误。"""


# 内存缓存LINE 配置
_LINE_SETTINGS_CACHE: Optional[Dict[str, Any]] = None


# 缓存失效
def invalidate_line_notify_filter_cache():
    """
    line-notify 配置更新后，清理相关缓存。
    """
    global _LINE_SETTINGS_CACHE
    _LINE_SETTINGS_CACHE = None


# 加载DB数据到缓存
def _load_line_settings_from_db() -> Dict[str, Any]:
    from settings.models import SysSettings
    try:
        row = SysSettings.objects.filter(
            name=LINE_SETTING_SECTION,
            deleted_at__isnull=True,
        ).first()
        if row and isinstance(row.settings, dict):
            return row.settings
    except Exception:
        return {}
    return {}


# 从缓存获取配置
def _get_line_settings_from_cache() -> Dict[str, Any]:
    global _LINE_SETTINGS_CACHE
    if _LINE_SETTINGS_CACHE is None:
        _LINE_SETTINGS_CACHE = _load_line_settings_from_db()
    return dict(_LINE_SETTINGS_CACHE)


# 获取过滤配置
def get_line_notify_filter() -> Dict[str, Any]:
    global _LINE_SETTINGS_CACHE
    if _LINE_SETTINGS_CACHE is None:
        _get_line_settings_from_cache()

    return {
        "nationality": _LINE_SETTINGS_CACHE.get("nationality", -1),
        "skills": list(_LINE_SETTINGS_CACHE.get("skills", [])),
    }


# 构造请求头
def _line_headers(channel_access_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {channel_access_token}",
        "Content-Type": "application/json",
    }


# 获取LINE token
def get_line_channel_access_token() -> str:
    settings_payload = _get_line_settings_from_cache()
    return str(settings_payload.get(LINE_SETTING_KEY_ACCESS_TOKEN) or "").strip()


# 获取LINE secret
def get_line_channel_secret() -> str:
    settings_payload = _get_line_settings_from_cache()
    return str(settings_payload.get(LINE_SETTING_KEY_CHANNEL_SECRET) or "").strip()


# 校验获取到的信息签名
def verify_line_signature(
        request_body: bytes,
        signature: str,
        channel_secret: str,
) -> bool:
    secret = channel_secret
    if not secret or not signature:
        return False
    digest = hmac.new(
        secret.encode("utf-8"),
        request_body or b"",
        hashlib.sha256,
    ).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, str(signature).strip())


# 获取LINE发送过来的消息
def get_line_message_content(
        message_id: str,
) -> Dict[str, Any]:
    mid = str(message_id or "").strip()
    if not mid:
        raise LineSendError("message_id is empty")

    token = get_line_channel_access_token()

    url = f"{LINE_DATA_API_BASE_URL.rstrip('/')}/v2/bot/message/{mid}/content"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=LINE_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise LineSendError(f"LINE content request failed: {exc}") from exc

    if response.status_code >= 400:
        detail: Any = response.text
        raise LineSendError(
            f"LINE content fetch failed [{response.status_code}] message_id={mid}: {detail}"
        )

    return {
        "message_id": mid,
        "content_type": response.headers.get("Content-Type") or "",
        "content": response.content,
        "content_length": len(response.content or b""),
    }


# LINE 送信
def send_line_messages(
        messages: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    使用 LINE Messaging API Push Message 发送消息。
    """
    if not isinstance(messages, list) or not messages:
        raise LineSendError("messages must be a non-empty list")

    settings_payload = _get_line_settings_from_cache()

    target_id = settings_payload.get(LINE_SETTING_KEY_TO_USER_ID)
    if not target_id:
        raise LineSendError("Missing LINE target id")

    token = get_line_channel_access_token()
    if not token:
        raise LineSendError("Missing LINE channel access token")

    return real_send_line_messages(messages, token, target_id)


def send_line_text(
        text: str
) -> Dict[str, Any]:
    if not str(text or "").strip():
        raise LineSendError("text is empty")

    return send_line_messages(
        messages=[{"type": "text", "text": str(text)}],
    )


# LINE回复信息
def reply_line_messages(
        reply_token: str,
        messages: List[Dict[str, Any]]
) -> Dict[str, Any]:
    if not isinstance(messages, list) or not messages:
        raise LineSendError("messages must be a non-empty list")

    rtoken = str(reply_token or "").strip()
    if not rtoken:
        raise LineSendError("reply_token is empty")

    token = get_line_channel_access_token()
    if not token:
        raise LineSendError("Missing LINE channel access token")

    url = f"{LINE_API_BASE_URL.rstrip('/')}/v2/bot/message/reply"
    payload = {
        "replyToken": rtoken,
        "messages": messages,
    }

    try:
        response = requests.post(
            url,
            headers=_line_headers(token),
            json=payload,
            timeout=LINE_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise LineSendError(f"LINE reply request failed: {exc}") from exc

    if response.status_code >= 400:
        detail: Any = ""
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise LineSendError(f"LINE reply failed [{response.status_code}]: {detail}")

    return {
        "message": "LINE reply sent",
        "status_code": response.status_code,
    }


# 回信
def reply_line_text(reply_token: str, text: str) -> Dict[str, Any]:
    if not str(text or "").strip():
        raise LineSendError("text is empty")
    return reply_line_messages(
        reply_token=reply_token,
        messages=[{"type": "text", "text": str(text)}],
    )


# 测试链接
def test_line_connection(channel_access_token: str, to_user_id: str):
    messages = [{"type": "text", "text": str("LINE connection test")}]
    return real_send_line_messages(messages, channel_access_token, to_user_id)


# 真送信
def real_send_line_messages(messages: List[Dict[str, Any]], token: str, target_id: str) -> Dict[str, Any]:
    url = f"{LINE_API_BASE_URL.rstrip('/')}/v2/bot/message/push"
    payload = {
        "to": target_id,
        "messages": messages,
        "notificationDisabled": False,
    }

    try:
        response = requests.post(
            url,
            headers=_line_headers(token),
            json=payload,
            timeout=LINE_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise LineSendError(f"LINE request failed: {exc}") from exc

    if response.status_code >= 400:
        detail: Any = ""
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise LineSendError(f"LINE send failed [{response.status_code}]: {detail}")

    return {
        "message": "LINE message sent",
        "status_code": response.status_code,
        "target_id": target_id,
    }
