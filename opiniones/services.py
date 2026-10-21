"""Reseñas y preguntas de productos: quien puede opinar, la compra verificada y lo que se publica."""
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count
from django.urls import reverse
from django.utils import timezone

from core import correo, limites
from core.correo import url_absoluta
from core.validators import validar_imagen
from pedidos.avisos import correos_de_la_tienda
from pedidos.models import DetallePedido, Pedido

from .models import FotoResena, Pregunta, Resena

Estado = Resena.Estado
PUBLICADAS_POR_PRODUCTO = 20


class ResenaError(Exception):
    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


def compro_el_producto(usuario, producto):
    """True si lo recibio en un pedido hecho con su cuenta. Es lo unico que se puede comprobar."""
    return DetallePedido.objects.filter(
        producto=producto, pedido__cliente=usuario, pedido__estado=Pedido.Estado.ENTREGADO,
    ).exists()


def limpiar_fotos(archivos):
    """Comprueba que sean imagenes de verdad (Pillow) y de tamaño aceptable. Lanza ResenaError."""
    archivos = [archivo for archivo in archivos if archivo]
    if len(archivos) > FotoResena.MAXIMO:
        raise ResenaError(f'Puedes subir hasta {FotoResena.MAXIMO} fotos.')
    campo = forms.ImageField()
    for archivo in archivos:
        try:
            campo.clean(archivo)
            validar_imagen(archivo)
        except ValidationError as error:
            raise ResenaError(f'"{archivo.name}": {" ".join(error.messages)}') from error
        archivo.seek(0)
    return archivos


@transaction.atomic
def guardar_resena(usuario, producto, estrellas, comentario, fotos=None):
    """Crea la reseña del cliente o cambia la que ya tenia. Siempre vuelve a revision antes de publicarse.

    Si trae `fotos` (ya revisadas con `limpiar_fotos`), reemplazan a las anteriores.
    """
    resena = _guardar_texto(usuario, producto, estrellas, comentario)
    if fotos:
        for anterior in resena.fotos.all():
            anterior.delete()
        for orden, archivo in enumerate(fotos):
            FotoResena.objects.create(resena=resena, imagen=archivo, orden=orden)
    return resena


def _guardar_texto(usuario, producto, estrellas, comentario):
    try:
        estrellas = int(estrellas)
    except (TypeError, ValueError):
        estrellas = 0
    comentario = ' '.join((comentario or '').split())
    if not 1 <= estrellas <= 5:
        raise ResenaError('Elige de 1 a 5 estrellas.')
    if len(comentario) < 10:
        raise ResenaError('Cuenta un poco más sobre el producto (al menos 10 letras).')
    resena, _ = Resena.objects.update_or_create(
        producto=producto, usuario=usuario,
        defaults={
            'tienda_id': producto.tienda_id, 'estrellas': estrellas, 'comentario': comentario[:1000],
            'estado': Estado.PENDIENTE, 'compra_verificada': compro_el_producto(usuario, producto),
        },
    )
    return resena


def publicadas(producto):
    return list(
        Resena.objects.filter(producto=producto, estado=Estado.APROBADA).select_related('usuario')
        .prefetch_related('fotos')[:PUBLICADAS_POR_PRODUCTO]
    )


def resumen(producto):
    """Cantidad y promedio de las reseñas publicadas; promedio None si no hay ninguna."""
    datos = Resena.objects.filter(producto=producto, estado=Estado.APROBADA).aggregate(
        total=Count('id'), promedio=Avg('estrellas'),
    )
    promedio = round(datos['promedio'], 1) if datos['promedio'] is not None else None
    return {'total': datos['total'], 'promedio': promedio}


def resena_de(usuario, producto):
    if not usuario.is_authenticated:
        return None
    return Resena.objects.filter(producto=producto, usuario=usuario).first()


# --- Preguntas y respuestas -----------------------------------------------------------

# Preguntas de un mismo cliente en una hora: nadie llena de preguntas a una tienda.
PREGUNTAS_POR_HORA = 5
UNA_HORA = 60 * 60


def preguntar(usuario, producto, texto):
    """El cliente pregunta; la tienda recibe un correo y la responde en el panel. Se publica al responderla."""
    texto = ' '.join((texto or '').split())
    if len(texto) < 10:
        raise ResenaError('Escribe tu pregunta (al menos 10 letras).')
    if limites.bloqueado('pregunta', usuario.pk, maximo=PREGUNTAS_POR_HORA, ventana=UNA_HORA):
        raise ResenaError('Hiciste varias preguntas seguidas. Espera un rato y vuelve a intentarlo.')
    limites.anotar_intento('pregunta', usuario.pk)
    pregunta = Pregunta.objects.create(
        tienda_id=producto.tienda_id, producto=producto, usuario=usuario, texto=texto[:500],
    )

    def avisar():
        contexto = {
            'pregunta': pregunta, 'producto': producto, 'tienda': producto.tienda,
            'enlace_panel': url_absoluta(reverse('admin:opiniones_pregunta_change', args=[pregunta.pk])),
        }
        correo.enviar(f'Pregunta sobre {producto.nombre}', 'tienda_pregunta', contexto, correos_de_la_tienda(producto.tienda))
    transaction.on_commit(avisar)
    return pregunta


@transaction.atomic
def responder(pregunta, respuesta, usuario=None):
    """La tienda responde: la pregunta se publica y al cliente le llega un correo (solo la primera vez)."""
    pregunta = Pregunta.objects.select_for_update().select_related('producto__tienda', 'usuario').get(pk=pregunta.pk)
    respuesta = (respuesta or '').strip()
    if not respuesta:
        raise ResenaError('Escribe la respuesta.')
    primera_vez = not pregunta.respondida_en
    pregunta.respuesta = respuesta[:1000]
    pregunta.estado = Pregunta.Estado.PUBLICADA
    pregunta.respondida_en = pregunta.respondida_en or timezone.now()
    pregunta.respondida_por = usuario
    pregunta.save()
    if primera_vez and pregunta.usuario.email:
        producto = pregunta.producto
        contexto = {
            'pregunta': pregunta, 'producto': producto, 'tienda': producto.tienda,
            'enlace': url_absoluta(producto.get_absolute_url() + '#preguntas'),
        }
        transaction.on_commit(lambda: correo.enviar(
            f'Respondieron tu pregunta sobre {producto.nombre}', 'cliente_respuesta', contexto, [pregunta.usuario.email],
        ))
    return pregunta


def ocultar_preguntas(consulta):
    return consulta.update(estado=Pregunta.Estado.OCULTA)


PREGUNTAS_POR_PRODUCTO = 20


def preguntas_publicadas(producto):
    return list(
        Pregunta.objects.filter(producto=producto, estado=Pregunta.Estado.PUBLICADA)
        .select_related('usuario').order_by('-respondida_en', '-id')[:PREGUNTAS_POR_PRODUCTO]
    )


def preguntas_sin_responder(usuario, producto):
    """Las que el cliente hizo y todavia esperan respuesta: solo las ve el."""
    if not usuario.is_authenticated:
        return []
    return list(Pregunta.objects.filter(producto=producto, usuario=usuario, estado=Pregunta.Estado.PENDIENTE))
