"""Limite de intentos: cuantas veces se puede hacer algo (entrar, crear una cuenta, probar un cupon...) en un rato.

Se cuenta en la base (`core.models.Intento`), de modo que valga para todos los procesos y sobreviva a un reinicio.
Las partes de la clave (una IP, un correo, un usuario) se resumen con sha256 antes de guardarse.
"""
import hashlib
from datetime import timedelta

from django.utils import timezone

from .models import Intento

INTENTOS_MAXIMOS = 5
VENTANA_SEGUNDOS = 15 * 60
# Lo que se guarda mas alla de esto ya no cuenta para ninguna ventana; lo borran las tareas periodicas.
CONSERVAR_HORAS = 24


def _clave(accion, *partes):
    texto = accion + ':' + ':'.join(str(parte).strip().lower() for parte in partes)
    return hashlib.sha256(texto.encode()).hexdigest()


def intentos(accion, *partes, ventana=VENTANA_SEGUNDOS):
    desde = timezone.now() - timedelta(seconds=ventana)
    return Intento.objects.filter(clave=_clave(accion, *partes), creado__gte=desde).count()


def bloqueado(accion, *partes, maximo=INTENTOS_MAXIMOS, ventana=VENTANA_SEGUNDOS):
    return intentos(accion, *partes, ventana=ventana) >= maximo


def anotar_intento(accion, *partes):
    Intento.objects.create(clave=_clave(accion, *partes))


def olvidar_intentos(accion, *partes):
    Intento.objects.filter(clave=_clave(accion, *partes)).delete()


def borrar_viejos():
    return Intento.objects.filter(creado__lt=timezone.now() - timedelta(hours=CONSERVAR_HORAS)).delete()[0]
