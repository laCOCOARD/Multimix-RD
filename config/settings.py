"""Configuracion de Multimix RD. Todo lo sensible se lee desde .env."""
import os
import sys
import tempfile
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
    'pagos',
    'clientes',
    'opiniones',
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
    'config.middleware.CuentaObligatoriaMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'config.middleware.PoliticaDeContenidoMiddleware',
    'config.middleware.TareasPeriodicasMiddleware',
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

# Cuentas de clientes. El panel tiene su propia pantalla de entrada.
# Se entra con el usuario o con el correo de la cuenta (el administrador no tiene el correo como usuario).
# ModelBackend sigue en la lista para no cerrar las sesiones abiertas antes de este cambio.
AUTHENTICATION_BACKENDS = ['clientes.autenticacion.CorreoOUsuarioBackend', 'django.contrib.auth.backends.ModelBackend']

LOGIN_URL = 'clientes:entrar'
LOGIN_REDIRECT_URL = 'clientes:cuenta'
# El enlace para recuperar la contraseña vale un dia.
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24

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
    from botocore.config import Config

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
            # Si Supabase no contesta, que falle pronto y el panel lo avise: por defecto botocore espera
            # 60 s y reintenta, y Gunicorn mataba antes la peticion (error 500 en blanco al subir un logo).
            'client_config': Config(
                s3={'addressing_style': 'path'}, connect_timeout=5, read_timeout=20,
                retries={'total_max_attempts': 2},
            ),
            'querystring_auth': False,
            'custom_domain': (
                f"{supabase_url.removeprefix('https://')}/storage/v1/object/public/{supabase_bucket}"
            ),
            # Toda imagen se guarda con un nombre que no se repite (uuid): no hace falta preguntarle
            # antes al almacenamiento si ya existe, que es una ida y vuelta mas por cada foto.
            'file_overwrite': True,
            'object_parameters': {'CacheControl': 'public, max-age=31536000, immutable'},
        },
    }

# Comprobantes de pago: llevan datos bancarios, asi que no van al bucket publico de las fotos. Se guardan en un
# bucket privado de Supabase (SUPABASE_S3_BUCKET_PRIVADO) y solo se ven desde el panel, que los lee con la clave
# del almacenamiento (pagos.admin). En desarrollo van a la carpeta `privado/`, que el sitio no sirve.
PRIVADO_ROOT = BASE_DIR / 'privado' if not EN_TESTS else Path(tempfile.gettempdir()) / 'multimix-privado-pruebas'
storage_privado = {
    'BACKEND': 'django.core.files.storage.FileSystemStorage',
    'OPTIONS': {'location': PRIVADO_ROOT},
}
SUPABASE_BUCKET_PRIVADO = os.getenv('SUPABASE_S3_BUCKET_PRIVADO', '').strip()
if storage_default['BACKEND'] == 'storages.backends.s3.S3Storage':
    if SUPABASE_BUCKET_PRIVADO:
        opciones = {
            clave: valor for clave, valor in storage_default['OPTIONS'].items()
            if clave not in ('custom_domain', 'object_parameters')
        }
        storage_privado = {
            'BACKEND': 'storages.backends.s3.S3Storage',
            'OPTIONS': {**opciones, 'bucket_name': SUPABASE_BUCKET_PRIVADO, 'querystring_auth': True},
        }
    else:
        # Sin el bucket privado siguen en el publico, como antes; el panel lo avisa (pagos.admin).
        storage_privado = storage_default

STORAGES = {
    'default': storage_default,
    'privado': storage_privado,
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
# Pixeles por imagen: por encima, convertirla se come la memoria del servidor (512 MB en Render free). Un PNG o
# WebP se abre entero (40 MP en RGBA = 160 MB); un JPG se lee ya reducido, asi que admite las fotos de 48 o 50 MP
# de los celulares y aun mas.
IMAGEN_MAX_PIXELES = 40_000_000
IMAGEN_MAX_PIXELES_JPEG = 120_000_000
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024

# --- Correo ---
# Con BREVO_API_KEY se envia por la API de Brevo (HTTPS); es lo que funciona en el plan gratis de Render, que
# bloquea SMTP. Con EMAIL_HOST se envia por SMTP. Sin ninguno, los correos se escriben en la consola.
BREVO_API_KEY = os.getenv('BREVO_API_KEY', '').strip()
EMAIL_HOST = os.getenv('EMAIL_HOST', '').strip()
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587') or 587)
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '').strip()
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '').strip()
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
# Que un proveedor lento no deje esperando al cliente que acaba de comprar.
EMAIL_TIMEOUT = 10
if BREVO_API_KEY:
    EMAIL_BACKEND = 'core.correo_brevo.BrevoBackend'
