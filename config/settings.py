"""Configuracion de Multimix RD. Todo lo sensible se lee desde .env."""
import os
import sys
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
from import_export.formats.base_formats import CSV, XLSX

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def env_bool(nombre, defecto=False):
    return os.getenv(nombre, str(defecto)).strip().lower() in ('1', 'true', 'yes', 'si', 'on')


def env_lista(nombre):
    return [v.strip() for v in os.getenv(nombre, '').split(',') if v.strip()]


EN_TESTS = len(sys.argv) > 1 and sys.argv[1] == 'test'

SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured('Falta SECRET_KEY en el archivo .env')

DEBUG = env_bool('DEBUG', False)
ALLOWED_HOSTS = env_lista('ALLOWED_HOSTS')
CSRF_TRUSTED_ORIGINS = env_lista('CSRF_TRUSTED_ORIGINS')
RENDER_EXTERNAL_HOSTNAME = os.getenv('RENDER_EXTERNAL_HOSTNAME', '').strip()
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')
ADMIN_URL = os.getenv('ADMIN_URL', 'panel').strip('/') or 'panel'

INSTALLED_APPS = [
    'config.apps.PanelAdminConfig',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'import_export',
    'tiendas',
    'core',
    'catalogo',
    'promociones',
    'carrito',
    'pedidos',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'config.middleware.ExcepcionRequestLoggingMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.tienda',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# --- Base de datos: se elige con DB_ENGINE o DATABASE_URL ---
DB_ENGINE = os.getenv('DB_ENGINE', 'sqlite').strip().lower()

if os.getenv('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.parse(
            os.environ['DATABASE_URL'], conn_max_age=60, ssl_require=not DEBUG,
        )
    }
elif DB_ENGINE == 'sqlite':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / os.getenv('DB_NAME', 'db.sqlite3'),
            # IMMEDIATE toma el bloqueo de escritura al abrir la transaccion; asi
            # las operaciones de stock quedan serializadas tambien en SQLite,
            # donde select_for_update no tiene efecto.
            'OPTIONS': {'transaction_mode': 'IMMEDIATE', 'timeout': 20},
        }
    }
elif DB_ENGINE in ('postgresql', 'mysql'):
    DATABASES = {
        'default': {
            'ENGINE': f'django.db.backends.{DB_ENGINE}',
            'NAME': os.getenv('DB_NAME', ''),
            'USER': os.getenv('DB_USER', ''),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', ''),
            'CONN_MAX_AGE': 60,
        }
    }
    if DB_ENGINE == 'mysql':
        DATABASES['default']['OPTIONS'] = {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        }
else:
    raise ImproperlyConfigured('DB_ENGINE debe ser sqlite, postgresql o mysql')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# En los tests se desactiva la cache para que cada prueba sea independiente.
CACHES = {
    'default': {
        'BACKEND': (
            'django.core.cache.backends.dummy.DummyCache' if EN_TESTS
            else 'django.core.cache.backends.locmem.LocMemCache'
        ),
    }
}

if EN_TESTS:
    # Las pruebas crean muchos usuarios; el cifrado real de contraseñas las haria lentas.
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- Idioma y zona horaria ---
LANGUAGE_CODE = 'es'
LANGUAGES = [('es', 'Español')]
TIME_ZONE = 'America/Santo_Domingo'
USE_I18N = True
USE_TZ = True

# --- Archivos estaticos y subidos ---
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_STORAGE = os.getenv('MEDIA_STORAGE', 'local').strip().lower()
if MEDIA_STORAGE not in ('local', 'supabase'):
    raise ImproperlyConfigured('MEDIA_STORAGE debe ser local o supabase')

storage_default = {'BACKEND': 'django.core.files.storage.FileSystemStorage'}
if MEDIA_STORAGE == 'supabase' and not EN_TESTS:
    supabase_url = os.getenv('SUPABASE_URL', '').rstrip('/')
    supabase_endpoint = os.getenv('SUPABASE_S3_ENDPOINT', '').rstrip('/')
    supabase_region = os.getenv('SUPABASE_S3_REGION', '').strip()
    supabase_bucket = os.getenv('SUPABASE_S3_BUCKET', '').strip()
    supabase_access_key = os.getenv('SUPABASE_S3_ACCESS_KEY_ID', '').strip()
    supabase_secret_key = os.getenv('SUPABASE_S3_SECRET_ACCESS_KEY', '').strip()
    supabase_values = (
        supabase_url, supabase_endpoint, supabase_region, supabase_bucket,
        supabase_access_key, supabase_secret_key,
    )
    if not all(supabase_values):
        raise ImproperlyConfigured('Falta configurar una o mas variables de Supabase Storage')
    if not supabase_url.startswith('https://') or not supabase_endpoint.startswith('https://'):
        raise ImproperlyConfigured('Las URL de Supabase Storage deben usar HTTPS')
    if not supabase_endpoint.endswith('/storage/v1/s3'):
        raise ImproperlyConfigured('SUPABASE_S3_ENDPOINT debe terminar en /storage/v1/s3')

    storage_default = {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'access_key': supabase_access_key,
            'secret_key': supabase_secret_key,
            'bucket_name': supabase_bucket,
            'endpoint_url': supabase_endpoint,
            'region_name': supabase_region,
            'addressing_style': 'path',
            'querystring_auth': False,
            'custom_domain': (
                f"{supabase_url.removeprefix('https://')}/storage/v1/object/public/{supabase_bucket}"
            ),
            'file_overwrite': False,
            'object_parameters': {'CacheControl': 'public, max-age=31536000, immutable'},
        },
    }

STORAGES = {
    'default': storage_default,
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage' if EN_TESTS
            else 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        ),
    },
}
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Imagenes: limite de subida y lado maximo al redimensionar las fotos de producto.
IMAGEN_MAX_BYTES = 5 * 1024 * 1024
IMAGEN_LADO_MAXIMO = 1200
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024

# --- Sesiones y mensajes ---
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

# --- Tienda ---
CARRITO_SESSION_ID = 'carrito'
CARRITO_MAX_POR_PRODUCTO = 99
# Anti-spam: pedidos permitidos por IP dentro de la ventana indicada.
PEDIDOS_MAX_POR_IP = 5
PEDIDOS_VENTANA_IP_MINUTOS = 60
MAS_VENDIDOS_CACHE_SEGUNDOS = 300

# --- Importar / exportar productos ---
IMPORT_EXPORT_USE_TRANSACTIONS = True
IMPORT_EXPORT_FORMATS = [XLSX, CSV]

# --- Seguridad en produccion ---
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
# Detras de Nginx la IP real del cliente llega en X-Real-IP.
CONFIAR_IP_PROXY = not DEBUG

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = not EN_TESTS
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# --- Logging ---
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detallado': {
            'format': '{asctime} {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'consola': {'class': 'logging.StreamHandler', 'formatter': 'detallado'},
        'archivo': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'multimix.log',
            'maxBytes': 2 * 1024 * 1024,
            'backupCount': 5,
            'encoding': 'utf-8',
            'formatter': 'detallado',
        },
    },
    'root': {'handlers': ['consola'], 'level': 'WARNING'},
    'loggers': {
        'django': {'handlers': ['consola'], 'level': 'INFO', 'propagate': False},
        'django.request': {
            'handlers': ['consola', 'archivo'], 'level': 'ERROR', 'propagate': False,
        },
        'multimix': {
            'handlers': ['consola'] if EN_TESTS else ['consola', 'archivo'],
            'level': 'CRITICAL' if EN_TESTS else 'INFO',
            'propagate': False,
        },
    },
}
