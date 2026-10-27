# Multimix RD

Sitio de tiendas online (Django) con precios en pesos dominicanos. Reune varias subtiendas de vendedores
independientes: cada una con su catalogo, carrito, cuentas y pedidos. La compra se completa en el sitio (checkout
por pasos); WhatsApp es solo un canal opcional para escribirle a la tienda. El pago lo confirma a mano el vendedor
desde el panel.

## Stack (fijo)
- Python 3.13, Django 5.2 LTS, entorno virtual en `.venv`.
- Plantillas Django + CSS + JavaScript sin frameworks. Bootstrap 5 y Bootstrap Icons por CDN, sin `integrity`.
- Sin React, Node, Tailwind ni pasos de build.
- Base de datos por `.env` (`DB_ENGINE`: sqlite | postgresql | mysql). Ninguna credencial en el codigo.
- Dependencias: `requirements.txt` (Django, Pillow, qrcode, django-import-export[xlsx], python-dotenv) y
  `requirements-prod.txt` (gunicorn, psycopg, dj-database-url, whitenoise, django-storages). El proyecto
  importa `dj_database_url` siempre: en desarrollo se instala `requirements-prod.txt`.
- Idioma `es`, zona horaria `America/Santo_Domingo`. Interfaz en español; modelos y campos en español sin tildes ni ñ.

## Comandos
```
.venv\Scripts\python manage.py check
.venv\Scripts\python manage.py makemigrations
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py test
.venv\Scripts\python manage.py cargar_demo
.venv\Scripts\python manage.py cancelar_pedidos_vencidos
.venv\Scripts\python manage.py runserver
```
Al cerrar cada modulo: check, makemigrations, migrate, test y commit.

## Estructura
- `config/` — settings, urls, wsgi.
- `tiendas/` — Tienda (subtienda) y sus vendedores; `@de_tienda` para las vistas, `AdminDeTienda` para el
  panel, grupo Vendedores, portada del sitio, pagina de todas las tiendas (`/tiendas/`), buscador del sitio y
  enlaces anteriores.
- `core/` — ConfiguracionTienda (fila unica, ajustes del sitio), CuentaDelSitio (a donde le pagan las tiendas su plan), panel (AdminSite propio),
  filtro `moneda`, telefonos RD, paginas informativas, sitemap/robots, comando `cargar_demo`.
- `catalogo/` — Categoria (comun a todas las tiendas), Producto, FotoProducto; inicio, catalogo y detalle de cada tienda.
- `promociones/` — Cupon y su validacion.
- `carrito/` — carrito en sesion, uno por tienda (sin modelo).
- `pedidos/` — ZonaEnvio, Pedido, DetallePedido, SecuenciaTienda, EventoPedido (seguimiento) y
  SolicitudDevolucion; checkout, pagina del pedido, clientes del panel, reportes, avisos por correo, WhatsApp.
- `clientes/` — cuentas de clientes del sitio (registro, entrada, recuperar contraseña, perfil, historial de
  pedidos) y limite de intentos.
- `opiniones/` — Resena: una por cliente y producto, moderada (solo el superusuario publica o rechaza; el
  vendedor las ve) y con "compra verificada" si lo recibio en un pedido hecho con su cuenta. Hasta 3 fotos
  (`FotoResena`, WebP; fotos nuevas reemplazan a las anteriores). Pregunta: el cliente con cuenta pregunta (5 por
  hora), la tienda recibe un correo y responde en el panel (`PreguntaAdmin`, `services.responder`): se publica y
  al cliente le llega un correo. La tienda puede ocultarlas.
- `pagos/` — Pago (un intento de pago por pedido), comprobantes de transferencia (privados), conciliacion en el panel y
  el contrato de las pasarelas de tarjeta (`proveedores.py`, ninguna conectada). Ver `docs/PAGOS.md`.
- `planes/` — Plan (tres: Basico, Estandar, Premium), Cargo (lo que cada tienda le debe al sitio: mensualidad, pedidos
  de mas u otro, con su comprobante privado), Anuncio (banners de las tiendas en la portada) y Video (videos cortos
  de las tiendas). `services.py`: cargos del mes, excedente, recordatorios, cierre y habilitacion, comprobantes,
  anuncios y videos. Ver `docs/PAGOS.md`.
- `templates/`, `static/` — plantillas y recursos de la tienda y del panel.
- `docs/` — RENDER.md (despliegue real y traslado de la base), PAGOS.md, DESPLIEGUE.md (VPS) y esquema.sql
  (referencia; las tablas las crea `migrate`).