elif EMAIL_HOST:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
CORREO_CONFIGURADO = bool(BREVO_API_KEY or EMAIL_HOST)
# Las cuentas nuevas confirman su correo antes de comprar. Sin correo configurado no se podria: no se pide.
VERIFICAR_CORREO = CORREO_CONFIGURADO and not EN_TESTS and env_bool('VERIFICAR_CORREO', True)
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', '').strip() or 'Multimix RD <no-responder@localhost>'
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# Direccion publica del sitio, para los enlaces de los correos.
SITIO_URL = (
    os.getenv('SITIO_URL', '').strip().rstrip('/')
    or (f'https://{RENDER_EXTERNAL_HOSTNAME}' if RENDER_EXTERNAL_HOSTNAME else 'http://127.0.0.1:8000')
)

# --- WhatsApp (avisos automaticos del pedido, opcional; docs/WHATSAPP.md) ---
# Con la API oficial de Meta (WhatsApp Cloud API). Sin token ni numero, apagado: el panel ofrece igual el boton
# para avisarle al cliente a mano.
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN', '').strip()
WHATSAPP_NUMERO_ID = os.getenv('WHATSAPP_NUMERO_ID', '').strip()
WHATSAPP_PLANTILLA = os.getenv('WHATSAPP_PLANTILLA', '').strip() or 'estado_pedido'
WHATSAPP_IDIOMA = os.getenv('WHATSAPP_IDIOMA', '').strip() or 'es'

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
# Y por cuenta, en la misma ventana: la IP no siempre se sabe, la cuenta si (el checkout la pide).
PEDIDOS_MAX_POR_CUENTA = 10
MAS_VENDIDOS_CACHE_SEGUNDOS = 300
# Pasarela de tarjeta (codigo de un proveedor registrado en pagos/proveedores.py). Vacio = no se ofrece tarjeta.
PAGOS_PROVEEDOR_TARJETA = os.getenv('PAGOS_PROVEEDOR_TARJETA', '').strip().lower()

# --- Importar / exportar productos ---
IMPORT_EXPORT_USE_TRANSACTIONS = True
IMPORT_EXPORT_FORMATS = [XLSX, CSV]

# Mantenimiento que corre solo con las visitas (ver core/tareas.py). En las pruebas se activa a mano.
TAREAS_AUTOMATICAS = not EN_TESTS

# Con CUENTA_OBLIGATORIA=1 todo el sitio pide iniciar sesion (ver config/middleware.py). Apagado: se navega
# libre (Google ve el catalogo) y la cuenta se pide solo para comprar, porque el checkout lleva @login_required.
CUENTA_OBLIGATORIA = os.getenv('CUENTA_OBLIGATORIA', '0') == '1' and not EN_TESTS

# --- Seguridad en produccion ---
# Scripts y estilos solo del propio sitio y del CDN de Bootstrap; las fotos pueden venir del almacenamiento.
# Los scripts NO pueden ir en linea (ni <script> sin src ni onclick=): asi un texto inyectado no se ejecuta. Todo
# script va en static/js/. Los estilos si admiten 'unsafe-inline' porque las plantillas usan atributos style.
# Los formularios solo envian a este sitio: al conectar una pasarela de pago hay que agregar aqui su dominio.
POLITICA_DE_CONTENIDO = '; '.join([
    "default-src 'self'",
    "script-src 'self' https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
    "font-src 'self' data: https://cdn.jsdelivr.net",
    "img-src 'self' data: blob: https:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
# Detras de un proxy, la IP del visitante sale de la cabecera que el proxy reescribe en cada visita: en Render
# (que va detras de Cloudflare) CF-Connecting-IP; con Nginx, X-Real-IP (docs/DESPLIEGUE.md). Se cambia con
# CABECERA_IP (por ejemplo CABECERA_IP=True-Client-IP). X-Forwarded-For no: su primera IP la escribe el visitante.
CONFIAR_IP_PROXY = not DEBUG
CABECERA_IP = 'HTTP_' + (
    os.getenv('CABECERA_IP', '').strip() or ('CF-Connecting-IP' if RENDER_EXTERNAL_HOSTNAME else 'X-Real-IP')
).upper().replace('-', '_')

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
        # Un fallo al enviar correo no se muestra al cliente: tiene que quedar en el registro.
        'multimix.correo': {'handlers': ['consola'], 'level': 'CRITICAL' if EN_TESTS else 'INFO', 'propagate': False},
        'multimix': {
            'handlers': ['consola'] if EN_TESTS else ['consola', 'archivo'],
            'level': 'CRITICAL' if EN_TESTS else 'INFO',
            'propagate': False,
        },
    },
}
