from __future__ import print_function
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# 需要的权限范围（scope）
# 只读：'https://www.googleapis.com/auth/gmail.readonly'
# 收发+管理：'https://www.googleapis.com/auth/gmail.modify'
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def main():
    creds = None
    # gmail_token.json 用来存放用户的访问令牌和刷新令牌
    base_dir = Path(__file__).resolve().parent.parent
    token_path = base_dir / "credentials" / "gmail_token.json"
    credentials_path = base_dir / "credentials" / "gmail_credentials.json"

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # 如果没有有效凭据，走 OAuth 流程
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # 过期则自动刷新
            creds.refresh(Request())
        else:
            # 第一次执行时会走这里，弹出浏览器登录
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)

        # 保存凭据到本地，后续直接复用
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    # 简单测试：列出最近 5 封邮件的 snippet
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(userId='me', maxResults=5).execute()
    messages = results.get('messages', [])

    print("Latest messages:")
    for m in messages:
        msg = service.users().messages().get(userId='me', id=m['id']).execute()
        print(m['id'], msg.get('snippet'))

if __name__ == '__main__':
    main()
