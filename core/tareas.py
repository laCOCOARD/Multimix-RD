"""Tareas periodicas sin programador.

El plan gratis de Render no tiene tareas programadas, asi que el mantenimiento corre, como mucho una vez por
hora, aprovechando una visita cualquiera. Donde si haya cron se puede seguir usando el comando
`cancelar_pedidos_vencidos`.
"""
import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('multimix.tareas')

CLAVE = 'tareas_periodicas'
CADA_SEGUNDOS = 60 * 60


def ejecutar_si_toca():
    """Cancela los pedidos vencidos y limpia sesiones caducadas e intentos viejos, si paso una hora desde la ultima vez."""
    if not settings.TAREAS_AUTOMATICAS or not cache.add(CLAVE, 1, CADA_SEGUNDOS):
        return False
    try:
        from django.contrib.sessions.models import Session
        from django.utils import timezone

        from pedidos.services import cancelar_pedidos_vencidos

        cancelados = cancelar_pedidos_vencidos()
        if cancelados:
            logger.info('Pedidos vencidos cancelados: %s', ', '.join(cancelados))
        Session.objects.filter(expire_date__lt=timezone.now()).delete()
        from .limites import borrar_viejos

        borrar_viejos()
        from pagos.services import mover_comprobantes_al_privado

        mover_comprobantes_al_privado()
        from catalogo.avisos import avisar_disponibles

        # Los cambios hechos en masa (acciones del panel, importacion) no pasan por el aviso inmediato.
        avisar_disponibles()
        from clientes.services import recordar_carritos_abandonados

        recordar_carritos_abandonados()
    except Exception:
        # El mantenimiento nunca debe tumbar la pagina que alguien esta viendo.
        logger.exception('Fallaron las tareas periodicas')
    return True
