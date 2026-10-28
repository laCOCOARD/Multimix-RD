# Sitio publico y diseño

Decisiones tomadas en Multimix RD (movidas desde CLAUDE.md el 2026-10-28). Leelas antes de tocar esta parte del proyecto.

- App instalable (PWA): `/manifest.webmanifest`, `/sw.js` (plantilla `pwa/sw.js`, en la raiz para que controle todo
  el sitio; `no-cache`) y `/sin-conexion/`, todas con `@login_not_required`. El service worker no guarda paginas
  (traen datos de la cuenta): las pide a la red y sin internet muestra "Sin conexion"; los estaticos si, con la
  cache nombrada por la version de los estaticos. Iconos `static/img/icono-*.png` (salen del simbolo del logo).
  En desarrollo (DEBUG) los estaticos no llevan huella y esa version no cambia: el navegador que ya instalo el
  service worker sigue viendo el CSS/JS viejo hasta recargar con Ctrl+Shift+R o abrir una ventana privada.
  El menu ofrece "Instalar la app" cuando el navegador lo permite y explica el camino en iPhone.
- JSON-LD del producto (`core.seo.producto_json_ld`): precio, disponibilidad y marca reales; la valoracion solo
  aparece si hay reseñas publicadas. Es la unica excepcion a "nada de |safe": el JSON se escapa como `json_script`.
- Contenido administrable: `tiendas.Banner` (carrusel del inicio de cada tienda; sin banners activos se ve el
  banner fijo de la tienda), `core.PaginaInformativa` (`/pagina/<slug>/`, politicas del sitio) y
  `core.PreguntaFrecuente`. Las politicas las crea `core/0014` y `core/0015` les pone un texto estandar y las
  publica (pedido del dueño el 2026-10-14; solo llena las vacias). Los plazos del texto (dias de devolucion, horas
  de vencimiento) son los de la configuracion al migrar: si cambian, se corrige el texto en el panel. Sin publicar
  solo las ve el superusuario. El contenido se muestra con el filtro
  `texto_legal` (`core/templatetags/textos.py`: titulos, listas y parrafos, todo escapado), nunca como HTML. El pie las lee de `core.models.contenido_del_pie` (cache de 5 minutos, se limpia al guardar).
- Fase 4 del rediseño (2026-10-27):
  - Miniaturas: `FotoProducto.miniatura` (WebP de 480 px, `catalogo.imagenes.LADO_MINIATURA`) se crea al subir la
    foto; `url_tarjeta` la usa si existe (tarjetas, carrito, sugerencias, categorias, miniaturas de la galeria y
    panel). La foto grande queda para la ficha y el JSON-LD. Las de antes las completan las tareas periodicas de a
    cinco (`catalogo.services.crear_miniaturas_faltantes`) o el comando `crear_miniaturas`; si la original ya no se
    puede leer, la miniatura apunta a ella para no reintentarlo.
  - Medicion propia (`core.metricas`, tabla `core.ConteoDiario`): solo cuantas veces paso cada evento por dia y
    tienda (busquedas y sin resultados, visitas a tiendas, productos vistos, agregados al carrito, inicios de compra,
    errores al confirmar). Sin IP, cuenta ni texto buscado; no cuenta robots, peticiones sin navegador ni al
    personal del panel; nunca rompe la pagina. Pedidos y solicitudes salen de sus tablas. Inicio del panel
    (`admin/_indicadores.html`): el superusuario ve "El sitio" (tiendas, productos publicados, solicitudes y su
    conversion solo con 5 revisadas o mas) y la actividad de todas las tiendas; el vendedor, solo la de las suyas.
    En las pruebas hay que mandar `HTTP_USER_AGENT` de un navegador para que cuente.
  - `requirements*.txt` con tope en la siguiente version mayor: Render instala lo mas nuevo en cada despliegue.
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
- Vender en el sitio (Fase 2 del rediseño, 2026-10-27): no hay alta propia; las tiendas las sigue creando el
  superusuario. `/vender/` (`tiendas:vender`) explica como funciona, lo que trae una tienda y preguntas frecuentes, sin
  prometer precios, comisiones, aprobacion automatica ni plazos. "Solicitar mi tienda" (`/vender/solicitar/`, abierta
  sin sesion) guarda una `tiendas.SolicitudTienda` en estado pendiente (`services.registrar_solicitud`: correo al
  sitio con el enlace del panel y confirmacion a quien la envia; limite 3 por IP y hora, 2 por correo y dia y 40 en el
  sitio por dia; honeypot `sitio_web`) y lleva a `/vender/solicitud-enviada/`. No crea cuentas ni da acceso: el
  superusuario la revisa en Panel > Solicitudes de tiendas (`SolicitudTiendaAdmin`, solo `ve_todas`; los vendedores
  no la ven), cambia su estado (`revisar_solicitud` anota quien y cuando) y "Crear la tienda con estos datos" abre el
  alta de la tienda con nombre y contactos puestos; los vendedores se asignan alli como siempre. El inicio del panel
  avisa de las pendientes. Todos los accesos ("Vende en...", la seccion `#vender` de la portada, el menu y el pie)
  llevan a `/vender/` o al formulario; `como_vender` (WhatsApp, correo o contacto) queda como "¿Prefieres hablar
  antes?". Dentro de una tienda no se ofrece. La direccion del panel (`ADMIN_URL`, secreta a pedido del dueño) solo se enlaza al personal
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
- Buscador con sugerencias: `catalogo.services.sugerencias` (minimo 2 letras) en `/tienda/<slug>/sugerencias/` y
  `/sugerencias/` (todo el sitio). El desplegable se arma en `tienda.js` con nodos, nunca con HTML del servidor.
  `/buscar/?categoria=<slug>` limita el buscador del sitio a una categoria con sus subcategorias (una que no existe
  o esta apagada se ignora, como los demas filtros). Fase 3 del rediseño (2026-10-27): el buscador del sitio tiene
  los filtros del catalogo de una tienda (precio, oferta, disponibles, orden) mas `?tienda=<slug>` (solo activas),
  filtros aplicados que se quitan uno a uno y "Limpiar filtros"; arriba muestra las tiendas que coinciden
  (`tiendas.services.buscar_tiendas`: nombre, descripcion y categorias principales, sin tildes, en Python porque
  son pocas). `/sugerencias/` devuelve tambien `tiendas` y el desplegable muestra "Buscando…", grupos Tiendas y
  Productos y "No encontramos nada" con "Buscar de todos modos".
