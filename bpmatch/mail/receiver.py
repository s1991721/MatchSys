from .common import MailToolError
from .imap_receiver import ImapReceiver
from .pop3_receiver import Pop3Receiver


class MailReceiver:
    """收信门面，负责选择并调用具体的协议实现。"""

    def __init__(self, send_config):
        self.send_config = send_config or {}
        self.receiver = self._build_receiver()

    def connect(self):
        return self.receiver.connect()

    def authenticate(self, username: str, password: str):
        return self.receiver.authenticate(username, password)

    def open_mailbox(self, folder: str):
        return self.receiver.open_mailbox(folder)

    def list_message_ids(self, criteria=None):
        return self.receiver.list_message_ids(criteria)

    def fetch_headers(self, message_id: str, fields=None):
        return self.receiver.fetch_headers(message_id, fields=fields)

    def fetch_message(self, message_id: str):
        return self.receiver.fetch_message(message_id)

    def get_flags(self, message_id: str):
        return self.receiver.get_flags(message_id)

    def get_stable_remote_id(self, message_id: str):
        return self.receiver.get_stable_remote_id(message_id)

    def supports_folders(self) -> bool:
        return self.receiver.supports_folders()

    def supports_server_search(self) -> bool:
        return self.receiver.supports_server_search()

    def supports_server_flags(self) -> bool:
        return self.receiver.supports_server_flags()

    def sync_mails(self, owner_id, sync_limit=120):
        return self.receiver.sync_mails(owner_id, sync_limit=sync_limit)


    def query_mails(self, page=1, page_size=20, keyword="", send_date=""):
        return self.receiver.query_mails(
            page=page,
            page_size=page_size,
            keyword=keyword,
            send_date=send_date,
        )

    def get_mail_detail(self, mail_id):
        return self.receiver.get_mail_detail(mail_id)

    def test_connection(self):
        return self.receiver.test_connection()

    def _build_receiver(self):
        incoming_protocol = str(self.send_config.get("incoming_protocol") or "").strip().lower()
        if incoming_protocol == "pop3":
            return Pop3Receiver(self.send_config)
        if str(self.send_config.get("pop3_host") or "").strip() and not str(
            self.send_config.get("imap_host") or ""
        ).strip():
            return Pop3Receiver(self.send_config)
        return ImapReceiver(self.send_config)


# 同步我的邮件（昨天-现在）
def sync_my_mails(owner_id, send_config, sync_limit=120):
    try:
        return MailReceiver(send_config).sync_mails(owner_id, sync_limit=sync_limit)
    except Exception as exc:
        if isinstance(exc, MailToolError):
            raise
        raise MailToolError(str(exc), status=500)


def query_my_mails(send_config, page=1, page_size=20, keyword="", send_date=""):
    try:
        return MailReceiver(send_config).query_mails(
            page=page,
            page_size=page_size,
            keyword=keyword,
            send_date=send_date,
        )
    except Exception as exc:
        if isinstance(exc, MailToolError):
            raise
        raise MailToolError(str(exc), status=500)


def get_my_mail_detail(send_config, mail_id):
    try:
        return MailReceiver(send_config).get_mail_detail(mail_id)
    except Exception as exc:
        if isinstance(exc, MailToolError):
            raise
        raise MailToolError(str(exc), status=500)


def test_receive_connection(send_config):
    try:
        return MailReceiver(send_config).test_connection()
    except Exception as exc:
        if isinstance(exc, MailToolError):
            raise
        raise MailToolError(str(exc), status=500)
