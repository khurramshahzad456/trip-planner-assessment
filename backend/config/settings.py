"""Django settings for the ELD Trip Planner backend.

All environment-specific values are read from environment variables (or a local
``.env`` file) so that no secrets live in source control.
"""

import os
import sys
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


RUNNING_TESTS = len(sys.argv) > 1 and sys.argv[1] == "test"

DEBUG = env_bool("DEBUG", default=False)
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY == "change-me":
    if DEBUG or RUNNING_TESTS:
        SECRET_KEY = "django-insecure-local-development-key-do-not-use-in-production"
    else:
        raise ImproperlyConfigured("SECRET_KEY must be set when DEBUG is False.")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "trips",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    }
]

DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG or RUNNING_TESTS
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

# --- CORS ---------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
CORS_ALLOWED_ORIGIN_REGEXES = env_list("CORS_ALLOWED_ORIGIN_REGEXES")
CORS_ALLOW_CREDENTIALS = False

# --- Django REST Framework ---------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"]
    + (["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else []),
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    "EXCEPTION_HANDLER": "trips.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [] if RUNNING_TESTS else ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"trip_plan": "20/min", "autocomplete": "90/min"},
}

# Provider responses are cached in the database so every gunicorn worker shares
# them and they survive restarts (run `manage.py createcachetable` once).
CACHES = {
    "default": {
        "BACKEND": (
            "django.core.cache.backends.locmem.LocMemCache"
            if RUNNING_TESTS
            else "django.core.cache.backends.db.DatabaseCache"
        ),
        "LOCATION": "eld_provider_cache",
        "TIMEOUT": 60 * 60 * 24,
        "OPTIONS": {"MAX_ENTRIES": 20000},
    }
}

# --- Mapping / trip planner configuration ------------------------------
TRIP_PLANNER = {
    "ROUTING_PROVIDER": os.environ.get("ROUTING_PROVIDER", "osrm").lower(),
    "ROUTING_API_KEY": os.environ.get("ROUTING_API_KEY", ""),
    "OSRM_BASE_URL": os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org"),
    "OPENROUTESERVICE_BASE_URL": os.environ.get(
        "OPENROUTESERVICE_BASE_URL", "https://api.openrouteservice.org"
    ),
    "NOMINATIM_BASE_URL": os.environ.get("NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org"),
    "PHOTON_BASE_URL": os.environ.get("PHOTON_BASE_URL", "https://photon.komoot.io"),
    "OVERPASS_URLS": env_list(
        "OVERPASS_URLS",
        "https://overpass-api.de/api/interpreter,https://overpass.private.coffee/api/interpreter",
    ),
    # OSM services reject generic or placeholder User-Agents (e.g. python-requests, example.com).
    "HTTP_USER_AGENT": os.environ.get("HTTP_USER_AGENT") or "eld-trip-planner/1.0 (+https://github.com/eld-trip-planner)",
    "GEOCODING_COUNTRY_CODES": os.environ.get("GEOCODING_COUNTRY_CODES", "us"),
    "ENABLE_FUEL_STATION_LOOKUP": env_bool("ENABLE_FUEL_STATION_LOOKUP", default=not RUNNING_TESTS),
    "ENABLE_REVERSE_GEOCODING": env_bool("ENABLE_REVERSE_GEOCODING", default=not RUNNING_TESTS),
    "REQUEST_TIMEOUT_SECONDS": float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "15")),
}
if RUNNING_TESTS:
    TRIP_PLANNER["ENABLE_FUEL_STATION_LOOKUP"] = False
    TRIP_PLANNER["ENABLE_REVERSE_GEOCODING"] = False

# --- Security hardening for production ----------------------------------
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=not RUNNING_TESTS)
    SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # HSTS preload is a per-domain decision; *.onrender.com is not ours to submit.
    SILENCED_SYSTEM_CHECKS = ["security.W021"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {"django": {"handlers": ["console"], "level": "WARNING", "propagate": False}},
}