- Politicas al dia (pedido del dueño el 2026-10-27; `core/0023`): metodos de pago con comprobante obligatorio,
  privacidad con las solicitudes de tiendas y la medicion sin datos personales, entregas con la fecha estimada,
  contacto con el nombre comercial (el sitio aun no esta registrado: sin razon social ni RNC hasta que el dueño los
  de) y la pagina nueva "Condiciones para vendedores" (`condiciones-para-vendedores`, con los dias de aviso y de
  gracia de la configuracion; en el pie con lo legal, enlazada en /vender/, la solicitud y los terminos). La migracion
  solo cambia frases del texto estandar que sigan tal cual. Los terminos dicen que cada tienda cobra en sus cuentas.
  Al aprobar o rechazar una solicitud el negocio recibe un correo (`services.avisar_resultado_de_solicitud`, solo al
  cambiar el estado, sin las notas internas). Para despues, decidido por el dueño: carrito unico junto con la
  tarjeta; los precios de los planes no se publican.
- Directorio de tiendas (`tiendas.services.directorio`, portada y `/tiendas/`): solo las activas, con
  `total_productos` contado como en el catalogo (una vez por grupo de variantes); `para_el_directorio` agrega sus
  categorias con mas productos y el tono de su franja si no tiene banner, con una consulta para todas.
- Experiencia de compra (tomado de las grandes tiendas; la primera barra inferior del celular se quito porque al
  dueño no le gusto y volvio rediseñada el 2026-10-26, ver "Barra del telefono"): estrellas en las tarjetas
  (`ProductoQuerySet.con_valoracion`, subconsultas, dentro de `para_listado`), vistos recientemente en la sesion
  (`catalogo.services.recordar_visto`/`vistos`; dentro de una tienda solo los suyos, porque la tarjeta agrega al
  carrito de esa tienda), cuenta regresiva si la oferta termina en 7 dias o menos, barra de compra fija en la
  ficha (celular), "Completa tu pedido" en el carrito (`sugerencias_para_el_carrito`, con `q_comprable`),
  sugerencias cuando una busqueda no encuentra nada y JSON-LD del sitio (SearchAction) y de la ruta del producto.
  Las valoraciones se muestran con punto decimal (`floatformat:"1u"`): el locale `es` pondria coma.