## Reglas que no se rompen
- Nada cruza de una tienda a otra. Producto, Pedido, Pago, Cupon, ZonaEnvio, CuentaBancaria, Cargo, Anuncio y Video
  llevan `tienda`.
  En el sitio toda vista de tienda usa `@de_tienda` y filtra por `request.tienda`; en el panel todo
  ModelAdmin con datos de tienda hereda `tiendas.panel.AdminDeTienda`. Un modelo o una pantalla nueva
  entra con su prueba de aislamiento (`tiendas/tests/`).
- Solo el superusuario ve todas las tiendas (`tiendas.services.ve_todas`); el resto, las de `Tienda.usuarios`.
- La logica de negocio vive en `services.py` de cada app, no en vistas ni plantillas.
- Montos siempre calculados en el servidor; nunca se confia en montos del navegador.
- Stock: `transaction.atomic` + `select_for_update`. `stock_reservado` solo lo toca `pedidos/services.py`.
- Lo que se puede comprar lo decide `Producto.se_puede_comprar` (o `q_comprable()` en consultas), nunca el
  stock a secas: casi ningun producto lleva inventario.
- El estado del pedido solo cambia con `pedidos.services.cambiar_estado` (lo usa el panel), que ademas deja el
  paso en `EventoPedido`. Estados: pendiente, pagado, preparando, listo (recoger) o enviado y en reparto (envio),
  entregado, cancelado y reembolsado. Cancelado y reembolsado no cuentan como venta (`Pedido.ESTADOS_SIN_VENTA`).
- El cliente cancela su pedido solo antes de pagar (`puede_cancelar_el_cliente`): pendiente y sin haber avisado
  la transferencia. La cancelacion automatica de vencidos (`cancelar_pedidos_vencidos`) tampoco toca un pedido con
  la transferencia avisada (lo vuelve a mirar con el pedido bloqueado): ese lo cancela una persona tras ver el banco. Las devoluciones se solicitan hasta `ConfiguracionTienda.dias_devolucion` dias tras la entrega.
- El cliente nunca marca un pedido como pagado; solo avisa que transfirio subiendo el comprobante, que es
  obligatorio (pedido del dueño el 2026-10-19): `pagos.services.registrar_comprobante` rechaza el aviso sin foto y
  `crear_pedido` solo lo marca si `datos['comprobante']` la trae.
- El pago de un pedido solo cambia con `pagos.services` (`registrar_comprobante`, `aprobar_pago`, `rechazar_pago`);
  `cambiar_estado` lo mantiene de acuerdo con el pedido (`sincronizar_con_pedido`). Nunca se guardan datos de tarjeta.
- Montos en plantillas con `{{ valor|moneda }}` -> `RD$ 1,250.00`.
- Nada de `|safe` con datos de usuarios. Solo ORM.

## Decisiones tomadas
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
- La pagina del pedido lleva `<meta name="referrer" content="same-origin">`, nunca `no-referrer`: con este ultimo
  el navegador envia `Origin: null` en sus formularios (comprobante, cancelar, devolucion) y Django responde 403.
  Paso en produccion y las pruebas no lo ven, porque el cliente de pruebas no manda `Origin`.
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
- Sin cron en Render free: `config.middleware.TareasPeriodicasMiddleware` llama a `core.tareas.ejecutar_si_toca`,
  que como mucho una vez por hora (candado en la cache) cancela los pedidos vencidos y borra sesiones caducadas.
  En las pruebas esta apagado (`TAREAS_AUTOMATICAS`).
- Cabecera CSP (`POLITICA_DE_CONTENIDO` en settings): scripts y estilos solo del sitio y de cdn.jsdelivr.net. Los
  scripts SIN 'unsafe-inline': nada de `<script>` sin `src` ni `onclick=` en las plantillas (lo comprueba
  `core/test_seguridad.py`); va en `static/js/` (`panel.js` en el panel, `tienda.js`, `js-activo.js`). Los botones
  que piden confirmacion llevan `data-confirmar`. Los estilos si llevan 'unsafe-inline' (atributos `style`). El
  JSON-LD (`application/ld+json`) no se ejecuta y no lo afecta. `form-action 'self'`: al conectar una pasarela
  que reciba un formulario hay que agregar su dominio.
