from datetime import date, timedelta
from typing import List, Optional
import base64
import os.path

from email.message import EmailMessage
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
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', self.SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # 一般不会再走到这里，除非你删了 token.json 或换了 scope
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', self.SCOPES)
                creds = flow.run_local_server(port=0)

            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        service = build('gmail', 'v1', credentials=creds)
        return service

    def fetch_messages(
        self,
        query: str = "is:unread",
        limit: int = 10,
        mark_seen: bool = False,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[dict]:
        """
        从 Gmail 获取邮件列表。

        :param query: Gmail 搜索语法，例如 "is:unread", "from:xxx", "label:INBOX"
        :param limit: 最多返回几封邮件
        :param mark_seen: 是否把取到的邮件标记为已读
        :param start_date: 起始日期（含），格式 date
        :param end_date: 结束日期（含），格式 date
        :return: list[dict]，结构与原来尽量保持相似
        """
        service = self.service

        query_parts = [query]
        if start_date:
            query_parts.append(f'after:{start_date.strftime("%Y/%m/%d")}')
        if end_date:
            # Gmail before: 是严格早于给定日期，所以要 +1 天来实现“含 end_date”。
            inclusive_end = end_date + timedelta(days=1)
            query_parts.append(f'before:{inclusive_end.strftime("%Y/%m/%d")}')
        final_query = " ".join(q for q in query_parts if q)

        # 列出邮件 ID
        response = service.users().messages().list(
            userId='me',
            q=final_query,
            maxResults=limit,
        ).execute()

        messages = []
        msg_items = response.get('messages', [])
        if not msg_items:
            return messages

        for item in msg_items:
            msg_id = item['id']
            msg = service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full',   # full 可以拿到 headers + body
            ).execute()

            headers = msg.get('payload', {}).get('headers', [])

            def get_header(name: str) -> str:
                for h in headers:
                    if h['name'].lower() == name.lower():
                        return h['value']
                return ""

            subject = get_header("Subject")
            from_ = get_header("From")
            to = get_header("To")
            date = get_header("Date")

            body_text = self._extract_text_from_gmail_msg(msg)

            messages.append({
                "id": msg_id,
                "subject": subject,
                "from": from_,
                "to": to,
                "date": date,
                "body": body_text,
            })

            # 标记为已读 -> 移除 UNREAD 标签
            if mark_seen:
                service.users().messages().modify(
                    userId='me',
                    id=msg_id,
                    body={"removeLabelIds": ["UNREAD"]}
                ).execute()

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

        # Gmail API 要求 base64url 编码的 raw 字符串
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
                    # 递归处理嵌套结构
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

            # Gmail 用 base64url 编码，要进行替换
            decoded_bytes = base64.urlsafe_b64decode(data.encode('utf-8'))
            text = decoded_bytes.decode('utf-8', errors='ignore')

            # 优先 text/plain，如果只有 html 也先收集起来
            if mime_type == 'text/plain':
                body_texts.insert(0, text)  # 放到前面
            else:
                body_texts.append(text)

        # 简单合并多个 part
        return "\n\n".join(body_texts).strip()

if __name__ == "__main__":
    tool = GmailTool()

    # 1. 收邮件测试
#     msgs = tool.fetch_messages(
#         limit=1,
#         query="",
#         start_date=date(2025, 11, 27),
#         end_date=date(2025, 11, 28),
# )
#     for m in msgs:
#         print(m["subject"], m["from"])
#         print(m["body"])

    # 2. 发邮件测试
    tool.send_message(
        to="jef4267@gmail.com",
        subject="Gmail API 测试",
        body="这是一封来自 Gmail API 的测试邮件。",
    )
