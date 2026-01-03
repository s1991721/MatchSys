from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple
import re
import base64
import os.path
from pathlib import Path
from html import unescape
from html.parser import HTMLParser
import json

from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from django.utils import timezone as dj_timezone
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
            for msg_id in ids[start : start + self.BATCH_LIMIT]:
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
        }

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
            for msg_id in ids_to_mark[start : start + self.BATCH_LIMIT]:
                mark_batch.add(
                    service.users()
                    .messages()
                    .modify(userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]})
                )
            mark_batch.execute()

    def send_message(
        self,
        to: str,
        subject: str,
        body: str,
        sender: str = None,
        cc: str = None,
        attachments: Optional[List[dict]] = None,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
        mail_type: Optional[int] = None,
    ):
        """
        通过 Gmail API 发送邮件，支持抄送、附件和回复现有线程。
        attachments: List[{"filename": str, "content_type": str, "content": bytes}]
        thread_id/in_reply_to/references 用于保持 Gmail 会话上下文。
        """
        service = self.service
        message = EmailMessage()
        message.set_content(body)

        if sender:
            message["From"] = sender
        message["To"] = to
        if cc:
            message["Cc"] = cc
        message["Subject"] = subject
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
        ref_to_use = references or ""
        if not ref_to_use and in_reply_to:
            ref_to_use = in_reply_to
        if ref_to_use:
            message["References"] = ref_to_use

        # 附件处理
        for att in attachments or []:
            fname = att.get("filename") or "attachment"
            ctype = att.get("content_type") or "application/octet-stream"
            raw_bytes = att.get("content") or b""
            if isinstance(raw_bytes, str):
                try:
                    raw_bytes = base64.b64decode(raw_bytes)
                except Exception:
                    raw_bytes = raw_bytes.encode("utf-8", errors="ignore")
            try:
                maintype, subtype = ctype.split("/", 1)
            except ValueError:
                maintype, subtype = "application", "octet-stream"
            message.add_attachment(raw_bytes, maintype=maintype, subtype=subtype, filename=fname)

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        send_body = {"raw": encoded_message}
        if thread_id:
            send_body["threadId"] = thread_id

        sent = service.users().messages().send(userId="me", body=send_body).execute()

        message_id = sent.get("id")
        sent_at = self._extract_sent_time(sent)
        self._persist_sent_log(
            message_id=message_id,
            sent_at=sent_at,
            to=to,
            cc=cc,
            subject=subject,
            body=body,
            attachments=attachments,
            mail_type=mail_type,
        )

        return message_id

    def _extract_sent_time(self, sent_response: dict) -> datetime:
        """
        从 Gmail send API 的返回中提取发送时间。若返回不包含 internalDate，则使用当前时间。
        """
        internal_ms = sent_response.get("internalDate")
        if internal_ms:
            try:
                ts = int(internal_ms) / 1000
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                pass
        return dj_timezone.now()

    def _persist_sent_log(
        self,
        message_id: Optional[str],
        sent_at: datetime,
        to: Optional[str],
        cc: Optional[str],
        subject: Optional[str],
        body: Optional[str],
        attachments: Optional[List[dict]],
        mail_type: Optional[int],
    ):
        """
        将发送结果写入数据库；若 ORM 不可用或写入失败，不影响主流程。
        """
        if not message_id:
            return

        try:
            from .models import SentEmailLog
        except Exception:
            return

        try:
            filenames = []
            for att in attachments or []:
                if not isinstance(att, dict):
                    continue
                fname = att.get("filename")
                if fname:
                    filenames.append(str(fname))

            defaults = {
                "sent_at": sent_at,
                "to": to or "",
                "cc": cc or "",
                "subject": subject or "",
                "body": body or "",
                "attachments": json.dumps(filenames, ensure_ascii=False),
            }
            if mail_type is not None:
                defaults["mail_type"] = mail_type

            SentEmailLog.objects.update_or_create(
                message_id=message_id,
                defaults=defaults,
            )
        except Exception as exc:
            print(f"[gmail] 保存发送记录失败: {exc}")

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
        body_texts = []

        for part in _get_parts(payload):
            mime_type = part.get("mimeType", "")
            body = part.get("body", {})
            data = body.get("data")
            if not data:
                continue

            decoded_bytes = base64.urlsafe_b64decode(data.encode("utf-8"))
            text = decoded_bytes.decode("utf-8", errors="ignore")

            if mime_type == "text/plain":
                body_texts.insert(0, text)  # 优先 text/plain
            else:
                if mime_type == "text/html":
                    body_texts.append(html_to_text(text))
                else:
                    body_texts.append(text)

        return "\n\n".join(body_texts).strip()


# ---------------------------
#  主运行入口
# ---------------------------
if __name__ == "__main__":
    print("\n=== Running Translation Tests ===\n")
    g = GmailTool()
    g.fetch_messages(page=2)
    print("=== All tests completed ===")
