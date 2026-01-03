from __future__ import print_function
from pathlib import Path
from typing import Dict, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# 需要的权限范围（scope）
# 只读：'https://www.googleapis.com/auth/gmail.readonly'
# 收发+管理：'https://www.googleapis.com/auth/gmail.modify'
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# 获取认证文件地址
def _get_paths():
    base_dir = Path(__file__).resolve().parent.parent
    token_path = base_dir / "credentials" / "gmail_token.json"
    credentials_path = base_dir / "credentials" / "gmail_credentials.json"
    return base_dir, token_path, credentials_path


# 写入token
def _save_token(token_path: Path, creds: Credentials) -> None:
    token_path.write_text(creds.to_json(), encoding="utf-8")


# 加载认证内容
def load_credentials() -> Credentials:
    creds = None
    _, token_path, credentials_path = _get_paths()

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(token_path, creds)
        return creds

    if creds and creds.valid:
        return creds

    if not credentials_path.exists():
        raise FileNotFoundError(f"Gmail 凭据文件缺失: {credentials_path}")

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(token_path, creds)
    return creds

# 测试Gmail连接
def test_connection() -> Dict[str, Optional[str]]:
    creds = load_credentials()
    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()
    return {
        "email_address": profile.get("emailAddress"),
        "messages_total": str(profile.get("messagesTotal", "")),
    }


def main():
    result = test_connection(allow_interactive=True)
    print("Gmail connection ok.")
    if result.get("email_address"):
        print("Account:", result["email_address"])

if __name__ == '__main__':
    main()
