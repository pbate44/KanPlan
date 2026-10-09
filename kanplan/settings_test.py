"""
Test settings — used by pytest (locally and in CI).

Uses an in-memory SQLite database and a fixed secret key so tests never
touch the local db.sqlite3 or .secret_key files.
"""

import os

# Fixed key so tests never generate a .secret_key file.
os.environ.setdefault("SECRET_KEY", "django-insecure-test-key-not-for-production")

from kanplan.settings import *  # noqa: E402, F401, F403

# Fixed AI provider so tests don't depend on .env; API calls are always mocked.
AI_BASE_URL      = "https://openrouter.ai/api/v1"
AI_API_KEY       = "test-key"
AI_MODEL         = ""
AI_SUMMARY_MODEL = ""
OPENROUTER_API_KEY = ""

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# PBKDF2 is deliberately slow; MD5 is fine for throwaway test users.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.InMemoryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
