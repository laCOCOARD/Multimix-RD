# Pagos, planes y cobros

Decisiones tomadas en Multimix RD (movidas desde CLAUDE.md el 2026-10-28). Leelas antes de tocar esta parte del proyecto.

- Reparto a las tiendas (`pagos/liquidaciones.py`, Panel > Liquidaciones > Saldos por tienda, solo superusuario):
  desde el 2026-10-26 solo queda para los pedidos que cobro el sitio antes (`cobra_el_sitio`); lo que cobra la tienda
  ya no paga comision (`comision_de` da 0). Reglas de entonces: entra en cuenta el pedido cobrado y entregado. Comision del sitio (`Tienda.comision_porcentaje`) sobre
  subtotal - descuento; el envio es de la tienda. Las transferencias las tiene el sitio y se le depositan a la
  tienda menos la comision; el efectivo siempre lo cobra la tienda y va en su propio apartado
  (`Saldo.del_sitio` / `Saldo.de_la_tienda`): no se le deposita, pero su comision se descuenta. Saldo negativo = la
  tienda le debe al sitio. `liquidar` crea la `Liquidacion` y marca cada pedido (`liquidacion`, `monto_liquidado`)
  para no pagarlo dos veces; un pedido liquidado que luego se reembolsa se descuenta en la siguiente
  (`ajuste_liquidacion`). Lo que cobre el banco por enviar el deposito (`Liquidacion.costo_transferencia`, un monto
  que se escribe al liquidar) lo paga el sitio (pedido del dueño el 2026-10-19): se anota como gasto del sitio y
  la tienda recibe su saldo completo; el vendedor no ve ese campo. El vendedor ve sus liquidaciones pero no la comision ni quien cobra en el formulario.
- Cada tienda cobra lo suyo (pedido del dueño el 2026-10-26; reemplaza el "cobro del sitio" del 2026-10-15): sus
  clientes transfieren a las cuentas de la tienda (`tiendas.CuentaBancaria`, las registra el vendedor;
  `core.models.cuentas_para_transferir(tienda)`), el comprobante le llega a ella y ella aprueba el pago. Sin cuentas
  activas la tienda no ofrece transferencia (`metodos_pago_disponibles`) y el checkout avisa si el envio queda sin
  forma de pago. `crear_pedido` deja `cobra_el_sitio=False`. `tiendas/0016` copio las cuentas del sitio a la tienda
  mas antigua (la del dueño), para que sus clientes sigan transfiriendo. En la prueba, `tienda_de_prueba()` nace
  con una cuenta (`con_cuenta=False` para probar sin ella).
  Los pedidos que cobro el sitio del 2026-10-15 al 26 (`cobra_el_sitio=True`) siguen como entonces: el comprobante
  le llega al sitio (`avisos.correos_del_sitio`), solo el superusuario aprueba o rechaza
  (`pagos.services.puede_resolver`) y marca Pagado o Reembolsado (`transiciones_permitidas(pedido, usuario)`), y al
  pasar a Pagado la tienda recibe "Pago confirmado" (`avisos.pago_confirmado_a_la_tienda`).
- Planes y cobro a las tiendas (pedido del dueño el 2026-10-26; app `planes`, ver `docs/PAGOS.md`): el sitio no
  cobra porcentaje por articulo. Cada tienda tiene un plan (`Tienda.plan`, lo asigna el superusuario; sin plan no se
  cobra nada ni hay anuncios): mensualidad, pedidos cobrados incluidos al mes, % sobre lo vendido (productos menos
  descuento, sin envio) en los pedidos de mas, anuncios en la portada y productos "Patrocinado". La mensualidad vence
  el dia 1 (el cargo aparece una semana antes; quien recibe el plan a mitad de mes empieza el siguiente, `plan_desde`)
  y el excedente del mes anterior se calcula el dia 1 y vence ese dia. La tienda transfiere a `CuentaDelSitio` y sube
  el comprobante en su panel (`CargoAdmin`, `services.subir_comprobante`); solo el superusuario confirma, rechaza o
  anula. Avisos: `dias_aviso_mensualidad` antes, el dia que vence y el ultimo dia de gracia; pasados
  `dias_de_gracia` (4) la tienda se cierra (`activa=False`, `cerrada_por_falta_de_pago`) hasta que el superusuario la
  habilita (encender "Activa" o la accion "Habilitar"; `habilitada_el` evita que lo ya vencido la vuelva a cerrar).
  Todo corre en `revisar_cobros`, dentro de las tareas periodicas (o el comando del mismo nombre). El superusuario
  edita todo en el panel (pedido del dueño): Planes, Cargos (monto, fechas, tipo, mes y estado; el estado pasa por
  `services.cambiar_estado_del_cargo`, con sus correos) y en Configuracion general los dias de aviso y de gracia.
  Tarjeta (decision del 2026-10-26, pendiente de construir): una sola afiliacion del dueño, un carrito unico con
  productos de todas las tiendas y luego el reparto a cada una (`cobra_el_sitio=True`, Liquidaciones). Los anuncios
  (`Anuncio`) salen cuando el superusuario los aprueba; cambiar su contenido los devuelve a revision. Los tres
  planes los creo `planes/0002` con montos propuestos que el dueño cambia en el panel.