- `/salud/` responde "ok" si la aplicacion y la base funcionan (para el Health Check Path de Render).
- App instalable (PWA): `/manifest.webmanifest`, `/sw.js` (plantilla `pwa/sw.js`, en la raiz para que controle todo
  el sitio; `no-cache`) y `/sin-conexion/`, todas con `@login_not_required`. El service worker no guarda paginas
  (traen datos de la cuenta): las pide a la red y sin internet muestra "Sin conexion"; los estaticos si, con la
  cache nombrada por la version de los estaticos. Iconos `static/img/icono-*.png` (salen del simbolo del logo).
  En desarrollo (DEBUG) los estaticos no llevan huella y esa version no cambia: el navegador que ya instalo el
  service worker sigue viendo el CSS/JS viejo hasta recargar con Ctrl+Shift+R o abrir una ventana privada.
  El menu ofrece "Instalar la app" cuando el navegador lo permite y explica el camino en iPhone.
- JSON-LD del producto (`core.seo.producto_json_ld`): precio, disponibilidad y marca reales; la valoracion solo
  aparece si hay reseñas publicadas. Es la unica excepcion a "nada de |safe": el JSON se escapa como `json_script`.
- Reporte de ventas (`pedidos.reportes`, Panel > Pedidos > Reporte de ventas) con descarga CSV, limitado a las
  tiendas del usuario. El historial de acciones del panel (LogEntry) lo ve solo el superusuario; los cambios de
  estado de cada pedido quedan en `EventoPedido` con el usuario que los hizo.
- Contenido administrable: `tiendas.Banner` (carrusel del inicio de cada tienda; sin banners activos se ve el
  banner fijo de la tienda), `core.PaginaInformativa` (`/pagina/<slug>/`, politicas del sitio) y
  `core.PreguntaFrecuente`. Las politicas las crea `core/0014` y `core/0015` les pone un texto estandar y las
  publica (pedido del dueño el 2026-10-14; solo llena las vacias). Los plazos del texto (dias de devolucion, horas
  de vencimiento) son los de la configuracion al migrar: si cambian, se corrige el texto en el panel. Sin publicar
  solo las ve el superusuario. El contenido se muestra con el filtro
  `texto_legal` (`core/templatetags/textos.py`: titulos, listas y parrafos, todo escapado), nunca como HTML. El pie las lee de `core.models.contenido_del_pie` (cache de 5 minutos, se limpia al guardar).
- Entrar: `clientes.autenticacion.CorreoOUsuarioBackend` acepta el usuario o el correo (si es de una sola cuenta):
  el superusuario de Render es `MULTIMIX_ADMIN` y el formulario del sitio pide el correo. Ojo: el arranque de
  Render vuelve a poner la contraseña del superusuario desde `DJANGO_SUPERUSER_PASSWORD` en cada despliegue, asi
  que recuperarla por correo dura hasta el siguiente. `BrevoBackend` registra cada envio aceptado con su messageId.
- Cuentas de clientes: son usuarios de Django sin acceso al panel, con el correo como nombre de usuario, y son
  del sitio, no de una tienda (`/cuenta/`). `clientes.Perfil` guarda el telefono y si quiere recordatorios; las
  direcciones son `clientes.Direccion` (hasta 10, una principal que llega puesta en el checkout; cada pedido a
  domicilio guarda la suya si es nueva; `clientes/0006` paso la del perfil). La zona no, porque es de cada tienda.
  Con la sesion iniciada el carrito tambien se copia a `clientes.CarritoGuardado` (en `Carrito._guardar`; el
  personal del panel no) y vuelve a la sesion al entrar (`carrito.carrito.recuperar_al_entrar`, senal
  `user_logged_in`; lo de la sesion manda). Las tareas periodicas envian un recordatorio a quien lo dejo entre 1 y 7
  dias (uno por cada vez que lo deja; enlace firmado para apagarlos). "Volver a pedir" (`pedidos:volver_a_pedir`,
  por token) pone en el carrito lo del pedido que siga a la venta. `Pedido.cliente` solo se llena si compro con la sesion iniciada: un pedido
  de invitado (de antes de la cuenta obligatoria) nunca se asocia despues a una cuenta por coincidir el correo. Las plantillas de acceso estan en `templates/clientes/` y no en
  `templates/registration/`, que pisaria las pantallas de contraseña del panel.
- Limite de intentos (`core.limites`, filas `core.Intento` con la clave en sha256; las viejas las borran las
  tareas periodicas): vive en la base, no en la cache, para que lo compartan los procesos y no se borre al
  reiniciar. La IP no es fiable, asi que lo que importa cuenta tambien sin ella (`clientes.services`): entrar, 5
  por conexion y correo y 10 por cuenta desde cualquier IP, y el panel (`EntrarAlPanelForm`, `PanelAdminSite.
  login_form`) cuenta junto con el sitio; cuentas nuevas, 5 por conexion y 30 en todo el sitio; enlaces de
  recuperacion o confirmacion, 3 por hora a un mismo correo (pasado el limite responde igual, sin enviar);
  pedidos, `PEDIDOS_MAX_POR_CUENTA`; cupones que no aplican (`promociones.services.probar_cupon`, desde
  `Carrito.aplicar_cupon`), 10 por cuenta, sesion o IP y 100 por tienda, sin contar dos veces el mismo codigo.
