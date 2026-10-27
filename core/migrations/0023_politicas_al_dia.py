from django.db import migrations

# Politicas al dia (pedido del dueño el 2026-10-27). Desde el 2026-10-26 cada tienda cobra en sus cuentas y el aviso de
# transferencia lleva el comprobante; en la Fase 2 llegaron las solicitudes de tiendas y en la Fase 4 la medicion sin
# datos personales. Solo se cambian frases del texto estandar de core/0015 que sigan tal cual: lo que el dueño haya
# reescrito en el panel se respeta. Las condiciones para vendedores son nuevas y salen de las reglas reales del sitio
# (planes, mensualidad, dias de aviso y de gracia de la configuracion actual); el dueño las ajusta en el panel.
# El sitio todavia no esta registrado (2026-10-27): no se publica razon social ni RNC.

PAGOS_ANTES = (
    'Transfiere el total y luego, en la página de tu pedido, pulsa "Ya hice la transferencia" y sube la foto o captura '
    'del comprobante.'
)
PAGOS_AHORA = (
    'Transfiere el total y sube la foto o captura del comprobante: al confirmar el pedido o después, en la página de tu '
    'pedido. Sin comprobante la tienda no puede confirmar tu pago.'
)

PRIVACIDAD_DATOS_ANTES = '- Las reseñas, favoritos y solicitudes de devolución que hagas.'
PRIVACIDAD_DATOS_AHORA = (
    '- Las reseñas, preguntas, favoritos y solicitudes de devolución que hagas.\n'
    '- Si pides abrir una tienda: tu nombre, el de tu negocio, tu correo, tu teléfono, lo que vendes y tus redes. Solo '
    'los ve la administración del sitio, para revisar tu solicitud y contactarte; no se publican.'
)
PRIVACIDAD_COOKIES_ANTES = (
    'Usamos solo las cookies necesarias para que el sitio funcione: mantener tu sesión iniciada, recordar tu carrito y '
    'proteger los formularios. No usamos cookies de publicidad ni de seguimiento de terceros.'
)
PRIVACIDAD_COOKIES_AHORA = (
    PRIVACIDAD_COOKIES_ANTES + ' Tu navegador también recuerda qué videos de las tiendas ya viste, sin enviarlo al '
    'sitio.\nPara saber cómo se usa el sitio contamos cuántas veces se visitan las tiendas y los productos, cuántas '
    'búsquedas se hacen y cuántos productos se agregan al carrito. Son solo totales por día: no guardamos quién lo hizo, '
    'su dirección IP ni lo que escribió en el buscador.'
)

ENTREGAS_ANTES = 'Los tiempos son estimados y pueden extenderse'
ENTREGAS_AHORA = (
    'Antes de confirmar ves una fecha estimada, calculada con los días hábiles (de lunes a sábado) que indica la '
    'tienda para tu zona o para el retiro. Los tiempos son estimados y pueden extenderse'
)


def _telefono(numero):
    digitos = ''.join(c for c in numero if c.isdigit())
    if len(digitos) == 11 and digitos.startswith('1'):
        digitos = digitos[1:]
    return f'{digitos[:3]}-{digitos[3:6]}-{digitos[6:]}' if len(digitos) == 10 else numero


def _contacto(config, sitio):
    lineas = [f'Nombre comercial: {sitio}']
    if config is not None:
        if config.correo:
            lineas.append(f'Correo: {config.correo}')
        if config.telefono:
            lineas.append(f'Teléfono: {_telefono(config.telefono)}')
        if config.whatsapp:
            lineas.append(f'WhatsApp: {_telefono(config.whatsapp)}')
        if config.horario:
            lineas.append(f'Horario: {config.horario}')
    return f"""{sitio} es un sitio de comercio en línea que reúne tiendas de vendedores independientes de la República Dominicana. Cada tienda publica sus productos y precios, cobra y atiende sus pedidos y responde por ellos.

Atención al cliente del sitio
{chr(10).join(lineas)}

Las tiendas
Cada tienda tiene sus propios datos de contacto (WhatsApp, teléfono, correo y dirección para retiros), que aparecen en sus páginas, en la ficha de cada producto ("Vendido por") y en la página de cada pedido. Para consultas sobre un pedido, escribe primero a la tienda donde compraste, con tu número de pedido.

Si la tienda no te responde o no llegan a un acuerdo, escríbenos y te ayudaremos a resolverlo. También puedes acudir al Instituto Nacional de Protección de los Derechos del Consumidor (Pro Consumidor).

Vender en {sitio}
Si tienes un negocio y quieres abrir tu tienda, entra a "Vende en {sitio}" y envía tu solicitud."""


