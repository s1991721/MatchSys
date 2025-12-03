from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
import base64
import os.path
from pathlib import Path

from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


class GmailTool:
    """
    Gmail helper based on Gmail API + OAuth2.
    """

    # 需要的 scope：读写+标记已读
    SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

    def __init__(self):
        self.service = self._build_service()

    def _build_service(self):
        creds = None
        # Use absolute paths so Django working dir changes won't break token/credentials lookup.
        base_dir = Path(__file__).resolve().parent.parent
        token_path = base_dir / "token.json"
        credentials_path = base_dir / "credentials.json"

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(token_path, self.SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not credentials_path.exists():
                    raise FileNotFoundError(f"Google OAuth client file missing: {credentials_path}")
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, self.SCOPES)
                creds = flow.run_local_server(port=0)

            with open(token_path, 'w') as token:
                token.write(creds.to_json())

        return build('gmail', 'v1', credentials=creds)

    def fetch_messages(
        self,
        query: str = "is:unread",
        limit: int = 10,
        mark_seen: bool = False,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[dict]:
        """
        从 Gmail 获取邮件列表（按时间倒序）。使用 list 拿 ID，再批量 get 详情。
        """
        service = self.service

        query_parts = [query]
        if start_date:
            query_parts.append(f'after:{start_date.strftime("%Y/%m/%d")}')
        if end_date:
            inclusive_end = end_date + timedelta(days=1)  # before: 为开区间
            query_parts.append(f'before:{inclusive_end.strftime("%Y/%m/%d")}')
        final_query = " ".join(q for q in query_parts if q)

        # 1) 先拿 ID（若有分页，按 limit 收够为止）
        ids: List[str] = []
        next_token = None
        remaining = limit
        while remaining > 0:
            resp = service.users().messages().list(
                userId='me',
                q=final_query,
                maxResults=min(remaining, 500),
                pageToken=next_token,
            ).execute()
            items = resp.get('messages', [])
            if not items:
                break
            ids.extend(item['id'] for item in items)
            remaining = limit - len(ids)
            next_token = resp.get('nextPageToken')
            if not next_token:
                break

        if not ids:
            return []

        # 2) 批量 get 详情
        details: List[dict] = []

        def handle_detail(_, response, exception):
            if exception:
                return
            details.append(response)

        batch = service.new_batch_http_request()
        for msg_id in ids:
            batch.add(
                service.users().messages().get(
                    userId='me',
                    id=msg_id,
                    format='full',
                ),
                callback=handle_detail,
            )
        batch.execute()

        messages: List[dict] = []
        for msg in details:
            headers = msg.get('payload', {}).get('headers', [])

            def get_header(name: str) -> str:
                for h in headers:
                    if h['name'].lower() == name.lower():
                        return h['value']
                return ""

            subject = get_header("Subject")
            from_ = get_header("From")
            to = get_header("To")
            date_header = get_header("Date")
            internal_ts_ms = msg.get("internalDate")  # 接收时间（毫秒）

            body_text = self._extract_text_from_gmail_msg(msg)

            # 解析 Date 头；若缺失则退化为 internalDate
            iso_ts = ""
            ts_float = float("-inf")
            try:
                if date_header:
                    dt = parsedate_to_datetime(date_header)
                    # 转为 aware（若缺 tz 则视为 UTC）
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    ts_float = dt.timestamp()
                    iso_ts = dt.astimezone(timezone.utc).isoformat()
            except Exception:
                ts_float = float("-inf")

            if iso_ts == "" and internal_ts_ms:
                try:
                    ts_float = int(internal_ts_ms) / 1000
                    iso_ts = datetime.fromtimestamp(ts_float, tz=timezone.utc).isoformat()
                except Exception:
                    ts_float = float("-inf")

            messages.append({
                "id": msg.get("id"),
                "subject": subject,
                "from": from_,
                "to": to,
                "date": iso_ts or date_header or "",  # 前端显示使用 ISO，缺失则原始
                "date_header": date_header,
                "internal_ts": ts_float,
                "body": body_text,
            })

        # 3) 按时间倒序（优先 Date 头，退化到 internalDate）
        messages.sort(
            key=lambda m: m.get("internal_ts", float("-inf")),
            reverse=True
        )

        # 4) 可选标记为已读（批量）
        if mark_seen and ids:
            mark_batch = service.new_batch_http_request()
            for msg_id in ids:
                mark_batch.add(
                    service.users().messages().modify(
                        userId='me',
                        id=msg_id,
                        body={"removeLabelIds": ["UNREAD"]}
                    )
                )
            mark_batch.execute()

        return messages

    def send_message(self, to: str, subject: str, body: str, sender: str = None):
        """
        通过 Gmail API 发送邮件
        """
        service = self.service
        message = EmailMessage()
        message.set_content(body)

        if sender:
            message['From'] = sender
        message['To'] = to
        message['Subject'] = subject

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        send_body = {'raw': encoded_message}

        sent = service.users().messages().send(
            userId='me',
            body=send_body
        ).execute()

        return sent['id']

    def _extract_text_from_gmail_msg(self, msg: dict) -> str:
        """
        从 Gmail API 返回的 message 结构中抽取文本正文（优先 text/plain）。
        """
        def _get_parts(payload):
            if 'parts' in payload:
                for part in payload['parts']:
                    mime_type = part.get('mimeType', '')
                    if mime_type.startswith('multipart/'):
                        yield from _get_parts(part)
                    else:
                        yield part
            else:
                yield payload

        payload = msg.get('payload', {})
        body_texts = []

        for part in _get_parts(payload):
            mime_type = part.get('mimeType', '')
            body = part.get('body', {})
            data = body.get('data')
            if not data:
                continue

            decoded_bytes = base64.urlsafe_b64decode(data.encode('utf-8'))
            text = decoded_bytes.decode('utf-8', errors='ignore')

            if mime_type == 'text/plain':
                body_texts.insert(0, text)  # 优先 text/plain
            else:
                body_texts.append(text)

        return "\n\n".join(body_texts).strip()
