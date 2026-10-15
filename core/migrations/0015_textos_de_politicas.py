from django.db import migrations

# Texto estandar de las politicas, pedido por el dueño el 2026-10-14. Solo se llenan (y publican) las paginas
# que siguen vacias: si el dueño ya escribio una, se respeta. Los plazos salen de la configuracion actual;
# si despues se cambian alli, hay que corregir el texto en Panel > Paginas informativas.


def _contacto(config):
    """Como escribirle al sitio, con los datos de Configuracion general."""
    if config is None:
        return 'usando los datos de contacto que aparecen al pie de esta página'
    medios = []
    if config.correo:
        medios.append(f'al correo {config.correo}')
    if config.whatsapp:
        medios.append(f'por WhatsApp al {config.whatsapp}')
    elif config.telefono:
        medios.append(f'al teléfono {config.telefono}')
    if not medios:
        return 'usando los datos de contacto que aparecen al pie de esta página'
    return ' o '.join(medios)


def _textos(config):
    sitio = config.nombre if config and config.nombre else 'Multimix RD'
    dias = config.dias_devolucion if config else 7
    horas = config.horas_vencimiento_pedido if config else 48
    contacto = _contacto(config)

    privacidad = f"""En {sitio} cuidamos los datos que nos confías. Esta política explica qué datos recogemos, para qué los usamos, con quién los compartimos y cómo puedes ejercer tus derechos, conforme a la Ley 172-13 sobre Protección de Datos de Carácter Personal de la República Dominicana.

1. Quién es responsable
{sitio} administra este sitio, donde varias tiendas independientes venden sus productos. Cada tienda recibe y usa los datos de los pedidos que le haces a ella para atenderlos.

2. Qué datos recogemos
- Al crear tu cuenta: tu nombre, tu correo, tu teléfono y tu contraseña. La contraseña se guarda cifrada: nadie puede leerla, ni siquiera nosotros.
- Al hacer un pedido: los productos, la forma de entrega y de pago y, si pides envío, tu zona, sector, calle y referencia.
- Si pagas por transferencia: la referencia y la imagen del comprobante que subas.
- Datos técnicos: la dirección IP desde la que haces un pedido o inicias sesión, para prevenir abusos y fraudes.
- Las reseñas, favoritos y solicitudes de devolución que hagas.
No recogemos ni guardamos datos de tarjetas de crédito o débito.

3. Para qué los usamos
- Crear y mantener tu cuenta y mostrarte tus pedidos.
- Preparar, entregar y cobrar tus pedidos, y avisarte por correo de cada cambio.
- Atender tus consultas, devoluciones y reclamaciones.
- Proteger el sitio contra fraudes, spam y accesos no autorizados.
- Cumplir las obligaciones que nos imponga la ley.
No vendemos ni alquilamos tus datos y no te enviamos publicidad sin tu permiso.

4. Con quién los compartimos
- Con la tienda a la que le compras: recibe tu nombre, teléfono, correo, dirección y los datos del pedido para atenderlo. Una tienda no ve los pedidos que haces en otras.
- Con los proveedores que nos prestan servicios técnicos (alojamiento del sitio, almacenamiento de imágenes y envío de correos), que solo pueden usarlos para prestar ese servicio.
- Con las autoridades, cuando una ley o una orden judicial lo exija.

5. Cookies
Usamos solo las cookies necesarias para que el sitio funcione: mantener tu sesión iniciada, recordar tu carrito y proteger los formularios. No usamos cookies de publicidad ni de seguimiento de terceros.

6. Cuánto tiempo los guardamos
Guardamos los datos de tu cuenta mientras esté activa. Los pedidos se conservan el tiempo que exigen las normas comerciales y fiscales, aunque cierres tu cuenta.

7. Tus derechos
Puedes ver tus datos y corregir tu nombre, teléfono y dirección en "Mi cuenta", en "Mis datos". También puedes pedirnos el acceso, la corrección o la eliminación de tus datos, u oponerte a su uso, escribiéndonos {contacto}. Te responderemos en un plazo máximo de 10 días hábiles.

8. Seguridad
El sitio usa conexión cifrada (HTTPS), las contraseñas se guardan cifradas y el acceso al panel de las tiendas está restringido. Cuida tu contraseña y no la compartas con nadie.

9. Cambios en esta política
Si cambiamos esta política, publicaremos la nueva versión en esta página con su fecha de actualización."""

    entregas = f"""Esta política explica cómo recibes los pedidos que haces en las tiendas de {sitio}. Cada tienda prepara y entrega sus propios pedidos.

1. Formas de entrega
- Retiro en tienda: recoges tu pedido en la dirección que indica la tienda, cuando te avise que está listo.
- Envío a domicilio: la tienda lleva tu pedido a la dirección que indicaste, solo dentro de las zonas de envío que tenga habilitadas. Las zonas y sus costos están en "Envíos y retiros" de cada tienda.

2. Costo del envío
El costo depende de la zona y se muestra en el resumen antes de confirmar el pedido. Se suma al total de los productos.

3. Tiempo de entrega
La tienda prepara tu pedido después de confirmar el pago (o después de confirmar el pedido, si pagas contra entrega) y te indica cuándo puedes recogerlo o cuándo llegará. Los tiempos son estimados y pueden extenderse por días feriados, clima, alta demanda u otras causas fuera del control de la tienda; si eso ocurre, la tienda te avisará.

4. Seguimiento
Puedes ver el estado de tu pedido en "Mi cuenta" y te avisamos por correo cada vez que cambia: pagado, en preparación, listo para recoger o enviado, en reparto y entregado. Si la tienda registra un número de guía, lo verás en tu pedido.

5. Al recibir
- Revisa el paquete al recibirlo. Si está dañado, abierto o incompleto, díselo al repartidor y escribe a la tienda ese mismo día con tu número de pedido y fotos.
- Debe haber una persona mayor de edad para recibir el pedido en la dirección indicada.
- Si pagas contra entrega, ten listo el monto en efectivo.

6. Si no se puede entregar
Si la dirección es incorrecta o no hay nadie para recibir, la tienda te contactará por teléfono o WhatsApp para coordinar un nuevo intento, que puede tener un costo adicional. Por eso el teléfono es obligatorio al hacer el pedido.

7. Pedidos sin pagar
Los pedidos que sigan pendientes de pago {horas} horas después de hechos se cancelan automáticamente. Si pagas por transferencia, avísalo y sube el comprobante cuanto antes para que la tienda lo verifique dentro de ese plazo."""

    devoluciones = f"""Queremos que estés conforme con tu compra. Esta política se aplica a todas las tiendas de {sitio}, sin perjuicio de los derechos que te reconoce la Ley 358-05 General de Protección de los Derechos del Consumidor o Usuario.

1. Plazo
Puedes solicitar un cambio o una devolución dentro de los {dias} días siguientes a la entrega de tu pedido.

2. Cómo solicitarla
Entra a "Mi cuenta", abre el pedido y usa "Solicitar devolución". Indica qué productos quieres cambiar o devolver y el motivo. La tienda revisa la solicitud y te responde por correo y en la misma página del pedido. No envíes productos antes de que la tienda apruebe la solicitud.

3. Condiciones
- El producto debe estar sin usar, completo, con sus etiquetas, sellos y empaque original, y con los accesorios o regalos que trajo.
- Por higiene y seguridad, no se aceptan devoluciones de productos de cuidado personal, cosméticos, suplementos o alimentos que se hayan abierto o tengan el sello roto, salvo que tengan un defecto de fábrica o estén vencidos.
- No se aceptan productos dañados por mal uso, golpes, humedad o por no seguir las instrucciones del fabricante.

4. Productos defectuosos o equivocados
Si recibes un producto defectuoso, vencido, dañado en el transporte o distinto al que pediste, avísale a la tienda cuanto antes, con fotos. En estos casos la tienda cubre el costo del cambio o del retiro y te ofrece cambiar el producto o devolverte el dinero.

5. Cambios por preferencia
Si el producto está en perfectas condiciones y lo quieres cambiar por otro (por ejemplo, otro tono o tamaño), el envío del cambio corre por tu cuenta. Si el nuevo producto tiene otro precio, pagas o recibes la diferencia.

6. Después de aprobada
Coordina con la tienda la entrega del producto, en la tienda o con su mensajero. Cuando la tienda lo reciba y verifique su estado, te entrega el cambio o te devuelve el dinero según la política de reembolsos."""

    reembolsos = f"""1. Cuándo hay reembolso
- Si cancelas un pedido antes de pagarlo no hay nada que devolver: el pedido se anula. Puedes cancelarlo tú mismo desde la página del pedido mientras esté pendiente y no hayas avisado la transferencia.
- Si ya pagaste y la tienda no puede entregarte un producto (por ejemplo, porque se agotó), te devuelve lo que pagaste por él, o el pedido completo si así lo prefieres.
- Si se aprueba una devolución según la política de cambios y devoluciones.

2. Qué se devuelve
El precio que pagaste por los productos, con el descuento que se haya aplicado. El costo de envío se devuelve cuando el pedido no se entregó o cuando la devolución se debe a un error o a un defecto.

3. Cómo se devuelve
- Pagos por transferencia: con una transferencia a una cuenta bancaria a nombre de quien hizo el pedido. La tienda te pedirá el banco, el tipo y el número de la cuenta.
- Pagos en efectivo: en efectivo en la tienda o por transferencia, según acuerdes con la tienda.

4. Plazo
La tienda hace el reembolso dentro de los 10 días hábiles siguientes a la aprobación o a la recepción del producto devuelto. Después, tu banco puede tardar unos días más en reflejarlo.

5. Aviso
Cuando el reembolso se completa, tu pedido pasa a "Reembolsado" y te avisamos por correo. Si tienes dudas, escribe a la tienda con tu número de pedido o escríbenos {contacto}."""

    garantias = f"""1. Productos originales
Las tiendas de {sitio} venden productos nuevos y originales, con la garantía que ofrezca su fabricante. Cuando un producto tenga una garantía especial, la tienda la indica en su descripción.

2. Qué cubre
La garantía cubre los defectos de fabricación y los productos que no correspondan a lo que se describe en su publicación. Ante un defecto, la tienda cambia el producto o te devuelve el dinero, según corresponda.

3. Qué no cubre
- El desgaste normal por el uso.
- Daños por mal uso, golpes, caídas, humedad, almacenamiento inadecuado o por no seguir las instrucciones del fabricante.
- Productos modificados o reparados por terceros.
- Resultados que dependen de cada persona, como el efecto de un cosmético o de un suplemento, salvo lo que garantice expresamente el fabricante.

4. Fecha de vencimiento
Las tiendas no venden productos vencidos. Revisa la fecha al recibir tu pedido: si un producto llega vencido, tienes derecho a cambiarlo o a que te devuelvan el dinero.

5. Cómo reclamar
Escribe a la tienda con tu número de pedido, una descripción del problema y fotos o un video. La tienda puede pedirte el producto para revisarlo. Si no te responde, escríbenos {contacto} y te ayudamos. También puedes acudir a Pro Consumidor."""

    pagos = f"""Todos los precios están en pesos dominicanos (RD$). Antes de confirmar tu pedido ves el total: productos, descuentos y costo de envío.

1. Transferencia o depósito bancario
Al hacer tu pedido verás las cuentas bancarias de la tienda. Transfiere el total y luego, en la página de tu pedido, pulsa "Ya hice la transferencia" y sube la foto o captura del comprobante. El pedido queda pagado cuando la tienda verifica que el dinero llegó, y te avisamos por correo. Si el comprobante no corresponde, te lo indicamos para que lo revises.

2. Efectivo al recoger
Pagas en efectivo cuando retiras tu pedido en la tienda.

3. Efectivo contra entrega
Pagas en efectivo al recibir tu pedido a domicilio. Solo está disponible en las tiendas que lo ofrecen: si lo ofrece, lo verás entre las formas de pago al elegir envío a domicilio. Ten el monto exacto, porque el repartidor puede no llevar cambio.

4. Tarjeta de crédito o débito
Por ahora no recibimos pagos con tarjeta en el sitio. Cuando se habilite, el pago se hará en la página segura del banco: ni {sitio} ni las tiendas verán ni guardarán los datos de tu tarjeta.

5. Plazo para pagar
Los pedidos que sigan pendientes de pago {horas} horas después de hechos se cancelan automáticamente.

6. Seguridad
Paga solo a las cuentas que aparecen en el sitio para tu pedido. Nadie de {sitio} ni de las tiendas te pedirá contraseñas, códigos de verificación ni datos de tu tarjeta por WhatsApp, teléfono o correo.

7. Comprobante
La constancia del pedido que descargas del sitio no es un comprobante fiscal. Si necesitas factura con número de comprobante fiscal (NCF), pídesela a la tienda antes de pagar."""

    lineas = []
    if config is not None:
        if config.correo:
            lineas.append(f'Correo: {config.correo}')
        if config.telefono:
            lineas.append(f'Teléfono: {config.telefono}')
        if config.whatsapp:
            lineas.append(f'WhatsApp: {config.whatsapp}')
        if config.horario:
            lineas.append(f'Horario: {config.horario}')
    atencion = '\n'.join(lineas) if lineas else 'Usa los datos de contacto que aparecen al pie de esta página.'

    contacto_pagina = f"""{sitio} es un sitio de comercio en línea que reúne tiendas de vendedores independientes de la República Dominicana. Cada tienda publica sus productos y precios, atiende sus pedidos y responde por ellos.

Atención al cliente del sitio
{atencion}

Las tiendas
Cada tienda tiene sus propios datos de contacto (WhatsApp, teléfono, correo y dirección para retiros), que aparecen al pie de sus páginas y en la página de cada pedido. Para consultas sobre un pedido, escribe primero a la tienda donde compraste, con tu número de pedido.

Si la tienda no te responde o no llegan a un acuerdo, escríbenos y te ayudaremos a resolverlo. También puedes acudir al Instituto Nacional de Protección de los Derechos del Consumidor (Pro Consumidor)."""

    return {
        'privacidad': privacidad,
        'entregas': entregas,
        'cambios-y-devoluciones': devoluciones,
        'reembolsos': reembolsos,
        'garantias': garantias,
        'metodos-de-pago': pagos,
        'contacto': contacto_pagina,
    }


def escribir_politicas(apps, schema_editor):
    Pagina = apps.get_model('core', 'PaginaInformativa')
    Configuracion = apps.get_model('core', 'ConfiguracionTienda')
    for slug, texto in _textos(Configuracion.objects.filter(pk=1).first()).items():
        pagina = Pagina.objects.filter(slug=slug).first()
        if pagina is None or pagina.contenido.strip():
            continue
        pagina.contenido = texto
        pagina.publicada = True
        pagina.save(update_fields=['contenido', 'publicada', 'actualizado'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_paginas_iniciales'),
    ]

    operations = [
        migrations.RunPython(escribir_politicas, migrations.RunPython.noop),
    ]
