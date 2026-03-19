from typing import Any, Dict, List, Optional

import requests

# ---------------------------- LINE 配置项 ----------------------------
# sys_settings 中的 section 名（新增系统设置项目：LINE通知）
LINE_SETTING_SECTION = "line-notify"
# sys_settings.settings 的字段名
LINE_SETTING_KEY_ACCESS_TOKEN = "channel_access_token"
LINE_SETTING_KEY_TO_USER_ID = "to_user_id"

# API 基础地址（一般无需修改）
LINE_API_BASE_URL = "https://api.line.me"
LINE_REQUEST_TIMEOUT_SECONDS = 10


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
        messages: List[Dict[str, Any]],
        user_id: Optional[str] = None,
        channel_access_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    使用 LINE Messaging API Push Message 发送消息。
    """
    if not isinstance(messages, list) or not messages:
        raise LineSendError("messages must be a non-empty list")

    settings = _get_line_settings_from_db()
    target_id = (user_id or settings.get(LINE_SETTING_KEY_TO_USER_ID) or "").strip()
    token = (channel_access_token or settings.get(LINE_SETTING_KEY_ACCESS_TOKEN) or "").strip()
    if not target_id:
        raise LineSendError("Missing LINE target id")
    if not token:
        raise LineSendError("Missing LINE channel access token")

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


def send_line_text(
        text: str,
        user_id: Optional[str] = None,
        channel_access_token: Optional[str] = None,
) -> Dict[str, Any]:
    if not str(text or "").strip():
        raise LineSendError("text is empty")

    return send_line_messages(
        messages=[{"type": "text", "text": str(text)}],
        user_id=user_id,
        channel_access_token=channel_access_token,
    )


def test_line_connection(
    user_id: Optional[str] = None,
    channel_access_token: Optional[str] = None,
):
    return send_line_text(
        "LINE connection test",
        user_id=user_id,
        channel_access_token=channel_access_token,
    )