- Marca: paleta del dueño del 2026-10-27 (Fase 1 del rediseño; reemplaza la azul `#244BFF` del 2026-10-25) en las
  variables de `:root` de `tienda.css`, unico lugar de colores, radios, sombras y espacios (los `rgba` usan
  `--mm-*-rgb`): carbon `#111827` (identidad, botones, titulos, precios), ambar `#F59E0B` con texto carbon solo para
  acciones importantes y ofertas (`.btn-acento`: buscar, la accion principal de la portada, comprar ahora, confirmar
  el pedido, boton del banner), `--mm-calido-texto` `#B45309` para ambar sobre fondo claro (el `#F59E0B` no se lee
  sobre blanco), fondo `#F3F4F6`, tarjetas blancas, texto secundario `#64748B`, bordes `#E5E7EB`; verde solo para lo
  que salio bien. Los enlaces van en carbon: dentro de un texto (`.mm-legal-texto`) se subrayan. `panel.css` sigue
  con la misma paleta desde el 2026-10-27 (enlaces en ambar oscuro `#b45309`). Recursos en `static/img/`. El encabezado del sitio muestra el simbolo estatico con el nombre salvo
  que haya un logo en Configuracion; el de cada tienda, su logo o su nombre, con una franja encima para volver a
  "Todas las tiendas".
- Ajustes del dueño del 2026-10-27/28:
  - Menu de las 3 barras en botones que se despliegan (Comprar o la tienda, Mi cuenta, Ayuda; uno abierto a la vez,
    `data-bs-parent`), con "Vende en..." / "Mi panel" e "Instalar la app" como accesos directos. Sin "Tu compra,
    protegida" (y sin `includes/confianza.html`).
  - Portada sin "Descubre productos" ni "Compra con confianza". Promociones en un carrusel que rota solo (`js-promos`
    en `tienda.js`; sin autoplay con "reducir movimiento"): anuncios aprobados, productos patrocinados y hasta 4
    ofertas reales (`planes.services.promociones_para`), primero lo que coincide con lo que el visitante busco
    (`catalogo.services.recordar_busqueda`, solo en su sesion), miro o dijo que le gusta. Cada una dice "Anuncio" u
    "Oferta -N%"; con coincidencias el titulo es "Elegidas para ti". Los productos de la bienvenida siguen tambien en
    el telefono.
  - El cliente no ve cantidades: ni existencias (el campo de cantidad ofrece `Producto.tope_a_la_vista`, el tope por
    pedido, y el carrito ajusta sin cifras) ni cuantos productos hay por categoria, tienda o busqueda. La opcion
    `mostrar_cantidad_exacta` ya no se usa (quedo fuera del panel).
- Panel del dueño de tienda, fase 1 (2026-10-28, pedido del dueño: "mas facil, puntos claros y menos pasos"): el inicio
  del vendedor (`templates/admin/_inicio_vendedor.html`) va en este orden: lo que debe al sitio (si debe), "Deja lista
  tu tienda" (WhatsApp, cuenta de banco, producto con foto, forma de entrega; desaparece cuando esta todo), "Para hacer
  ahora" (`core.panel.tareas_de_la_tienda`: cada fila lleva a la lista ya filtrada), accesos rapidos, ventas, ultimos
  pedidos, lo mas vendido, por reponer, actividad plegada, plan en una linea y "Todo tu panel". El menu del vendedor se
  agrupa en `core.admin_site.MENU_DEL_VENDEDOR` (solo cambia nombres y orden, no permisos); el superusuario conserva el
  menu y el inicio de siempre. Titulos simples para todos: "Productos", "Agregar producto", "Editar producto".
- Panel del dueño de tienda, separado del administrador (2026-10-28): el vendedor no ve lo del reparto viejo
  (filtros "lo cobra el sitio" y "liquidación", "Reparto a la tienda", "Lo confirma", la pasarela) ni Liquidaciones si
  su tienda no tiene. Su ruta de arriba es "Inicio › Productos › X" (plantillas admin/change_list.html y
  change_form.html). Numeritos de pendientes en el menu (`core.panel.pendientes_del_menu`,
  `admin_site.PANTALLAS_CON_PENDIENTES`, plantilla admin/app_list.html copiada de Django) que, junto con "Para hacer
  ahora" y el titulo de la pestaña, se actualizan solos cada minuto (`admin:pendientes`, static/js/panel.js). En el
  telefono sus listas se ven como tarjetas con el nombre de cada columna (CSS con `html:has(meta[name=pv-pendientes])`).
