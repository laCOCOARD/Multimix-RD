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
        extras.append(f'*Dirección:* {pedido.direccion}')
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


def enlace_al_cliente(pedido):
    """Para el panel: abre el chat con el cliente."""
    mensaje = f'Hola {pedido.nombre}, te escribimos por tu pedido {pedido.numero}.'
    return construir_enlace(telefono_internacional(pedido.telefono), mensaje)
