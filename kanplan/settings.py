import os
from importlib.util import find_spec
from dotenv import load_dotenv
from django.core.management.utils import get_random_secret_key

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Where the database, uploads and generated secret key live. Docker points
# this at a mounted folder so data survives container rebuilds.
DATA_DIR = os.environ.get('DATA_DIR', BASE_DIR)


def _load_or_create_secret_key():
    # Use SECRET_KEY from the environment if set, otherwise generate one on
    # first run and persist it so sessions survive restarts.
    key = os.environ.get('SECRET_KEY')
    if key:
        return key
    key_file = os.path.join(DATA_DIR, '.secret_key')
    if os.path.exists(key_file):
        with open(key_file) as f:
            return f.read().strip()
    key = get_random_secret_key()
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(key_file, 'w') as f:
        f.write(key)
    return key


SECRET_KEY = _load_or_create_secret_key()
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# Default AI connection (users can override it in Settings): OpenRouter when only
# OPENROUTER_API_KEY is set, otherwise a local Ollama.
OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'
OPENROUTER_API_KEY  = os.environ.get('OPENROUTER_API_KEY', '')
_ollama_host        = 'host.docker.internal' if os.path.exists('/.dockerenv') else 'localhost'
OLLAMA_BASE_URL     = f'http://{_ollama_host}:11434/v1'
LMSTUDIO_BASE_URL   = f'http://{_ollama_host}:1234/v1'
_default_ai_url     = OPENROUTER_BASE_URL if OPENROUTER_API_KEY else OLLAMA_BASE_URL

AI_BASE_URL      = os.environ.get('AI_BASE_URL', _default_ai_url).rstrip('/')
# Only send the OpenRouter key to OpenRouter, never to another server.
AI_API_KEY       = os.environ.get('AI_API_KEY', OPENROUTER_API_KEY if 'openrouter.ai' in AI_BASE_URL else '')
AI_MODEL         = os.environ.get('AI_MODEL', '')
AI_SUMMARY_MODEL = os.environ.get('AI_SUMMARY_MODEL', '')
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Live reload is a dev-only dependency, so only enable it when installed.
BROWSER_RELOAD = DEBUG and find_spec('django_browser_reload') is not None

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(DATA_DIR, 'media')

FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MAX_UPLOAD_SIZE = 10 * 1024 * 1024

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'app',
]

if BROWSER_RELOAD:
    INSTALLED_APPS += ['django_browser_reload']

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

if BROWSER_RELOAD:
    MIDDLEWARE += ['django_browser_reload.middleware.BrowserReloadMiddleware']

ROOT_URLCONF = 'kanplan.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'kanplan.wsgi.application'


LOGIN_URL = '/login/'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(DATA_DIR, 'db.sqlite3'),
        # Wait for locks and take write locks up front, so concurrent requests
        # (e.g. gunicorn threads) don't fail with "database is locked".
        'OPTIONS': {
            'timeout': 20,
            'transaction_mode': 'IMMEDIATE',
        },
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
