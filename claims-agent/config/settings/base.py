"""Django base settings — claims-agent"""
from pathlib import Path
from decouple import config as env_config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = env_config("SECRET_KEY", default="dev-secret-change-in-production")
DEBUG = env_config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = env_config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "corsheaders",
    "channels",
    "drf_spectacular",
    # Local apps
    "apps.cases",
    "apps.policies",
    "apps.drugs",
    "apps.hospitals",
    "apps.diseases",
    "apps.rules",
    "apps.audit",
    "apps.fulfillment",
    "apps.sla",
    "apps.reports",
    "apps.organizations",
    "apps.notifications",
    "apps.evaluation",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "data" / "db.sqlite3",
    }
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Session
SESSION_COOKIE_AGE = 28800  # 8 hours

# Auth
AUTH_USER_MODEL = "organizations.User"
LOGIN_URL = "/login/"

# Internationalization
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# CORS (dev)
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = env_config("CORS_ORIGINS", default="http://localhost:5173").split(",")

# Channels
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# Huey
HUEY = {
    "huey_class": "huey.SqliteHuey",
    "filename": BASE_DIR / "data" / "huey.db",
    "immediate": DEBUG,
}

# Readonly DB
READONLY_DB_URL = env_config("READONLY_DB_URL", default=None)

# AI Models
DASHSCOPE_API_KEY = env_config("DASHSCOPE_API_KEY", default="")
DASHSCOPE_BASE_URL = env_config("DASHSCOPE_BASE_URL", default="https://dashscope.aliyuncs.com/compatible-mode/v1")
PRIMARY_MODEL = env_config("PRIMARY_MODEL", default="qwen3.6-plus")
FALLBACK_MODEL = env_config("FALLBACK_MODEL", default="deepseek-v4-pro")
FLASH_MODEL = env_config("FLASH_MODEL", default="qwen3.6-flash")
LARGE_CONTEXT_MODEL = env_config("LARGE_CONTEXT_MODEL", default="deepseek-v4-flash")
EMBEDDING_MODEL = env_config("EMBEDDING_MODEL", default="text-embedding-v3")
