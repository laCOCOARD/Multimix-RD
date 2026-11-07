"""Respaldo automatico de la base (2026-11-06): una vez por semana, un JSON comprimido en el bucket privado.

Supabase gratis no hace copias que se puedan bajar y Render free no tiene cron, asi que lo hacen las tareas
periodicas (core/tareas.py). Se guardan los ultimos `GUARDAR`; los mas viejos se borran. Para restaurar, ver
docs/RENDER.md ("Respaldos automaticos"): `loaddata` lee el .json.gz tal cual.

Lleva datos de clientes, asi que nunca va al bucket publico de las fotos: si falta el bucket privado, no se respalda.
"""
import gzip
import io
import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.core.management import call_command
from django.utils import timezone

logger = logging.getLogger('multimix.respaldos')

CARPETA = 'respaldos'
CADA_DIAS = 7
GUARDAR = 8
FORMATO = '%Y-%m-%d-%H%M'
# Lo mismo que excluye el respaldo a mano de docs/RENDER.md: lo que `migrate` vuelve a crear y lo que caduca solo.
EXCLUIR = ['contenttypes', 'auth.permission', 'sessions', 'admin.logentry']


def disponible():
    """Solo con un almacenamiento privado de verdad: el bucket privado de Supabase o la carpeta local."""
    backend = settings.STORAGES['privado']['BACKEND']
    return backend != 'storages.backends.s3.S3Storage' or bool(settings.SUPABASE_BUCKET_PRIVADO)


def _fecha(nombre):
    try:
        return timezone.make_aware(datetime.strptime(nombre.removesuffix('.json.gz'), FORMATO))
    except ValueError:
        return None


def respaldos():
    """Los respaldos guardados, del mas nuevo al mas viejo, como (fecha, nombre)."""
    try:
        _, archivos = storages['privado'].listdir(CARPETA)
    except FileNotFoundError:
        return []
    lista = [(fecha, nombre) for nombre in archivos if (fecha := _fecha(nombre))]
    return sorted(lista, reverse=True)


def _guardar(almacen, ruta, contenido):
    bucket = getattr(almacen, 'bucket', None)
    if bucket is None:
        return almacen.save(ruta, ContentFile(contenido))
    # S3Storage lo subiria como application/json con Content-Encoding gzip, y Supabase lo devuelve descomprimido:
    # el archivo bajado ya no seria un .json.gz. Como application/gzip llega tal cual.
    bucket.put_object(Key=almacen._normalize_name(ruta), Body=contenido, ContentType='application/gzip')
    return ruta


def respaldar(ahora=None):
    """Guarda un respaldo ya y borra los que pasan de `GUARDAR`. Devuelve la ruta guardada."""
    ahora = timezone.localtime(ahora or timezone.now())
    salida = io.StringIO()
    call_command(
        'dumpdata', natural_foreign=True, natural_primary=True, exclude=EXCLUIR, stdout=salida, verbosity=0,
    )
    contenido = gzip.compress(salida.getvalue().encode('utf-8'))
    almacen = storages['privado']
    ruta = _guardar(almacen, f'{CARPETA}/{ahora.strftime(FORMATO)}.json.gz', contenido)
    for _, nombre in respaldos()[GUARDAR:]:
        almacen.delete(f'{CARPETA}/{nombre}')
    logger.info('Respaldo de la base guardado: %s (%s KB)', ruta, len(contenido) // 1024)
    return ruta


def respaldar_si_toca(ahora=None):
    """Respalda si el ultimo tiene `CADA_DIAS` dias o mas (o no hay ninguno). Devuelve la ruta o None."""
    if not disponible():
        return None
    ahora = ahora or timezone.now()
    lista = respaldos()
    if lista and ahora - lista[0][0] < timedelta(days=CADA_DIAS):
        return None
    return respaldar(ahora)