- IP del visitante (`core.red.ip_del_cliente`): solo la cabecera que el proxy reescribe (`settings.CABECERA_IP`:
  `CF-Connecting-IP` en Render, que va detras de Cloudflare; `X-Real-IP` con Nginx). Nunca la primera de
  `X-Forwarded-For`: Render la deja como la mando el visitante y se podia inventar una IP en cada intento. Sin la
  cabecera devuelve None (no hay limite por IP) y lo registra una vez.
- Correo confirmado (`clientes.Perfil.correo_verificado`): al crear la cuenta se envia un enlace firmado
  (`signing`, 3 dias, ligado al correo); el checkout lo exige (`correo_confirmado`) y manda a
  `/cuenta/confirmar/`. Recuperar la contraseña tambien lo confirma. Las cuentas anteriores quedaron confirmadas
  (`clientes/0004`); el personal del panel no lo necesita. Apagado sin correo configurado y en las pruebas
  (`VERIFICAR_CORREO`).
- Comprobantes privados: `Pago.comprobante` usa `STORAGES['privado']` (bucket `SUPABASE_S3_BUCKET_PRIVADO`; en
  desarrollo la carpeta `privado/`, que no se sirve; en produccion el bucket `multimix-privado`, creado el
  2026-10-19). Sin ese bucket es el mismo publico de antes.
  `Pago.comprobante_privado` dice donde esta cada archivo (`almacenamiento_del_comprobante`); las tareas
  periodicas pasan los de antes (`pagos.services.mover_comprobantes_al_privado`). El panel lo muestra con
  `admin:pagos_pago_comprobante`, que lo lee del almacenamiento y filtra por tienda; el archivo no tiene URL publica.
- Imagenes: `validar_imagen` mide los pixeles leyendo solo la cabecera (`IMAGEN_MAX_PIXELES` 40 MP;
  `IMAGEN_MAX_PIXELES_JPEG` 120 MP, porque un JPG se abre reducido con `draft`). `convertir_a_webp` achica antes de
  girar segun el EXIF, para no tener dos copias grandes en memoria (Render free tiene 512 MB).
- Correos: `core.correo.enviar` (texto, plantillas en `templates/correos/`, nunca lanza: registra el fallo) y
  `pedidos.avisos` (pedido nuevo, cambio de estado, comprobante, pago rechazado). Salen con
  `transaction.on_commit`, asi que en las pruebas hay que envolver con `captureOnCommitCallbacks(execute=True)`.
  En produccion van por la API de Brevo (`BREVO_API_KEY`, `core.correo_brevo.BrevoBackend`): Render free bloquea
  SMTP y el envio se quedaba en `TimeoutError`. Con `EMAIL_HOST` van por SMTP y sin nada, a la consola. La tienda recibe en su correo de
  contacto y, si no tiene, en el de sus vendedores, el del sitio o el de los superusuarios. Los enlaces usan
  `SITIO_URL`. En Configuracion general hay un boton "Enviar correo de prueba" (Render free no tiene consola).
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
- Disponibilidad comercial: el negocio no cuenta unidades fiables, asi que cada producto se vende segun
  `Producto.disponibilidad` (disponible, bajo pedido, agotado, temporalmente no disponible). El inventario es
  opcional por producto (`controla_stock`, apagado por defecto): solo entonces valen `stock_almacen` y
  `stock_reservado`. `estado_venta` es lo que ve el cliente y `limite_compra` cuantas unidades caben en el carrito.
  `DetallePedido.reserva_stock` recuerda si la linea aparto stock, para liberar o descontar solo eso aunque el
  producto cambie despues de modalidad. En las pruebas `crear_producto` si lleva inventario.
- Proyecto en `C:\Users\elies\multimix_rd` (no en la carpeta de usuario) para aislar el repositorio.
- Paquete de configuracion: `config`. Apps en la raiz del proyecto.
- `django-import-export[xlsx]`: el extra instala openpyxl, necesario para Excel.
- SQLite usa `transaction_mode=IMMEDIATE` para serializar escrituras (alli `select_for_update` no hace nada).
- ConfiguracionTienda: `save()` fuerza `pk=1`, `delete()` no hace nada, `obtener()` la entrega con cache.
  Guarda lo del sitio (nombre, logo, descripcion, contactos, dias de "nuevo", umbral de stock, horas de
  vencimiento); el banner, la direccion para recoger y el contra entrega son de cada `Tienda`.
