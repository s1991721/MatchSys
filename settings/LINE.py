from typing import Any, Dict, List

import requests

# ---------------------------- LINE 配置项 ----------------------------
# sys_settings 中的 section 名（新增系统设置项目：LINE通知）
LINE_SETTING_SECTION = "line-notify"
# sys_settings.settings 的字段名
LINE_SETTING_KEY_ACCESS_TOKEN = "channel_access_token"
LINE_SETTING_KEY_TO_USER_ID = "to_user_id"
LINE_SETTING_KEY_NOTIFY_DISABLED = "notification_disabled"
LINE_SETTING_KEY_REQUEST_TIMEOUT = "timeout_seconds"

# API 基础地址（一般无需修改）
LINE_API_BASE_URL = "https://api.line.me"


class LineSendError(Exception):
    """LINE 送信错误。"""


def _get_line_settings_from_db() -> Dict[str, Any]:
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


def _line_headers(channel_access_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {channel_access_token}",
        "Content-Type": "application/json",
    }


def send_line_messages(
        messages: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    使用 LINE Messaging API Push Message 发送消息。
    """
    if not isinstance(messages, list) or not messages:
        raise LineSendError("messages must be a non-empty list")

    settings = _get_line_settings_from_db()
    target_id = settings.get(LINE_SETTING_KEY_TO_USER_ID)
    token = settings.get(LINE_SETTING_KEY_ACCESS_TOKEN)
    notify_disabled = settings.get(LINE_SETTING_KEY_NOTIFY_DISABLED)
    request_timeout = settings.get(LINE_SETTING_KEY_REQUEST_TIMEOUT)

    url = f"{LINE_API_BASE_URL.rstrip('/')}/v2/bot/message/push"
    payload = {
        "to": target_id,
        "messages": messages,
        "notificationDisabled": notify_disabled,
    }

    try:
        response = requests.post(
            url,
            headers=_line_headers(token),
            json=payload,
            timeout=request_timeout,
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


def send_line_text(
        text: str
) -> Dict[str, Any]:
    if not str(text or "").strip():
        raise LineSendError("text is empty")

    return send_line_messages(messages=[{"type": "text", "text": str(text)}])


def test_line_connection():
    send_line_text("LINE connection test")