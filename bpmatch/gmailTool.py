from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple
import re
import base64
import os.path
from pathlib import Path
from html import unescape
from html.parser import HTMLParser

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
    BATCH_LIMIT = 100  # Gmail batch API 限制：单批最多100个请求

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
        page: int = 1,
        page_size: int = 20,
        mark_seen: bool = False,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Tuple[List[dict], bool]:
        """
        从 Gmail 获取邮件列表（按时间倒序）。分页返回指定页的数据以及是否存在下一页。
        """
        service = self.service

        query_parts = [query]
        if start_date:
            query_parts.append(f'after:{start_date.strftime("%Y/%m/%d")}')
        if end_date:
            inclusive_end = end_date + timedelta(days=1)  # before: 为开区间
            query_parts.append(f'before:{inclusive_end.strftime("%Y/%m/%d")}')
        final_query = " ".join(q for q in query_parts if q)

        # Gmail API 的 maxResults 上限为 500；这里固定分页大小（默认20）
        page = max(int(page or 1), 1)
        page_size = max(1, min(int(page_size or 1), 500))
        target_count = page * page_size + 1  # 多取 1 条用于判断是否有下一页

        # 用于缓存结果与分页标记
        messages: List[dict] = []
        next_page_token: Optional[str] = None
        current_token: Optional[str] = None

        def in_range(ts: Optional[float]) -> bool:
            if not (start_date or end_date):
                return True
            if ts is None or ts == float("-inf"):
                return False
            try:
                local_tz = datetime.now().astimezone().tzinfo
                local_dt = datetime.fromtimestamp(ts, tz=local_tz)
                local_d = local_dt.date()
            except Exception:
                return False
            if start_date and local_d < start_date:
                return False
            if end_date and local_d > end_date:
                return False
            return True

        def fetch_details(ids: List[str]) -> List[dict]:
            detail_items: List[dict] = []

            def handle_detail(_, response, exception):
                if exception:
                    return
                detail_items.append(response)

            for start in range(0, len(ids), self.BATCH_LIMIT):
                batch = service.new_batch_http_request()
                for msg_id in ids[start:start + self.BATCH_LIMIT]:
                    batch.add(
                        service.users().messages().get(
                            userId='me',
                            id=msg_id,
                            format='full',
                        ),
                        callback=handle_detail,
                    )
                batch.execute()
            return detail_items

        while len(messages) < target_count:
            resp = service.users().messages().list(
                userId='me',
                q=final_query,
                maxResults=page_size,
                pageToken=current_token,
            ).execute()

            ids = [item.get('id') for item in resp.get('messages', []) if item.get('id')]
            if not ids:
                current_token = resp.get('nextPageToken')
                next_page_token = current_token
                if not current_token:
                    break
                continue

            details = fetch_details(ids)

            for msg in details:
                headers = msg.get('payload', {}).get('headers', [])

                def get_header(name: str) -> str:
                    for h in headers:
                        if h['name'].lower() == name.lower():
                            return h['value']
                    return ""

                def get_header_list(name: str) -> List[str]:
                    return [h['value'] for h in headers if h.get('name', '').lower() == name.lower()]

                subject = get_header("Subject")
                from_ = get_header("From")
                to = get_header("To")
                date_header = get_header("Date")
                internal_ts_ms = msg.get("internalDate")  # 接收时间（毫秒）
                received_headers = get_header_list("Received")

                body_text = self._extract_text_from_gmail_msg(msg)

                # 解析 Date 头；若缺失则退化为 internalDate
                iso_ts = ""
                ts_float = float("-inf")
                try:
                    received_dt = None
                    # Gmail 的 Received 会有多个，取第一条（最新一跳）末尾分号后的时间
                    if received_headers:
                        for raw in received_headers:
                            if ";" not in raw:
                                continue
                            _, _, after = raw.rpartition(";")
                            candidate = after.strip()
                            if not candidate:
                                continue
                            try:
                                received_dt = parsedate_to_datetime(candidate)
                                if received_dt:
                                    break
                            except Exception:
                                continue
                        if not received_dt:
                            try:
                                received_dt = parsedate_to_datetime(received_headers[0])
                            except Exception:
                                received_dt = None

                    if not received_dt and date_header:
                        try:
                            received_dt = parsedate_to_datetime(date_header)
                        except Exception:
                            received_dt = None

                    if received_dt:
                        if received_dt.tzinfo is None:
                            received_dt = received_dt.replace(tzinfo=timezone.utc)
                        ts_float = received_dt.timestamp()
                        iso_ts = received_dt.astimezone(timezone.utc).isoformat()
                except Exception:
                    ts_float = float("-inf")

                if iso_ts == "" and internal_ts_ms:
                    try:
                        ts_float = int(internal_ts_ms) / 1000
                        iso_ts = datetime.fromtimestamp(ts_float, tz=timezone.utc).isoformat()
                    except Exception:
                        ts_float = float("-inf")

                message = {
                    "id": msg.get("id"),
                    "subject": subject,
                    "from": from_,
                    "to": to,
                    "date": iso_ts or date_header or "",  # 前端显示使用 ISO，缺失则原始
                    "date_header": date_header,
                    "internal_ts": ts_float,
                    "body": body_text,
                }

                if in_range(message.get("internal_ts")):
                    messages.append(message)

            current_token = resp.get('nextPageToken')
            next_page_token = current_token
            if not current_token:
                break

        # 3) 按时间倒序（优先 Date 头，退化到 internalDate）
        messages.sort(
            key=lambda m: m.get("internal_ts", float("-inf")),
            reverse=True
        )

        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        page_messages = messages[start_index:end_index]
        has_next = len(messages) > end_index or (next_page_token is not None and len(messages) > start_index)

        # 4) 可选标记为已读（批量）
        if mark_seen and page_messages:
            ids_to_mark = [m.get("id") for m in page_messages if m.get("id")]
            for start in range(0, len(ids_to_mark), self.BATCH_LIMIT):
                mark_batch = service.new_batch_http_request()
                for msg_id in ids_to_mark[start:start + self.BATCH_LIMIT]:
                    mark_batch.add(
                        service.users().messages().modify(
                            userId='me',
                            id=msg_id,
                            body={"removeLabelIds": ["UNREAD"]}
                        )
                    )
                mark_batch.execute()

        return page_messages, has_next

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

        class _HTMLStripper(HTMLParser):
            def __init__(self):
                super().__init__()
                self.parts: List[str] = []

            def handle_starttag(self, tag, attrs):
                if tag in ("br", "p", "div", "li", "tr"):
                    self.parts.append("\n")

            def handle_endtag(self, tag):
                if tag in ("p", "div", "li", "tr", "table"):
                    self.parts.append("\n")

            def handle_data(self, data):
                if data:
                    self.parts.append(data)

            def get_text(self):
                text = "".join(self.parts)
                # 去掉过多空行
                text = re.sub(r"\n{3,}", "\n\n", text)
                # 行尾空白
                text = "\n".join(line.rstrip() for line in text.splitlines())
                return text.strip()

        def html_to_text(html_body: str) -> str:
            stripper = _HTMLStripper()
            try:
                stripper.feed(html_body)
                stripper.close()
            except Exception:
                return html_body
            text = stripper.get_text()
            return unescape(text)

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
                if mime_type == 'text/html':
                    body_texts.append(html_to_text(text))
                else:
                    body_texts.append(text)

        return "\n\n".join(body_texts).strip()
