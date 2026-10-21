"""Mensaje y enlaces de WhatsApp de un pedido."""
from urllib.parse import quote

from core.telefonos import formatear_telefono, normalizar_whatsapp, telefono_internacional
from core.templatetags.moneda import formatear_monto


def construir_mensaje(pedido):
    """Texto del pedido para enviar a la tienda. Usa el formato de negritas de WhatsApp (*texto*)."""
    lineas = [
        f'*Nuevo pedido {pedido.numero}*',
        '',
        f'*Cliente:* {pedido.nombre}',
        f'*Teléfono:* {formatear_telefono(pedido.telefono)}',
    ]
    if pedido.correo:
        lineas.append(f'*Correo:* {pedido.correo}')

    lineas += ['', '*Productos:*']
    for detalle in pedido.detalles.all():
        lineas.append(f'• {detalle.cantidad} × {detalle.nombre_producto} = {formatear_monto(detalle.subtotal)}')

    lineas += ['', f'*Subtotal:* {formatear_monto(pedido.subtotal)}']
    if pedido.descuento > 0:
        lineas.append(f'*Cupón {pedido.codigo_cupon}:* -{formatear_monto(pedido.descuento)}')
    if pedido.impuesto > 0:
        lineas.append(f'*{pedido.etiqueta_impuesto}:* {formatear_monto(pedido.impuesto)}')
    if pedido.recoge_en_tienda:
        lineas.append('*Entrega:* Recoger en tienda')
    else:
        zona = f' ({pedido.zona.nombre})' if pedido.zona else ''
        lineas.append(f'*Envío{zona}:* {formatear_monto(pedido.costo_envio)}')
    lineas.append(f'*Total:* {formatear_monto(pedido.total)}')

    lineas += ['', f'*Forma de pago:* {pedido.get_metodo_pago_display()}']
    if pedido.paga_por_transferencia and pedido.transferencia_realizada:
        aviso = '✅ Ya hice la transferencia'
        if pedido.referencia_transferencia:
            aviso += f' (Ref.: {pedido.referencia_transferencia})'
        lineas.append(aviso)

    extras = []
    if not pedido.recoge_en_tienda:
        extras.append(f'*Dirección:* {pedido.direccion_completa}')
        if pedido.referencia:
            extras.append(f'*Referencia:* {pedido.referencia}')
    if pedido.notas_cliente:
        extras.append(f'*Notas:* {pedido.notas_cliente}')
    if extras:
        lineas += [''] + extras

    return '\n'.join(lineas)


def construir_enlace(numero, mensaje):
    """https://wa.me/<numero>?text=<mensaje codificado>. El numero va solo con digitos y con codigo de pais."""
    return f'https://wa.me/{normalizar_whatsapp(numero)}?text={quote(mensaje, safe="")}'


def enlace_del_pedido(pedido, numero_tienda):
    return construir_enlace(numero_tienda, construir_mensaje(pedido))


MENSAJES_DE_ESTADO = {
    'pendiente': 'recibimos tu pedido {numero}. Te avisamos cuando confirmemos el pago.',
    'pagado': 'confirmamos el pago de tu pedido {numero}. Ya lo estamos preparando.',
    'preparando': 'estamos preparando tu pedido {numero}.',
    'listo': 'tu pedido {numero} está listo para recoger{donde}.',
    'enviado': 'tu pedido {numero} va en camino.',
    'en_reparto': 'tu pedido {numero} está en reparto: llega pronto.',
    'entregado': 'tu pedido {numero} fue entregado. ¡Gracias por tu compra!',
    'cancelado': 'tu pedido {numero} fue cancelado. Si es un error, respóndenos por aquí.',
    'reembolsado': 'registramos el reembolso de tu pedido {numero}.',
}


def mensaje_de_estado(pedido, enlace):
    """Texto para avisarle al cliente, a mano desde el panel, en que esta su pedido."""
    donde = f' en {pedido.tienda.direccion_tienda}' if pedido.tienda.direccion_tienda else ''
    plantilla = MENSAJES_DE_ESTADO.get(pedido.estado, 'tu pedido {numero} ahora está: ' + pedido.get_estado_display())
    saludo = f'Hola {pedido.nombre}, te escribimos de {pedido.tienda.nombre}: '
    lineas = [saludo + plantilla.format(numero=pedido.numero, donde=donde)]
    if pedido.numero_seguimiento and pedido.estado in ('enviado', 'en_reparto'):
        lineas.append(f'Seguimiento: {pedido.numero_seguimiento}')
    lineas.append(f'Míralo aquí: {enlace}')
    return '\n'.join(lineas)


def enlace_aviso_de_estado(pedido, enlace):
    return construir_enlace(telefono_internacional(pedido.telefono), mensaje_de_estado(pedido, enlace))


def enlace_al_cliente(pedido):
    """Para el panel: abre el chat con el cliente."""
    mensaje = f'Hola {pedido.nombre}, te escribimos por tu pedido {pedido.numero}.'
    return construir_enlace(telefono_internacional(pedido.telefono), mensaje)
