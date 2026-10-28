# Catalogo, carrito y pedidos

Decisiones tomadas en Multimix RD (movidas desde CLAUDE.md el 2026-10-28). Leelas antes de tocar esta parte del proyecto.

- Subcategorias: `Categoria.padre`, solo dos niveles (lo valida `clean` y el panel solo ofrece principales). La
  pagina de una categoria principal lista tambien los productos de sus subcategorias, y `categorias_de` devuelve
  cada subcategoria debajo de su principal.
- Variantes (talla, color, tamaño): cada variante sigue siendo un `Producto` con su SKU, precio, disponibilidad y
  fotos, agrupado con `variante_de` (un solo nivel, misma tienda: lo valida `clean`), `nombre_variante` y, en el
  principal, `tipo_variante`. Carrito, pedidos y stock no cambian. Los listados (`catalogo.services._base`) muestran
  solo el principal (`sin_variantes_repetidas`; si el principal no se vende, salen sueltas) con "N opciones"
  (`con_variantes`, dentro de `para_listado`), y la ficha ofrece las opciones (`opciones_de`). La importacion lee
  `variante_de` con el SKU del principal dentro de la tienda.
- Galeria de la ficha: todas las fotos en una pista con scroll-snap (se desliza con el dedo, puntos en el celular)
  y las miniaturas la mueven (`tienda.js`).
- Reporte de ventas (`pedidos.reportes`, Panel > Pedidos > Reporte de ventas) con descarga CSV, limitado a las
  tiendas del usuario. El historial de acciones del panel (LogEntry) lo ve solo el superusuario; los cambios de
  estado de cada pedido quedan en `EventoPedido` con el usuario que los hizo.
- Checkout en una sola pantalla (pedido del dueño el 2026-10-19; antes eran 4 pasos con una pantalla de revision):
  datos, entrega, pago, notas y terminos a la vista, con el total junto al boton de confirmar. Un solo formulario y
  un solo POST; `checkout.js` muestra los campos segun entrega y pago, pide los totales y al confirmar lleva al
  primer campo que falte. El cliente debe aceptar los terminos (`acepta_terminos`).
- La entrega a domicilio pide zona (de las que la tienda tenga), sector, calle y referencia.
- La confirmacion ya no abre WhatsApp ni lo pide: solo ofrece un boton para escribirle a la tienda.
- Avisos del pedido por WhatsApp (docs/WHATSAPP.md): en el detalle del pedido del panel, "Avisar al cliente por
  WhatsApp" abre wa.me con el mensaje del estado (`pedidos.whatsapp.mensaje_de_estado`). Automatico y opcional con
  la WhatsApp Cloud API de Meta (`pedidos/whatsapp_api.py`, `WHATSAPP_TOKEN` + `WHATSAPP_NUMERO_ID`, plantilla
  aprobada `estado_pedido` con 4 variables): solo si el cliente lo acepto en el checkout (`Pedido.avisos_whatsapp`;
  sin configurar no se ofrece) y sale con los correos de `pedidos.avisos`. Nunca lanza.