def _condiciones(config, sitio):
    aviso = config.dias_aviso_mensualidad if config else 3
    gracia = config.dias_de_gracia if config else 4
    return f"""Estas condiciones se aplican a las tiendas que venden en {sitio}, junto con los términos del sitio y las políticas publicadas (entregas, cambios y devoluciones, reembolsos, garantías y privacidad).

1. Cómo se abre una tienda
Quien quiere vender envía su solicitud desde "Vende en {sitio}". La administración la revisa y, si la aprueba, crea la tienda y le da acceso a su panel. Enviar la solicitud no garantiza que se apruebe.

2. Lo que hace cada tienda
- Publica productos nuevos y originales, con su precio en pesos dominicanos, una descripción fiel y fotos reales, y mantiene al día su disponibilidad.
- Cobra a sus clientes en sus propias cuentas o en efectivo, y confirma cada pago en su panel.
- Prepara y entrega sus pedidos en las formas y zonas que configure, y mantiene a sus clientes al tanto del estado del pedido.
- Atiende las consultas, los cambios, las devoluciones y los reembolsos según las políticas del sitio.
- Usa los datos de sus clientes solo para atender sus pedidos y no los comparte con nadie más.

3. Lo que no se puede vender
Productos ilegales, falsificados, robados, vencidos o peligrosos, ni los que necesiten permisos que la tienda no tenga.

4. El plan y los pagos al sitio
- Cada tienda tiene un plan, que asigna la administración: una mensualidad, una cantidad de pedidos incluidos al mes y un porcentaje sobre lo vendido en los pedidos que pasen de ese límite (productos menos descuentos, sin el envío). El plan de la tienda y sus montos se ven en su panel.
- La mensualidad vence el día 1 de cada mes y el cargo aparece una semana antes. El porcentaje de los pedidos de más del mes anterior se calcula y vence el día 1.
- La tienda paga por transferencia a las cuentas del sitio que aparecen en su panel y sube el comprobante allí; la administración lo confirma.
- Recibe avisos por correo {aviso} días antes del vencimiento, el día que vence y el último día de gracia.

5. Falta de pago
Si un pago sigue pendiente {gracia} días después de vencido, la tienda se cierra: sus productos dejan de mostrarse hasta que pague y la administración la habilite. Sus datos y sus pedidos se conservan.

6. Anuncios y videos
Según su plan, la tienda puede anunciar productos y publicar anuncios o videos en la portada. Salen cuando la administración los aprueba; si se cambia su contenido, vuelven a revisión. Siempre se muestran como anuncios.

7. Suspensión
La administración puede ocultar productos o suspender una tienda que incumpla estas condiciones, venda productos prohibidos o acumule reclamos graves de sus clientes.

8. Cambios
Si estas condiciones cambian, publicaremos la nueva versión en esta página."""


def actualizar(apps, schema_editor):
    Pagina = apps.get_model('core', 'PaginaInformativa')
    Configuracion = apps.get_model('core', 'ConfiguracionTienda')
    config = Configuracion.objects.filter(pk=1).first()
    sitio = config.nombre if config and config.nombre else 'Multimix RD'

    cambios = {
        'metodos-de-pago': [(PAGOS_ANTES, PAGOS_AHORA)],
        'privacidad': [(PRIVACIDAD_DATOS_ANTES, PRIVACIDAD_DATOS_AHORA), (PRIVACIDAD_COOKIES_ANTES, PRIVACIDAD_COOKIES_AHORA)],
        'entregas': [(ENTREGAS_ANTES, ENTREGAS_AHORA)],
    }
    for slug, reemplazos in cambios.items():
        pagina = Pagina.objects.filter(slug=slug).first()
        if pagina is None:
            continue
        texto = pagina.contenido
        for antes, ahora in reemplazos:
            if antes in texto and ahora not in texto:
                texto = texto.replace(antes, ahora, 1)
        if texto != pagina.contenido:
            pagina.contenido = texto
            pagina.save(update_fields=['contenido', 'actualizado'])

    # Contacto: se rehace solo si sigue siendo el texto estandar (sin cambios del dueño).
    contacto = Pagina.objects.filter(slug='contacto').first()
    if contacto and (not contacto.contenido.strip() or 'es un sitio de comercio en línea que reúne tiendas de vendedores '
                     'independientes de la República Dominicana. Cada tienda publica sus productos y precios, atiende sus '
                     'pedidos y responde por ellos.' in contacto.contenido):
        contacto.contenido = _contacto(config, sitio)
        contacto.save(update_fields=['contenido', 'actualizado'])

    ultimo = Pagina.objects.order_by('-orden').values_list('orden', flat=True).first() or 0
    Pagina.objects.get_or_create(slug='condiciones-para-vendedores', defaults={
        'titulo': 'Condiciones para vendedores', 'contenido': _condiciones(config, sitio), 'publicada': True,
        'orden': ultimo + 1,
    })


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_conteos_diarios'),
    ]

    operations = [
        migrations.RunPython(actualizar, migrations.RunPython.noop),
    ]
