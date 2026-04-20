from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ReceiverInterface(ABC):
    @abstractmethod
    def connect(self):
        """建立到邮件服务器的网络连接。"""

    @abstractmethod
    def authenticate(self, username: str, password: str):
        """使用账号密码或授权码完成登录认证。"""

    @abstractmethod
    def open_mailbox(self, folder: str):
        """打开目标邮箱或文件夹。"""

    @abstractmethod
    def list_message_ids(self, criteria: Optional[Dict[str, Any]] = None) -> List[bytes]:
        """按条件列出邮件标识列表。"""

    @abstractmethod
    def fetch_headers(self, message_id: str, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """仅读取邮件头信息，不取正文和附件。"""

    @abstractmethod
    def fetch_message(self, message_id: str) -> Dict[str, Any]:
        """读取整封邮件的完整内容。"""

    @abstractmethod
    def get_flags(self, message_id: str) -> Dict[str, Any]:
        """读取邮件状态标记。"""

    @abstractmethod
    def get_stable_remote_id(self, message_id: str) -> str:
        """返回可用于去重和增量同步的稳定远端标识。"""

    @abstractmethod
    def supports_folders(self) -> bool:
        """返回当前协议是否支持文件夹切换。"""

    @abstractmethod
    def supports_server_search(self) -> bool:
        """返回当前协议是否支持服务端搜索。"""

    @abstractmethod
    def supports_server_flags(self) -> bool:
        """返回当前协议是否支持读取服务端状态标记。"""

    @abstractmethod
    def logout(self):
        """关闭与邮件服务器的会话。"""

    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """验证当前接收协议配置是否可以成功连接并认证。"""

    @abstractmethod
    def sync_mails(self, owner_id, sync_limit=120):
        """同步昨天 00:00 到当前时刻的邮件，`sync_limit` 控制最多处理的候选邮件数。"""