- Ficha del producto (Fase 3, 2026-10-27): galeria fija en pantallas anchas; a la derecha la compra, "Vendido por"
  (la tienda con "Ver la tienda" y su WhatsApp como "Preguntar", contacto secundario) y entrega y pago tal como los
  ofrece el checkout (`pedidos.services.formas_de_pago`: sin cuentas activas no dice transferencia; sin zonas, "solo
  retiro"); debajo, descripcion y "Detalles" (marca, categoria, SKU, disponibilidad). Sin mensajes de urgencia por
  existencias: la cantidad solo sale con inventario y `mostrar_cantidad_exacta`, en tono neutro. La tarjeta en el
  checkout dice "Todavia no disponible" (sin plazos).
- Disponibilidad comercial: el negocio no cuenta unidades fiables, asi que cada producto se vende segun
  `Producto.disponibilidad` (disponible, bajo pedido, agotado, temporalmente no disponible). El inventario es
  opcional por producto (`controla_stock`, apagado por defecto): solo entonces valen `stock_almacen` y
  `stock_reservado`. `estado_venta` es lo que ve el cliente y `limite_compra` cuantas unidades caben en el carrito.
  `DetallePedido.reserva_stock` recuerda si la linea aparto stock, para liberar o descontar solo eso aunque el
  producto cambie despues de modalidad. En las pruebas `crear_producto` si lleva inventario.
- SKU y slug de producto, codigo de cupon, nombre de zona y cuenta bancaria son unicos por tienda.
- Categorias globales: solo el superusuario las administra; la importacion de un vendedor no las crea.
- No hay tabla de clientes: `pedidos.services.clientes` los saca de los pedidos (por tienda y telefono).
- Numero de pedido `PREFIJO-AAAA-NNNNN` con la tabla `SecuenciaTienda` (una fila por tienda y año, bloqueada
  al crear). Cada tienda numera aparte; la primera conserva `MMX`.
- `Pedido.ip` guarda la IP para el limite anti-spam (`PEDIDOS_MAX_POR_IP` por `PEDIDOS_VENTANA_IP_MINUTOS`).
  Con `DEBUG=False` se lee de `X-Real-IP`, que pone Nginx.
- Ventas del panel = pedidos con `fecha_pago` y no cancelados. "Mas vendidos" = unidades en pedidos
  Pagado/Listo/Enviado/Entregado, con cache de 5 minutos por tienda (`clave_mas_vendidos`).
- Contra entrega solo aplica a envio a domicilio; para recoger existe "Efectivo al recoger".
- Pedido pagado puede pasar directo a Entregado (el cliente lo recoge en el momento).
- El carrito de la sesion es `{id_tienda: {'items': ..., 'cupon': ...}}`; el formato anterior (un solo
  carrito) se descarta. El cupon vive ahi; el checkout lo revalida y `crear_pedido` lo bloquea y cuenta el uso.
  `crear_pedido` toma la tienda del carrito y exige que productos, zona y cupon sean de ella.
- El comprobante se sube en el checkout (campo `comprobante`, formulario multipart; se guarda en la misma
  transaccion del pedido) o despues en la pagina del pedido; nunca cambia el estado. No hay casilla "ya transferi".
- Marca del producto: texto libre (`Producto.marca`), sin modelo aparte; el filtro del catalogo la compara sin
  mayusculas (`catalogo.services.marcas_de`). Asi el vendedor no depende del administrador para una marca nueva.
- "Comprar ahora" es el mismo POST de agregar al carrito con `comprar=1`: redirige al checkout. Cada tarjeta de
  producto (`includes/tarjeta_producto.html`) lleva Agregar (icono) y Comprar, siempre contra el carrito de la
  tienda del producto (`producto.tienda.slug`), asi que sirve tambien en la portada, el buscador del sitio y
  favoritos.
- Busqueda sin tildes: `Producto.texto_busqueda` (nombre + marca + SKU + descripcion normalizados en `save()`).
  Ojo: `queryset.update()` de nombre/descripcion no lo refresca.
- El checkout no pide correo: el pedido lleva el de la cuenta (`request.user.email`) y los avisos van alli. El
  telefono es obligatorio.
- Los pedidos no se crean desde el panel; en su formulario solo se editan las notas internas.
- Los pedidos si se eliminan desde el panel (boton del detalle y accion de la lista), siempre con
  `pedidos.services.eliminar_pedido`: si aun se podia cancelar lo cancela primero (reserva y cupon); lo
  enviado o entregado no devuelve stock. El numero no se reutiliza y el pedido sale de las ventas del panel.
  El vendedor solo borra pedidos sin dinero de por medio (`puede_eliminar`: sin pago, sin transferencia avisada y
  sin liquidar); lo demas es el registro de lo cobrado y de la comision, y solo lo borra el superusuario. Tampoco
  cancela un pedido que el sitio ya cobro (`transiciones_permitidas`).
- Importacion Excel: `catalogo/resources.py`, identifica por `sku` dentro de la tienda elegida en el
  formulario y valida con `full_clean`. Solo el superusuario crea categorias al importar. No importa fotos
  ni `stock_reservado`.
- Inicio de tienda: `catalogo.services.categorias_de_portada(tienda)` trae las categorias con productos de
  la tienda y da a la que no tiene imagen la foto de uno de ellos.
- Fotos por SKU: `catalogo.services.asignar_foto_por_sku` usa el nombre del archivo como SKU (dentro de la
  tienda) y deja la foto como principal. La pagina del panel las envia una por una con `fetch` (cada foto se convierte y se sube al
  almacenamiento; en una sola peticion se agotaria el tiempo de Gunicorn). Sin JavaScript funciona con un POST normal.
- QR de la factura: lleva `pedidos.factura.codigo_de_verificacion` (el id firmado con `Signer`, sin fecha) en
  `/factura/<codigo>/`, nunca el token: el token abre la pagina privada del pedido y la factura se comparte en
  fotos. Las facturas de antes (`/pedido/<token>/verificar/`) redirigen a la nueva.
- Fecha estimada de entrega (`pedidos/entregas.py`): dias habiles de lunes a sabado. Plazos de la tienda
  (`dias_para_recoger`, `dias_bajo_pedido`, que se suma si el pedido lleva algo bajo pedido) y de cada zona
  (`dias_entrega_min`/`max`). Se ve en la ficha, el checkout y la pagina de envios; el pedido guarda lo prometido
  (`entrega_desde`/`entrega_hasta`).
- "Avisame cuando este disponible" (`catalogo.AvisoDisponible`, `catalogo/avisos.py`): un correo por producto, con
  o sin cuenta (con cuenta va al de la cuenta), limite de 10 por persona y hora (`core.red.quien_es`). Se avisa una
  sola vez al guardar el producto ya comprable (senal `post_save`), con las acciones de disponibilidad del panel y,
  para lo demas hecho en masa (`update`), en las tareas periodicas. El vendedor ve quien espera (solo lectura).
- Factura PNG: usa una fuente del sistema (`core.fuentes.cargar_fuente`); con la de Pillow, que no trae
  tildes, escribe sin ellas para que no salgan recuadros.
- Solicitudes de tiendas: el negocio elige un rubro general (`tiendas.models.RUBROS`: detergentes y limpieza, cocina,
  barberia, musica, electronica...), no las categorias de los productos (pedido del dueño el 2026-10-27; `tiendas/0018`
  a `0020`; las solicitudes de antes guardaron su categoria en las notas).
