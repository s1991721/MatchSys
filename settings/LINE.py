from typing import Any, Dict, List, Optional

import requests

# ---------------------------- LINE 必填参数（请按需配置） ----------------------------
# 1) LINE Messaging API Channel Access Token（长效 token）
#    来源：LINE Developers Console -> Messaging API -> Channel access token
LINE_CHANNEL_ACCESS_TOKEN = "EuICtiyImO5foYbVTFKsCIF6kYeZrJOug42fYc1w0vGlj2eucWsXSiNTHwDcJjRJeqTABgAigmnYloZlHXuCw61rcEwGT8nYnx4Or49WkwaOp1nPttOKHkPtbiCpo0XJSNGSl9NAQFCYQ9a/1sKwLAdB04t89/1O/w1cDnyilFU="
# 2) 送信目标 ID（用户 / 群组 / 聊天室 三选一或都留空，调用时传入）
#    个人 userId 获取方式：先让用户加 bot 好友并发消息，再从 webhook 事件取 source.userId
LINE_DEFAULT_TO_USER_ID = "U3c75576f759fc68aff9c2cb2c3de3202"
# 3) API 基础地址（一般无需修改）
LINE_API_BASE_URL = "https://api.line.me"
# 4) 请求超时时间（秒）
LINE_TIMEOUT_SECONDS = 10
# 5) 是否关闭推送通知（True=静默发送，False=正常通知）
LINE_NOTIFICATION_DISABLED = "False"


class LineSendError(Exception):
    """LINE 送信错误。"""


def _line_headers(channel_access_token: str) -> Dict[str, str]:
    # LINE Push API 使用 Bearer Token 鉴权
    if not channel_access_token:
        raise LineSendError("Missing LINE channel access token")
    return {
        "Authorization": f"Bearer {channel_access_token}",
        "Content-Type": "application/json",
    }


def send_line_messages(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    使用 LINE Messaging API Push Message 发送消息。
    messages 格式示例:
    [
        {"type": "text", "text": "你好，LINE"},
    ]
    """
    if not isinstance(messages, list) or not messages:
        raise LineSendError("messages must be a non-empty list")

    target_id = LINE_DEFAULT_TO_USER_ID
    token = LINE_CHANNEL_ACCESS_TOKEN
    notify_disabled = LINE_NOTIFICATION_DISABLED
    request_timeout = LINE_TIMEOUT_SECONDS

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
        detail = ""
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


def send_line_text(text: str) -> Dict[str, Any]:
    # 常用快捷方法：包装为单条 text message
    if not str(text or "").strip():
        raise LineSendError("text is empty")
    return send_line_messages(
        messages=[{"type": "text", "text": str(text)}]
    )