- Videos de las tiendas (pedido del dueño el 2026-10-26: "el plan Premium permita un video de 15 segundos";
  `planes.Video`, Premium trae 1 por `planes/0004`, `Plan.videos_portada`): "Videos de las tiendas" en la portada
  (un circulo por tienda, orden al azar en cada visita, marcados "Anuncio") y arriba en la pagina de la tienda; el
  visor tipo historias es `static/js/historias.js` (datos en atributos de `includes/visor_historias.html`, nada de
  HTML). Sale solo aprobado por el superusuario (`services.aprobar_video`, correo a la tienda); cambiar video, titulo
  o producto lo devuelve a revision. El plan cuenta todos los videos guardados, activos o no. No se convierte nada
  (Render free no tiene ffmpeg): `core.videos` lee solo las cajas del MP4/MOV y exige H.264 (+AAC), la duracion y el
  peso de `ConfiguracionTienda` (`video_segundos_maximos`, `video_megas_maximos`); el HEVC del iPhone se rechaza con
  el consejo de reenviarlo por WhatsApp. Se guardan como `.mp4` en `STORAGES['videos']` (bucket publico
  `SUPABASE_S3_BUCKET_VIDEOS`; el de las fotos rechaza video): sin ese bucket en produccion `VIDEOS_CONFIGURADOS` es
  False y el panel no deja subirlos. Las vistas las suma `planes:vista_de_video` (POST, una por sesion). CSP:
  `media-src 'self' blob: https:`.
- Comprobantes privados: `Pago.comprobante` usa `STORAGES['privado']` (bucket `SUPABASE_S3_BUCKET_PRIVADO`; en
  desarrollo la carpeta `privado/`, que no se sirve; en produccion el bucket `multimix-privado`, creado el
  2026-10-19). Sin ese bucket es el mismo publico de antes.
  `Pago.comprobante_privado` dice donde esta cada archivo (`almacenamiento_del_comprobante`); las tareas
  periodicas pasan los de antes (`pagos.services.mover_comprobantes_al_privado`). El panel lo muestra con
  `admin:pagos_pago_comprobante`, que lo lee del almacenamiento y filtra por tienda; el archivo no tiene URL publica.
- Pagos: `pedidos.services` importa `pagos.services` dentro de las funciones (pagos usa pedidos para cambiar el
  estado). `pago_vigente(pedido)` abre el pago si falta, asi que los pedidos anteriores no necesitaron migracion.
  Un comprobante rechazado deja el pago como historial y el siguiente aviso abre otro (`-P2`). Los comprobantes
  se convierten a WebP y van a `comprobantes/` del almacenamiento privado (ver "Comprobantes privados").
  `PagoAdmin` da permiso de borrado solo para que el panel deje eliminar el pedido en cascada; no tiene boton ni accion.
- ITBIS: apagado. El dueño pidio quitarlo el 2026-10-13: `Tienda.itbis_porcentaje` vale 0 en todas las tiendas
  y por defecto, asi que no se suma ni se menciona. El calculo sigue disponible por si una tienda lo activa:
  `core.impuestos.calcular_itbis` sobre los productos no exentos (`Producto.exento_itbis`), despues del
  descuento y sin el envio. El pedido guarda `impuesto` y
  `porcentaje_impuesto`. `tienda_de_prueba()` va con 0 para que los totales de las pruebas sean los de los productos.
- Lo que el vendedor no toca: su plan, la comision de los pedidos viejos, el ITBIS, las cuentas del sitio, abrir su
  tienda cerrada y aprobar sus pagos al sitio o sus anuncios: solo el superusuario. Desde el 2026-10-26 si maneja las
  cuentas bancarias de su tienda (cobra lo suyo). Los permisos del grupo se fijan con `set` al migrar, asi que
  quitar uno de `PERMISOS_VENDEDOR` se lo quita al grupo.
- Cupones: `usos_maximos` (en total) y `usos_por_cliente` (por cuenta; 1 = bienvenida). El limite por cliente
  lo mira `validar_cupon(..., cliente=)` contando sus pedidos no cancelados con el cupon; sin sesion no se mira, y
  el checkout (con cuenta) y `crear_pedido` (con el cupon bloqueado) lo vuelven a validar.
- Envio gratis (`Tienda.envio_gratis_desde`, lo pone el vendedor): desde ese monto en productos, despues del
  cupon, el envio a domicilio cuesta 0 (`pedidos.services.costo_de_envio`, que usan los totales y `crear_pedido`).
  El carrito muestra cuanto falta (`progreso_envio_gratis`).
