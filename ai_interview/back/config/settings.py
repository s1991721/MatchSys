"""Django settings for the AI Interview backend."""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.environ.get(
    "AI_INTERVIEW_SECRET_KEY",
    "django-insecure-ai-interview-local-development-only",
)
DEBUG = env_bool("AI_INTERVIEW_DEBUG", default=True)
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "AI_INTERVIEW_ALLOWED_HOSTS",
        "localhost,127.0.0.1,[::1]",
    ).split(",")
    if host.strip()
]

INSTALLED_APPS = [
    # Sessions are stored in the manually maintained django_session table.
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "corsheaders",
    "accounts",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# PyCharm serves static files from a separate local port. Allow those local
# origins in development while keeping production same-origin by default.
_default_local_origins = (
    "http://localhost:63342,http://127.0.0.1:63342" if DEBUG else ""
)
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "AI_INTERVIEW_CORS_ALLOWED_ORIGINS",
        _default_local_origins,
    ).split(",")
    if origin.strip()
]
CORS_ALLOWED_ORIGIN_REGEXES = (
    [r"^http://(?:localhost|127\.0\.0\.1)(?::\d+)?$"] if DEBUG else []
)
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("AI_INTERVIEW_DB_NAME", "ai_interview"),
        "USER": os.environ.get("AI_INTERVIEW_DB_USER", "root"),
        "PASSWORD": os.environ.get("AI_INTERVIEW_DB_PASSWORD", "123456"),
        "HOST": os.environ.get("AI_INTERVIEW_DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("AI_INTERVIEW_DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET time_zone = '+09:00'",
        },
    }
}

LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = True

# MatchSys and AI Interview share one public domain. Use product-specific cookie
# names and paths so signing in to either Django service does not overwrite the
# other service's session or CSRF token.
SESSION_COOKIE_NAME = "ai_interview_sessionid"
SESSION_COOKIE_PATH = os.environ.get(
    "AI_INTERVIEW_COOKIE_PATH",
    "/" if DEBUG else "/ai_interview/",
)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_NAME = "ai_interview_csrftoken"
CSRF_COOKIE_PATH = SESSION_COOKIE_PATH
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"

# Gunicorn receives HTTP from Nginx; trust the forwarded protocol for secure
# request and cookie handling.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
