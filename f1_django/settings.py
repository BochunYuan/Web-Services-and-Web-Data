from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from app.database_urls import sqlite_path_from_url


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def normalize_api_prefix(value: str | None) -> str:
    prefix = (value or "/api/v1").strip()
    if not prefix:
        return "/api/v1"
    if not prefix.startswith("/"):
        prefix = f"/{prefix}"
    return prefix.rstrip("/") or "/"


ENVIRONMENT = env("ENVIRONMENT", "development")
SECRET_KEY = env("SECRET_KEY", "django-insecure-change-me")
DEBUG = ENVIRONMENT != "production"
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "f1_django.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "f1_django.wsgi.application"
ASGI_APPLICATION = "f1_django.asgi.application"

DATABASE_URL = env("DATABASE_URL", f"sqlite:///{BASE_DIR / 'f1_analytics.db'}")


def _sqlite_name_from_url(url: str) -> str:
    return sqlite_path_from_url(url, BASE_DIR)


if DATABASE_URL.startswith("sqlite"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": _sqlite_name_from_url(DATABASE_URL),
        }
    }
else:
    try:
        import dj_database_url  # type: ignore
    except ImportError as exc:
        raise RuntimeError("dj-database-url is required for non-SQLite DATABASE_URL values") from exc

    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=280 if "mysql" in DATABASE_URL else 60,
            ssl_require=False,
        )
    }

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = Path(env("DJANGO_STATIC_ROOT", str(BASE_DIR / "staticfiles")) or str(BASE_DIR / "staticfiles"))
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

API_V1_PREFIX = normalize_api_prefix(env("API_V1_PREFIX", "/api/v1"))
PROJECT_NAME = env("PROJECT_NAME", "F1 Analytics API")
PROJECT_VERSION = env("PROJECT_VERSION", "1.0.0")
PROJECT_DESCRIPTION = env(
    "PROJECT_DESCRIPTION",
    "A RESTful API for Formula 1 World Championship data analysis.",
)
ACCESS_TOKEN_EXPIRE_MINUTES = int(env("ACCESS_TOKEN_EXPIRE_MINUTES", "30") or "30")
REFRESH_TOKEN_EXPIRE_DAYS = int(env("REFRESH_TOKEN_EXPIRE_DAYS", "7") or "7")
ALGORITHM = env("ALGORITHM", "HS256")
RATE_LIMIT_PER_MINUTE = int(env("RATE_LIMIT_PER_MINUTE", "60") or "60")
ALLOWED_ORIGINS = env_list(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000",
)
