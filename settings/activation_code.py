"""Activation code generator.

Usage:
  python settings/activation_code.py

It will prompt for username, email, and validity, then output an encrypted code.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

try:
    from cryptography.fernet import Fernet
except ImportError as exc:  # pragma: no cover - runtime guard
    raise SystemExit(
        "Missing dependency: cryptography. Install with `pip install cryptography`."
    ) from exc


@dataclass(frozen=True)
class ActivationPayload:
    username: str
    email: str
    issued_at: str
    expires_at: str
    nonce: str
    version: int = 1

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            {
                "version": self.version,
                "username": self.username,
                "email": self.email,
                "issued_at": self.issued_at,
                "expires_at": self.expires_at,
                "nonce": self.nonce,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")


def _load_secret() -> str:
    env_secret = os.environ.get("ACTIVATION_CODE_SECRET")
    if env_secret:
        return env_secret
    try:
        from project import settings as project_settings

        return project_settings.SECRET_KEY
    except Exception:
        return os.environ.get("SECRET_KEY", "")


def _derive_fernet_key(secret: str) -> bytes:
    if not secret:
        raise SystemExit(
            "Missing secret. Set ACTIVATION_CODE_SECRET or SECRET_KEY environment variable."
        )
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _parse_validity(value: str, now: datetime) -> datetime:
    value = value.strip()
    if not value:
        raise ValueError("有效期不能为空")

    if value.isdigit():
        days = int(value)
        if days <= 0:
            raise ValueError("有效期天数必须大于 0")
        return now + timedelta(days=days)

    # Try YYYY-MM-DD
    try:
        parsed_date = date.fromisoformat(value)
        return datetime.combine(parsed_date, time(23, 59, 59), tzinfo=timezone.utc)
    except ValueError:
        pass

    # Try full ISO datetime
    try:
        parsed_dt = datetime.fromisoformat(value)
        if parsed_dt.tzinfo is None:
            parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
        return parsed_dt
    except ValueError as exc:
        raise ValueError("有效期格式应为天数或 YYYY-MM-DD") from exc


def generate_activation_code(username: str, email: str, validity: str) -> tuple[str, str]:
    username = username.strip()
    email = email.strip()
    if not username:
        raise ValueError("用户名不能为空")
    if not email or "@" not in email:
        raise ValueError("邮箱格式不正确")

    now = datetime.now(timezone.utc)
    expires_at = _parse_validity(validity, now)

    payload = ActivationPayload(
        username=username,
        email=email,
        issued_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
        nonce=secrets.token_urlsafe(16),
    )

    secret = _load_secret()
    fernet = Fernet(_derive_fernet_key(secret))
    token = fernet.encrypt(payload.to_json_bytes()).decode("utf-8")
    return token, expires_at.isoformat()


def parse_activation_code(token: str, secret: Optional[str] = None) -> dict:
    """Decrypt and parse activation code.

    Returns a dict with payload fields. Raises on invalid token.
    """

    token = token.strip()
    if not token:
        raise ValueError("激活码不能为空")

    if secret is None:
        secret = _load_secret()

    fernet = Fernet(_derive_fernet_key(secret))
    payload_bytes = fernet.decrypt(token.encode("utf-8"))
    payload = json.loads(payload_bytes.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("激活码内容无效")

    required_fields = {"version", "username", "email", "issued_at", "expires_at", "nonce"}
    if not required_fields.issubset(payload.keys()):
        raise ValueError("激活码内容缺少必要字段")

    return payload


def main(argv: Optional[list[str]] = None) -> int:
    try:
        username = input("请输入用户名: ").strip()
        email = input("请输入邮箱: ").strip()
        validity = input("请输入有效期(天数或YYYY-MM-DD): ").strip()
        token, expires_at = generate_activation_code(username, email, validity)
    except Exception as exc:
        print(f"错误: {exc}")
        return 1

    print("激活码:")
    print(token)
    print(f"到期时间(UTC): {expires_at}")
    return 0


if __name__ == "__main__":
    print(parse_activation_code(
        "gAAAAABpjd-Y1WGQoLdKqlJuvNZsYdUlpqz66Mg5n8B9lP7c6Y5NggQzOrjbu8owrzmAd-6U40QFHcNCCIv1L6rxREuvmfTkTwUmE1CWDurBH6hkMXRF_Lhxnnii8pGuvospS-VXlRIxHPgP1udxjHtx4TxScq8tFMZ6QTCZmW232t0CYlJjGYiqweFl63tdqw_BbKsXJ2ZSWsvgx90iPh3Wen9QhtWNKjKPJfG6aB91FL5N8bdadHJuH-MLZEeJh11asVB98Ygkqkrd2C5srk8jy0iSfLLIMKovUB8M2hqJPIYMonJ7PZJ-aqp3bJ36jz1C4ZhtyeM6"))
    # raise SystemExit(main())