- `Tienda` repite los nombres de campo de contacto de ConfiguracionTienda (`nombre`, `logo`, `whatsapp`,
  redes...) y expone `descripcion` (su `banner_subtitulo`). En las plantillas `tienda` es la subtienda actual
  (o nada en las paginas del sitio), `plataforma` la configuracion y `marca` la que firme la pagina
  (`tienda or plataforma`).
- Portada, Fase 1 del rediseño (2026-10-27): bienvenida carbon "Descubre. Compra. Emprende." con "Explorar productos"
  (ambar) y "Conocer las tiendas", tres puntos ciertos para cualquier tienda y cuatro productos reales de la seleccion
  con el nombre de su tienda; categorias como tarjetas con foto y "Ver productos"; tiendas en una banda blanca
  (`mm-banda`) con boton "Visitar tienda"; "Compra con confianza" (`includes/confianza.html`, el mismo texto del
  menu). Corazon de favoritos en cada tarjeta de producto: `favoritos_ids` (perezoso, en `core.context_processors`)
  dice si esta guardado; `clientes:alternar_favorito` responde JSON a `tienda.js` (`X-Requested-With: fetch`) y sin
  JavaScript redirige como antes; sin sesion lleva a entrar. Precio y botones van en `.mm-tarjeta-pie`, abajo, para
  quedar alineados entre tarjetas.
- Portada del sitio (pedido del dueño el 2026-10-25; reemplaza la de "solo tiendas, sin productos" del 2026-10-19):
  un sitio de muchas tiendas, para comprar sin conocer al vendedor o para entrar a una tienda. Orden: bienvenida
  corta (`mm-hero`, clara, distinta del `mm-banner` oscuro de las tiendas; en pantallas anchas 4 fotos reales de la
  seleccion), categorias del sitio (`catalogo.services.categorias_del_sitio`: principales con algo a la venta, con
  cuantos productos y foto; llevan a `/buscar/?categoria=<slug>`), "Descubre productos" (`vitrina_del_sitio`: solo
  lo comprable, con foto primero, repartido entre tiendas y, dentro de cada tienda, alternando sus categorias: la
  base numera con `RowNumber` por tienda y categoria y el reparto se hace en Python; 12, ocho en el celular), tiendas
  (8; "Ver todas" lleva a `/tiendas/`), ofertas (`ofertas_del_sitio`, igual de repartidas, solo si hay, y no se repiten
  en la seleccion), "Para emprendedores" (`#vender`) y preguntas frecuentes. Todo sale de la base: una seccion sin
  datos no se muestra. Fuera de una tienda la tarjeta de producto dice "Vendido por <tienda>" con enlace a ella.
  "Tu compra, protegida", la ayuda y lo legal siguen en el menu de 3 barras y en el pie. Con una sola tienda su
  tarjeta se acuesta a todo el ancho (`una-sola`).
- Vender en el sitio: no hay alta propia (las tiendas las crea el superusuario). `tiendas.services.como_vender` da
  el camino: el WhatsApp del sitio con el mensaje listo, su correo o la pagina de contacto; sin ninguno no se
  ofrece. La direccion del panel (`ADMIN_URL`, secreta a pedido del dueño) solo se enlaza al personal
  (`user.is_staff`: "Mi panel"); nunca a clientes ni visitantes.
- Cabecera (todas las paginas): en pantallas anchas una fila fija y debajo la franja `mm-nav` (categorias,
  tiendas, productos, ofertas, vender o "Mi panel"). En el telefono dos filas (marca y favoritos; menu y buscador)
  que se van al bajar. El buscador ya no esta repetido en el menu de 3 barras. Al agregar al carrito fuera de una
  tienda (portada, buscador, favoritos) el aviso enlaza al carrito de la tienda del producto (`data-tienda`).
