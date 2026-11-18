"""Django settings. Secrets and server-specific values come from environment variables (.env)."""

import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # .../web
REPO_ROOT = BASE_DIR.parent  # .../treasure-travel
sys.path.insert(0, str(REPO_ROOT))  # so `import agent` and `import src` work
load_dotenv(REPO_ROOT / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
if not DEBUG and (
    len(SECRET_KEY) < 50
    or len(set(SECRET_KEY)) < 5
    or SECRET_KEY.startswith("django-insecure-")
    or SECRET_KEY in {"dev-only-change-me", "change-me-to-a-long-random-string"}
):
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY to a random value of at least 50 characters.")
DATA_UPLOAD_MAX_MEMORY_SIZE = 32 * 1024
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]
if os.environ.get("BEHIND_HTTPS_PROXY") == "1":  # Caddy terminates HTTPS in front of us
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "planner",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "planner.limits.AdminLoginLimitMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "travel_site.urls"
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
            ]
        },
    }
]
WSGI_APPLICATION = "travel_site.wsgi.application"

DB_DIR = Path(os.environ.get("DB_DIR", REPO_ROOT / "web_data"))
DB_DIR.mkdir(parents=True, exist_ok=True)
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": DB_DIR / "db.sqlite3"}}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# "offline" = deterministic planner; "claude" = API; "fake" = scripted test fixture
AGENT_BACKEND = os.environ.get(
    "AGENT_BACKEND", "claude" if os.environ.get("ANTHROPIC_API_KEY") else "offline"
)

if AGENT_BACKEND not in {"claude", "fake", "offline"}:
    raise ImproperlyConfigured("AGENT_BACKEND must be claude, offline or fake.")


MAPS_MODE = os.environ.get("MAPS_MODE", "offline")
if MAPS_MODE not in {"offline", "google"}:
    raise ImproperlyConfigured("MAPS_MODE must be offline or google.")
REDIS_URL = os.environ.get("REDIS_URL", "")
PLANNER_LIMITS_ENABLED = os.environ.get("PLANNER_LIMITS_ENABLED", "1") == "1"
PLANNER_RATE = int(os.environ.get("PLANNER_RATE", "20"))
PLANNER_LOGIN_RATE = int(os.environ.get("PLANNER_LOGIN_RATE", "10"))
PLANNER_MAX_CONCURRENT = int(os.environ.get("PLANNER_MAX_CONCURRENT", "4"))
PLANNER_LEASE_SECONDS = int(os.environ.get("PLANNER_LEASE_SECONDS", "180"))
if min(PLANNER_RATE, PLANNER_LOGIN_RATE, PLANNER_MAX_CONCURRENT) < 1:
    raise ImproperlyConfigured("Planner limits must be positive.")
if PLANNER_LEASE_SECONDS < 150:
    raise ImproperlyConfigured(
        "Lease must exceed the 120-second sync worker timeout (minimum 150)."
    )
if REDIS_URL:
    CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 12 * 60 * 60
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
if not DEBUG:
    if not REDIS_URL or not PLANNER_LIMITS_ENABLED:
        raise ImproperlyConfigured("Production requires REDIS_URL and enabled admission limits.")
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured("Production requires explicit ALLOWED_HOSTS.")
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r"^healthz$", r"^readyz$"]
    SECURE_HSTS_SECONDS = 3600
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

if AGENT_BACKEND == "offline" and MAPS_MODE == "google":
    raise ImproperlyConfigured("Google Maps requires the dated Claude planner, not offline mode.")
if not DEBUG and AGENT_BACKEND == "claude":
    if not os.environ.get("ANTHROPIC_API_KEY") or not os.environ.get("LLM_MODEL"):
        raise ImproperlyConfigured("Claude requires ANTHROPIC_API_KEY and an explicit LLM_MODEL.")
if not DEBUG and MAPS_MODE == "google":
    if not os.environ.get("GOOGLE_MAPS_API_KEY") or not os.environ.get("GOOGLE_PLACE_IDS_FILE"):
        raise ImproperlyConfigured("Google Maps requires API key and verified place-ID mapping.")
