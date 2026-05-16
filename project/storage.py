import os
from pathlib import Path

from django.conf import settings


"""
统一文件存储入口。

业务层只使用 StorageArea 和本模块提供的文件操作方法，不直接拼接 BASE_DIR、
upload 或未来可能出现的 bucket 路径。这样底层从本地目录切换到对象存储时，
可以优先在这里适配，减少业务代码变更。
"""


class StorageArea:
    """业务文件区标识。业务代码只需要知道这些业务目录。"""

    SS = "ss"
    CUSTOMER_CONTRACT = "customer_contract"
    LINE_UPLOADS = "line_uploads"
    CREDENTIALS = "credentials"
    COMPANY_INFO = "company_info"
    ORDER = "order"


# 业务文件区到存储内相对目录的映射。
# 注意：这里的目录不包含 upload 根目录；relative_path() 也会返回这个业务相对路径。
_AREA_DIRS = {
    StorageArea.SS: "ss",
    StorageArea.CUSTOMER_CONTRACT: "customer_contract",
    StorageArea.LINE_UPLOADS: "line_uploads",
    StorageArea.CREDENTIALS: "credentials",
    StorageArea.COMPANY_INFO: "company_info",
    StorageArea.ORDER: "order",
}


def _upload_root() -> Path:
    """返回当前本地存储根目录，默认是项目根目录下的 upload。"""

    return Path(getattr(settings, "UPLOAD_ROOT", settings.BASE_DIR / "upload"))


def _area_root(area: str) -> Path:
    """返回某个业务文件区的真实本地目录，并确保目录存在。"""

    try:
        relative_dir = _AREA_DIRS[area]
    except KeyError as exc:
        raise ValueError(f"Unknown storage area: {area}") from exc

    root = (_upload_root() / relative_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_path(area: str, filename: str | None = None) -> Path:
    """
    解析业务文件路径，并防止通过 ../ 逃逸到业务目录外。

    filename 为空时返回业务文件区目录，主要用于兼容旧 helper。
    """

    root = _area_root(area)
    if not filename:
        return root

    target = (root / filename).resolve()
    if target != root and root not in target.parents:
        raise ValueError("Invalid storage path")
    return target


def save_upload(area: str, filename: str, uploaded_file) -> str:
    """保存 Django request.FILES 中的上传文件，返回原文件名用于写入数据库。"""

    target = _resolve_path(area, filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "wb") as handle:
        for chunk in uploaded_file.chunks():
            handle.write(chunk)
    return filename


def save_bytes(area: str, filename: str, content: bytes) -> str:
    """保存 bytes 内容，适用于 LINE 图片、JSON 凭据和 Gmail token 写回。"""

    target = _resolve_path(area, filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return filename


def open_file(area: str, filename: str, mode: str = "rb"):
    """打开业务文件，供 FileResponse、邮件附件读取等场景使用。"""

    return open(_resolve_path(area, filename), mode)


def exists(area: str, filename: str) -> bool:
    """判断业务文件是否存在。"""

    return _resolve_path(area, filename).exists()


def path(area: str, filename: str | None = None) -> str:
    """
    返回当前实现下的真实本地路径。

    业务代码应优先使用 save/open/exists；只有第三方 SDK 必须接收路径字符串时，
    才使用这个方法，例如 Google OAuth 或 Vision SDK。
    """

    return str(_resolve_path(area, filename))


def relative_path(area: str, filename: str) -> str:
    """
    返回业务相对路径，不包含 upload 根目录。

    用于数据库、日志和 API 返回值，例如 credentials/gmail_token.json。
    """

    _resolve_path(area, filename)
    try:
        relative_dir = _AREA_DIRS[area]
    except KeyError as exc:
        raise ValueError(f"Unknown storage area: {area}") from exc
    return str(Path(relative_dir) / filename)
