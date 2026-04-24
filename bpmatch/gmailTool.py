import base64
import re
from datetime import date, datetime, timedelta, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


class GmailTool:
    """
    Gmail helper based on Gmail API + OAuth2.
    """

    # 需要的 scope：读写+标记已读
    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
    BATCH_LIMIT = 100  # Gmail batch API 限制：单批最多100个请求

    def __init__(self):
        self.service = self._build_service()

    def _build_service(self):
        creds = None
        # Use absolute paths so Django working dir changes won't break token/credentials lookup.
        base_dir = Path(__file__).resolve().parent.parent
        token_path = base_dir / "credentials" / "gmail_token.json"
        credentials_path = base_dir / "credentials" / "gmail_credentials.json"

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(token_path, self.SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not credentials_path.exists():
                    raise FileNotFoundError(
                        f"Google OAuth client file missing: {credentials_path}"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, self.SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(token_path, "w") as token:
                token.write(creds.to_json())

        return build("gmail", "v1", credentials=creds)

    def fetch_messages(
            self,
            query: str = "",
            page: int = 1,
            page_size: int = 20,
            mark_seen: bool = False,
            start_date: Optional[date] = None,
            end_date: Optional[date] = None,
    ) -> Tuple[List[dict], bool, int]:
        """
        从 Gmail 获取邮件列表（按时间倒序）。分页返回指定页的数据以及是否存在下一页。
        """
        service = self.service
        # 构造包含时间范围的 Gmail 查询字符串
        final_query = self._compose_query(query, start_date, end_date)

        current_token: Optional[str] = None
        resp: Optional[dict] = None

        # 逐页前进到目标页，只对目标页的 ID 拉详情
        for idx in range(page):
            resp = (
                service.users()
                .messages()
                .list(
                    userId="me",
                    q=final_query,
                    maxResults=page_size,
                    pageToken=current_token,
                )
                .execute()
            )
            current_token = resp.get("nextPageToken")
            # 已经到达最后一页但仍未到目标页，提前结束
            if current_token is None and idx < page - 1:
                break

        if not resp:
            return [], False, 0

        ids = self._extract_ids(resp)
        if not ids:
            return [], False, int(resp.get("resultSizeEstimate") or 0)

        # 批量拉取目标页邮件详情
        details = self._fetch_details(service, ids)
        page_messages = [self._parse_message(msg) for msg in details]
        has_next = resp.get("nextPageToken") is not None
        total_count = int(resp.get("resultSizeEstimate") or 0)

        # 如需标记已读，批量移除 UNREAD 标签
        if mark_seen and page_messages:
            self._mark_seen(service, page_messages)

        return page_messages, has_next, total_count

    def fetch_new_messages(
            self,
            query: str = "",
            page: int = 1,
            page_size: int = 20,
            mark_seen: bool = False,
            start_date: Optional[date] = None,
            end_date: Optional[date] = None,
    ) -> Tuple[List[dict], bool, int]:
        """
        从 Gmail 获取邮件列表（按时间倒序），仅返回 SavedMailInfo 中不存在的邮件。
        """
        service = self.service
        final_query = self._compose_query(query, start_date, end_date)

        current_token: Optional[str] = None
        resp: Optional[dict] = None

        for idx in range(page):
            resp = (
                service.users()
                .messages()
                .list(
                    userId="me",
                    q=final_query,
                    maxResults=page_size,
                    pageToken=current_token,
                )
                .execute()
            )
            current_token = resp.get("nextPageToken")
            if current_token is None and idx < page - 1:
                break

        if not resp:
            return [], False, 0

        ids = self._extract_ids(resp)
        total_count = int(resp.get("resultSizeEstimate") or 0)
        if not ids:
            return [], False, total_count

        try:
            from .models import SavedMailInfo

            saved_ids = set(
                SavedMailInfo.objects.filter(id__in=ids).values_list("id", flat=True)
            )
        except Exception:
            saved_ids = set()

        new_ids = [msg_id for msg_id in ids if msg_id not in saved_ids]
        has_next = resp.get("nextPageToken") is not None
        if not new_ids:
            return [], has_next, total_count

        details = self._fetch_details(service, new_ids)
        page_messages = [self._parse_message(msg) for msg in details]

        if mark_seen and page_messages:
            self._mark_seen(service, page_messages)

        return page_messages, has_next, total_count

    def _compose_query(
            self, query: str, start_date: Optional[date], end_date: Optional[date]
    ) -> str:
        query_parts = [query]
        if start_date:
            query_parts.append(f'after:{start_date.strftime("%Y/%m/%d")}')
        if end_date:
            inclusive_end = end_date + timedelta(days=1)  # before: 为开区间
            query_parts.append(f'before:{inclusive_end.strftime("%Y/%m/%d")}')
        return " ".join(q for q in query_parts if q)

    def _extract_ids(self, resp: dict) -> List[str]:
        return [item.get("id") for item in resp.get("messages", []) if item.get("id")]

    def _fetch_details(self, service, ids: List[str]) -> List[dict]:
        detail_items: List[dict] = []

        def handle_detail(_, response, exception):
            if exception:
                return
            detail_items.append(response)

        for start in range(0, len(ids), self.BATCH_LIMIT):
            batch = service.new_batch_http_request()
            for msg_id in ids[start: start + self.BATCH_LIMIT]:
                batch.add(
                    service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=msg_id,
                        format="full",
                    ),
                    callback=handle_detail,
                )
            batch.execute()
        return detail_items

    def _parse_message(self, msg: dict) -> dict:
        headers = msg.get("payload", {}).get("headers", [])

        header_map = {}
        for h in headers:
            name = h.get("name")
            val = h.get("value")
            if not name or val is None:
                continue
            header_map.setdefault(name.lower(), []).append(val)

        def get_header(name: str) -> str:
            vals = header_map.get(name.lower())
            return vals[0] if vals else ""

        def get_header_list(name: str) -> List[str]:
            return header_map.get(name.lower(), [])

        subject = get_header("Subject")
        from_ = get_header("From")
        to = get_header("To")
        date_header = get_header("Date")
        message_id_header = get_header("Message-ID")
        references_header = get_header("References")
        internal_ts_ms = msg.get("internalDate")  # 接收时间（毫秒）
        received_headers = get_header_list("Received")

        body_text = self._extract_text_from_gmail_msg(msg)
        attachments = self._extract_attachments_from_gmail_msg(msg)

        iso_ts, ts_float = self._parse_dates(
            received_headers, date_header, internal_ts_ms
        )

        return {
            "id": msg.get("id"),
            "subject": subject,
            "from": from_,
            "to": to,
            "date": iso_ts or date_header or "",  # 前端显示使用 ISO，缺失则原始
            "date_header": date_header,
            "thread_id": msg.get("threadId"),
            "message_id_header": message_id_header,
            "references_header": references_header,
            "internal_ts": ts_float,
            "body": body_text,
            "files": attachments,
        }

    def fetch_attachment(self, message_id: str, attachment_id: str) -> bytes:
        if not message_id or not attachment_id:
            raise ValueError("message_id and attachment_id are required")
        payload = (
            self.service.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=message_id, id=attachment_id)
            .execute()
        )
        data = str(payload.get("data") or "").strip()
        if not data:
            return b""
        return self._decode_base64url(data)

    def _parse_dates(
            self,
            received_headers: List[str],
            date_header: str,
            internal_ts_ms: Optional[str],
    ) -> Tuple[str, float]:
        iso_ts = ""
        ts_float = float("-inf")
        try:
            received_dt = self._parse_received_header(received_headers)

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

        return iso_ts, ts_float

    def _parse_received_header(self, received_headers: List[str]) -> Optional[datetime]:
        if not received_headers:
            return None

        # Gmail 的 Received 会有多个，取第一条（最新一跳）末尾分号后的时间
        for raw in received_headers:
            if ";" not in raw:
                continue
            _, _, after = raw.rpartition(";")
            candidate = after.strip()
            if not candidate:
                continue
            try:
                parsed = parsedate_to_datetime(candidate)
                if parsed:
                    return parsed
            except Exception:
                continue

        try:
            return parsedate_to_datetime(received_headers[0])
        except Exception:
            return None

    def _mark_seen(self, service, page_messages: List[dict]):
        ids_to_mark = [m.get("id") for m in page_messages if m.get("id")]
        for start in range(0, len(ids_to_mark), self.BATCH_LIMIT):
            mark_batch = service.new_batch_http_request()
            for msg_id in ids_to_mark[start: start + self.BATCH_LIMIT]:
                mark_batch.add(
                    service.users()
                    .messages()
                    .modify(userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]})
                )
            mark_batch.execute()

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
            if "parts" in payload:
                for part in payload["parts"]:
                    mime_type = part.get("mimeType", "")
                    if mime_type.startswith("multipart/"):
                        yield from _get_parts(part)
                    else:
                        yield part
            else:
                yield payload

        payload = msg.get("payload", {})
        plain_text = ""
        html_text = ""

        for part in _get_parts(payload):
            mime_type = part.get("mimeType", "")
            filename = part.get("filename", "")
            if filename:
                continue

            body = part.get("body", {})
            data = body.get("data")
            if not data:
                continue

            decoded_bytes = base64.urlsafe_b64decode(data.encode("utf-8"))
            text = decoded_bytes.decode("utf-8", errors="ignore")

            if mime_type == "text/plain":
                if not plain_text:
                    plain_text = text
            elif mime_type == "text/html":
                if not html_text:
                    html_text = html_to_text(text)

        return (plain_text or html_text).strip()

    def _extract_attachments_from_gmail_msg(self, msg: dict) -> List[Dict[str, object]]:
        attachments: List[Dict[str, object]] = []
        payload = msg.get("payload", {}) or {}
        message_id = str(msg.get("id") or "").strip()

        def walk_parts(part):
            if not isinstance(part, dict):
                return
            children = part.get("parts", []) or []
            if not children:
                yield part
                return
            for child in children:
                if isinstance(child, dict) and str(child.get("mimeType") or "").startswith("multipart/"):
                    yield from walk_parts(child)
                else:
                    yield child

        for part in walk_parts(payload):
            filename = self._decode_header_value(part.get("filename"))
            body = part.get("body", {}) or {}
            attachment_id = str(body.get("attachmentId") or "").strip()
            if not filename and not attachment_id:
                continue
            headers = part.get("headers", []) or []
            content_id = ""
            disposition = ""
            for header in headers:
                if not isinstance(header, dict):
                    continue
                name = str(header.get("name") or "").strip().lower()
                value = self._decode_header_value(header.get("value"))
                if name == "content-id":
                    content_id = value
                elif name == "content-disposition":
                    disposition = value
            mime_type = str(part.get("mimeType") or "application/octet-stream").strip() or "application/octet-stream"
            attachments.append(
                {
                    "filename": filename or "attachment",
                    "mime_type": mime_type,
                    "size": int(body.get("size") or 0),
                    "part_id": str(part.get("partId") or "").strip(),
                    "attachment_id": attachment_id,
                    "message_id": message_id,
                    "inline": self._is_inline_part(disposition, content_id),
                }
            )
        return attachments

    def _decode_header_value(self, value) -> str:
        raw = str(value or "")
        if not raw:
            return ""
        parts = []
        for chunk, encoding in decode_header(raw):
            if isinstance(chunk, bytes):
                enc = encoding or "utf-8"
                try:
                    parts.append(chunk.decode(enc, errors="replace"))
                except Exception:
                    parts.append(chunk.decode("utf-8", errors="replace"))
            else:
                parts.append(str(chunk))
        return "".join(parts).strip()

    def _is_inline_part(self, disposition: str, content_id: str) -> bool:
        disposition_text = str(disposition or "").strip().lower()
        if "inline" in disposition_text:
            return True
        return bool(str(content_id or "").strip())

    def _decode_base64url(self, value: str) -> bytes:
        normalized = str(value or "").strip()
        if not normalized:
            return b""
        padding = (-len(normalized)) % 4
        if padding:
            normalized += "=" * padding
        return base64.urlsafe_b64decode(normalized.encode("utf-8"))


# ---------------------------
#  主运行入口
# ---------------------------
if __name__ == "__main__":
    print("\n=== Running Translation Tests ===\n")
    g = GmailTool()
    g.fetch_messages(page=2)
    print("=== All tests completed ===")