- Barra del telefono (`mm-barra-movil` en `base.html`, pedido del dueño el 2026-10-26: "para el telefono, no en
  la PC"): solo por debajo de 992 px y con `puede_navegar`. En el sitio Inicio, Tiendas, Buscar, Ofertas y Mi
  cuenta; dentro de una tienda Tienda, Catalogo, Buscar, Carrito (con contador) y Mi cuenta. Es lo unico fijo en el
  telefono: la cuenta y el carrito de la cabecera se esconden alli (`con-barra-movil` en el body, que tambien deja
  espacio abajo y sube WhatsApp, "volver arriba" y los avisos). "Buscar" sube al buscador de la cabecera y lo
  enfoca (`js-ir-al-buscador`; sin JavaScript abre la busqueda). Se aparta mientras se escribe en un campo y cuando
  la ficha muestra su barra de compra (`mm-compra-fija`).
- Filas: `includes/fila_productos.html` + `[data-fila]` en `tienda.js` (flechas, `data-auto` avanza solo); las
  categorias de la portada usan la misma fila. El inicio de cada tienda: cinta en movimiento (`mm-cinta`),
  categorias en burbujas y una fila por seccion.
  Animaciones al deslizar en `tienda.js`: `revelar` (en cascada con `--retraso`; variantes `revelar-izq`,
  `-der`, `-zoom`, que el JS pone a titulos, burbujas, tarjetas y paneles), barra `mm-progreso`, cabecera
  `con-sombra`, boton `mm-arriba` y el banner de la tienda mas lento. Con "reducir movimiento" no se anima.
  Ojo: algo con `position: absolute` (como un texto solo para lectores de pantalla) dentro de una fila que se
  desliza necesita un ancestro posicionado dentro de la fila (`.mm-tarjeta` es `relative`): si no, cuando
  `revelar` quita el `transform` escapa del recorte y ensancha toda la pagina en el celular.
  Letra: Inter servida desde `static/fonts/` (no por CDN). Pantallas de entrar/crear/recuperar con panel de marca
  (`mm-acceso con-marca`); politicas, terminos y preguntas con indice lateral (`paginas/_indice_legal.html`).
  Tampoco hay guia "Como comprar" (quitada a pedido del dueño): su ruta redirige al
  inicio de la tienda. El banner (`mm-banner`) es solo de las tiendas.
- WhatsApp siempre con codigo de pais: `core.telefonos.normalizar_whatsapp` antepone el 1 a los numeros
  dominicanos de 10 digitos. Se aplica al validar y guardar Tienda y ConfiguracionTienda y, por si acaso, al
  armar cada enlace (`construir_enlace`). Sin el 1, wa.me abre un numero de otro pais.
- Los ModelAdmin con imagenes heredan `core.admin_avisos.AvisaImagenesSinGuardar`: si el formulario vuelve
  con errores, el navegador olvida los archivos elegidos y hay que avisarlo.
  El mismo mixin atrapa los fallos del almacenamiento (`core.archivos.ERRORES_DE_ALMACENAMIENTO`) y vuelve
  al formulario con un mensaje en vez de un error 500.
- Las imagenes se guardan con nombre generado: `core.archivos.NombreUnico('carpeta')` como `upload_to`
  (logo y banner de tienda, logo del sitio, categorias) y uuid en `FotoProducto.save`. Supabase responde 400
  a los nombres con tildes o ñ. Por eso el almacenamiento va con `file_overwrite=True` (no pregunta si el
  archivo existe): una imagen nueva nunca debe guardarse con el nombre que trae del usuario.
- Supabase lento: botocore con 5 s de conexion, 20 s de lectura y 2 intentos (`client_config`), y
  `gunicorn.conf.py` con `timeout = 120`. Con los valores por defecto Gunicorn mataba la peticion a los 30 s.
- Rutas de tienda bajo `/tienda/<tienda_slug>/` (`tiendas.decoradores.RUTA_DE_TIENDA`). `pedidos` y `core`
  mezclan rutas de tienda y del sitio, por eso declaran las suyas completas y se incluyen en la raiz.
  Las paginas por token (confirmacion, factura) ponen `request.tienda = pedido.tienda`.
- Lo que el vendedor no toca: su plan, la comision de los pedidos viejos, el ITBIS, las cuentas del sitio, abrir su
  tienda cerrada y aprobar sus pagos al sitio o sus anuncios: solo el superusuario. Desde el 2026-10-26 si maneja las
  cuentas bancarias de su tienda (cobra lo suyo). Los permisos del grupo se fijan con `set` al migrar, asi que
  quitar uno de `PERMISOS_VENDEDOR` se lo quita al grupo.
- Las tiendas las crea el superusuario. Al asignar usuarios en `TiendaAdmin` se llama
  `dar_acceso_al_panel` (personal + grupo Vendedores); `tienda.usuarios.add()` a secas no da permisos.
  El grupo y sus permisos (`PERMISOS_VENDEDOR`) se crean con `post_migrate`.
- El campo `tienda` de los formularios del panel nunca se excluye: va oculto (vendedor con una tienda) o
  deshabilitado (al editar). Si se excluyera, Django no validaria las unicidades por tienda (SKU, slug,
  codigo de cupon, zona) y fallaria con IntegrityError.
- `Tienda.prefijo` no cambia despues de crear la tienda: ya esta en los numeros de pedido emitidos.
- SKU y slug de producto, codigo de cupon, nombre de zona y cuenta bancaria son unicos por tienda.
- Categorias globales: solo el superusuario las administra; la importacion de un vendedor no las crea.
- No hay tabla de clientes: `pedidos.services.clientes` los saca de los pedidos (por tienda y telefono).
- `/catalogo/`, `/producto/<slug>/`, `/carrito/`... (de cuando habia una tienda) redirigen a la tienda mas
  antigua activa (`tiendas.services.tienda_principal`).
- Migracion a subtiendas en tres pasos por app (campo opcional, datos, campo obligatorio) y en archivos
  separados: PostgreSQL no deja alterar una tabla en la misma transaccion en que se actualizaron sus filas.
  `tiendas/0002` crea la primera tienda (prefijo MMX) solo si ya habia configuracion o datos.
- Al agrupar (`annotate` con Count/Sum) Django ignora el `ordering` del modelo: se ordena a mano.
- En los tests la cache es `DummyCache` para que cada prueba sea independiente.
- Telefonos guardados como 10 digitos (`8095551234`); para wa.me se antepone `1`.
- `PanelAdminConfig` vive en `config/apps.py` (no en `core/apps.py`: Django no admite dos AppConfig por
  defecto en un modulo). El sitio es `core.admin_site.PanelAdminSite`; el resumen sale de `core/panel.py`.
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
- Buscador con sugerencias: `catalogo.services.sugerencias` (minimo 2 letras) en `/tienda/<slug>/sugerencias/` y
  `/sugerencias/` (todo el sitio). El desplegable se arma en `tienda.js` con nodos, nunca con HTML del servidor.
  `/buscar/?categoria=<slug>` limita el buscador del sitio a una categoria con sus subcategorias (una que no existe
  o esta apagada se ignora, como los demas filtros).
- Directorio de tiendas (`tiendas.services.directorio`, portada y `/tiendas/`): solo las activas, con
  `total_productos` contado como en el catalogo (una vez por grupo de variantes); `para_el_directorio` agrega sus
  categorias con mas productos y el tono de su franja si no tiene banner, con una consulta para todas.
- "Comprar ahora" es el mismo POST de agregar al carrito con `comprar=1`: redirige al checkout. Cada tarjeta de
  producto (`includes/tarjeta_producto.html`) lleva Agregar (icono) y Comprar, siempre contra el carrito de la
  tienda del producto (`producto.tienda.slug`), asi que sirve tambien en la portada, el buscador del sitio y
  favoritos.
- Busqueda sin tildes: `Producto.texto_busqueda` (nombre + marca + SKU + descripcion normalizados en `save()`).
  Ojo: `queryset.update()` de nombre/descripcion no lo refresca.
- Cuenta para comprar: se navega y se arma el carrito sin cuenta (Google ve el catalogo); el checkout lleva
  `@login_required` y el carrito ofrece "Iniciar sesion y continuar" (el carrito de la sesion se conserva al
  entrar). El dueño pidio primero cerrar todo el sitio y despues, el 2026-10-14, abrirlo: el cierre sigue
  disponible con la variable `CUENTA_OBLIGATORIA=1` (`config.middleware.CuentaObligatoriaMiddleware`, el
  `LoginRequiredMiddleware` de Django), que manda a `/cuenta/entrar/` todo el sitio. Abren sin sesion, con
  `@login_not_required`: entrar, crear cuenta, recuperar contraseña, terminos, politicas, preguntas, robots,
  sitemap, `/salud/`, el panel (se protege solo) y las paginas por token del pedido (los enlaces de los correos y
  los pedidos de invitado anteriores). Una vista nueva del sitio queda cerrada sin hacer nada. En las pruebas esta
  apagado (`CUENTA_OBLIGATORIA`); `clientes/tests/test_cuenta_obligatoria.py` lo prueba encendido. Sin sesion la
  plantilla oculta menu, buscador y carrito (`puede_navegar`). El checkout lleva ademas `@login_required`.
- Experiencia de compra (tomado de las grandes tiendas; la primera barra inferior del celular se quito porque al
  dueño no le gusto y volvio rediseñada el 2026-10-26, ver "Barra del telefono"): estrellas en las tarjetas
  (`ProductoQuerySet.con_valoracion`, subconsultas, dentro de `para_listado`), vistos recientemente en la sesion
  (`catalogo.services.recordar_visto`/`vistos`; dentro de una tienda solo los suyos, porque la tarjeta agrega al
  carrito de esa tienda), cuenta regresiva si la oferta termina en 7 dias o menos, barra de compra fija en la
  ficha (celular), "Completa tu pedido" en el carrito (`sugerencias_para_el_carrito`, con `q_comprable`),
  sugerencias cuando una busqueda no encuentra nada y JSON-LD del sitio (SearchAction) y de la ruta del producto.
  Las valoraciones se muestran con punto decimal (`floatformat:"1u"`): el locale `es` pondria coma.
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
- Marca: paleta del dueño del 2026-10-27 (Fase 1 del rediseño; reemplaza la azul `#244BFF` del 2026-10-25) en las
  variables de `:root` de `tienda.css`, unico lugar de colores, radios, sombras y espacios (los `rgba` usan
  `--mm-*-rgb`): carbon `#111827` (identidad, botones, titulos, precios), ambar `#F59E0B` con texto carbon solo para
  acciones importantes y ofertas (`.btn-acento`: buscar, la accion principal de la portada, comprar ahora, confirmar
  el pedido, boton del banner), `--mm-calido-texto` `#B45309` para ambar sobre fondo claro (el `#F59E0B` no se lee
  sobre blanco), fondo `#F3F4F6`, tarjetas blancas, texto secundario `#64748B`, bordes `#E5E7EB`; verde solo para lo
  que salio bien. Los enlaces van en carbon: dentro de un texto (`.mm-legal-texto`) se subrayan. `panel.css` sigue
  con el azul del logo. Recursos en `static/img/`. El encabezado del sitio muestra el simbolo estatico con el nombre salvo
  que haya un logo en Configuracion; el de cada tienda, su logo o su nombre, con una franja encima para volver a
  "Todas las tiendas".
- Inicio de tienda: `catalogo.services.categorias_de_portada(tienda)` trae las categorias con productos de
  la tienda y da a la que no tiene imagen la foto de uno de ellos.
- `core/migrations/0002` quita de la configuracion el logo o banner cuyo archivo ya no existe en el
  almacenamiento (se perdieron los que se subieron cuando los archivos iban al disco de Render).
- Fotos por SKU: `catalogo.services.asignar_foto_por_sku` usa el nombre del archivo como SKU (dentro de la
  tienda) y deja la foto como principal. La pagina del panel las envia una por una con `fetch` (cada foto se convierte y se sube al
  almacenamiento; en una sola peticion se agotaria el tiempo de Gunicorn). Sin JavaScript funciona con un POST normal.
- Acciones del admin: las descripciones pasan por formato `%`, asi que un `%` literal se escribe `%%`.
- `docs/esquema.sql` se genera con `sqlmigrate` sobre SQLite; regenerarlo si cambian las migraciones.
- QR de la factura: lleva `pedidos.factura.codigo_de_verificacion` (el id firmado con `Signer`, sin fecha) en
  `/factura/<codigo>/`, nunca el token: el token abre la pagina privada del pedido y la factura se comparte en
  fotos. Las facturas de antes (`/pedido/<token>/verificar/`) redirigen a la nueva.
- Cupones: `usos_maximos` (en total) y `usos_por_cliente` (por cuenta; 1 = bienvenida). El limite por cliente
  lo mira `validar_cupon(..., cliente=)` contando sus pedidos no cancelados con el cupon; sin sesion no se mira, y
  el checkout (con cuenta) y `crear_pedido` (con el cupon bloqueado) lo vuelven a validar.
- Envio gratis (`Tienda.envio_gratis_desde`, lo pone el vendedor): desde ese monto en productos, despues del
  cupon, el envio a domicilio cuesta 0 (`pedidos.services.costo_de_envio`, que usan los totales y `crear_pedido`).
  El carrito muestra cuanto falta (`progreso_envio_gratis`).
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

## Pruebas
- `tiendas.tests.utiles`: `tienda_de_prueba()` (la tienda "Multimix RD", prefijo MMX, donde corren casi todas
  las pruebas; con otro nombre crea otra) y `ruta('carrito:detalle')` (reverse con el slug de la tienda).
  `crear_producto`, `zona_de_prueba` y `cupon_de_prueba` usan esa tienda si no se pasa otra.
- El carrito de las pruebas guarda la misma instancia de `producto.tienda`: para cambiar un ajuste de la
  tienda en una prueba de servicios se modifica esa instancia (`self.tienda`), no una recien consultada.
- `tiendas/tests/test_migracion.py` recorre las migraciones reales con datos de una sola tienda.
- En los tests las contraseñas usan MD5 (`PASSWORD_HASHERS`) para que crear usuarios no sea lento.
- Los tests usan `assertRedirects(..., fetch_redirect_response=False)` cuando despues se revisan mensajes
  o la apertura automatica de WhatsApp: seguir la redireccion los consume.
