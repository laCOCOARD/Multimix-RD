# Multimix RD

Sitio de tiendas online (Django) con precios en pesos dominicanos. Reune varias subtiendas de vendedores
independientes: cada una con su catalogo, carrito, WhatsApp, cuentas y pedidos. El pedido se cierra por
WhatsApp con la tienda y el pago lo confirma a mano el vendedor desde el panel.

## Stack (fijo)
- Python 3.13, Django 5.2 LTS, entorno virtual en `.venv`.
- Plantillas Django + CSS + JavaScript sin frameworks. Bootstrap 5 y Bootstrap Icons por CDN, sin `integrity`.
- Sin React, Node, Tailwind ni pasos de build.
- Base de datos por `.env` (`DB_ENGINE`: sqlite | postgresql | mysql). Ninguna credencial en el codigo.
- Dependencias: `requirements.txt` (Django, Pillow, django-import-export[xlsx], python-dotenv) y
  `requirements-prod.txt` (gunicorn, psycopg).
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
  panel, grupo Vendedores, portada (directorio), buscador del sitio y enlaces anteriores.
- `core/` — ConfiguracionTienda (fila unica, ajustes del sitio), CuentaBancaria, panel (AdminSite propio),
  filtro `moneda`, telefonos RD, paginas informativas, sitemap/robots, comando `cargar_demo`.
- `catalogo/` — Categoria (comun a todas las tiendas), Producto, FotoProducto; inicio, catalogo y detalle de cada tienda.
- `promociones/` — Cupon y su validacion.
- `carrito/` — carrito en sesion, uno por tienda (sin modelo).
- `pedidos/` — ZonaEnvio, Pedido, DetallePedido, SecuenciaTienda; checkout, confirmacion, clientes, WhatsApp.
- `templates/`, `static/` — plantillas y recursos de la tienda y del panel.
- `docs/` — DESPLIEGUE.md y esquema.sql (referencia; las tablas las crea `migrate`).

## Reglas que no se rompen
- Nada cruza de una tienda a otra. Producto, Pedido, Cupon, ZonaEnvio y CuentaBancaria llevan `tienda`.
  En el sitio toda vista de tienda usa `@de_tienda` y filtra por `request.tienda`; en el panel todo
  ModelAdmin con datos de tienda hereda `tiendas.panel.AdminDeTienda`. Un modelo o una pantalla nueva
  entra con su prueba de aislamiento (`tiendas/tests/`).
- Solo el superusuario ve todas las tiendas (`tiendas.services.ve_todas`); el resto, las de `Tienda.usuarios`.
- La logica de negocio vive en `services.py` de cada app, no en vistas ni plantillas.
- Montos siempre calculados en el servidor; nunca se confia en montos del navegador.
- Stock: `transaction.atomic` + `select_for_update`. `stock_reservado` solo lo toca `pedidos/services.py`.
- El estado del pedido solo cambia con `pedidos.services.cambiar_estado` (lo usa el panel).
- El cliente nunca marca un pedido como pagado; solo "Ya hice la transferencia".
- Montos en plantillas con `{{ valor|moneda }}` -> `RD$ 1,250.00`.
- Nada de `|safe` con datos de usuarios. Solo ORM.

## Decisiones tomadas
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
- La portada del sitio (directorio) no lleva banner ni boton de catalogo, a pedido del dueño: se veia igual
  que el inicio de una tienda. El banner (`mm-banner`) es solo de las tiendas; la portada usa `mm-directorio`.
- WhatsApp siempre con codigo de pais: `core.telefonos.normalizar_whatsapp` antepone el 1 a los numeros
  dominicanos de 10 digitos. Se aplica al validar y guardar Tienda y ConfiguracionTienda y, por si acaso, al
  armar cada enlace (`construir_enlace`). Sin el 1, wa.me abre un numero de otro pais.
- Los ModelAdmin con imagenes heredan `core.admin_avisos.AvisaImagenesSinGuardar`: si el formulario vuelve
  con errores, el navegador olvida los archivos elegidos y hay que avisarlo.
- Rutas de tienda bajo `/tienda/<tienda_slug>/` (`tiendas.decoradores.RUTA_DE_TIENDA`). `pedidos` y `core`
  mezclan rutas de tienda y del sitio, por eso declaran las suyas completas y se incluyen en la raiz.
  Las paginas por token (confirmacion, factura) ponen `request.tienda = pedido.tienda`.
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
- "Ya hice la transferencia" se marca en el checkout o en la pagina de confirmacion; nunca cambia el estado.
- Busqueda sin tildes: `Producto.texto_busqueda` (nombre + SKU + descripcion normalizados en `save()`).
  Ojo: `queryset.update()` de nombre/descripcion no lo refresca.
- Correo del cliente opcional en el checkout (el contacto es por WhatsApp).
- Los pedidos no se crean desde el panel; en su formulario solo se editan las notas internas.
- Los pedidos si se eliminan desde el panel (boton del detalle y accion de la lista), siempre con
  `pedidos.services.eliminar_pedido`: si aun se podia cancelar lo cancela primero (reserva y cupon); lo
  enviado o entregado no devuelve stock. El numero no se reutiliza y el pedido sale de las ventas del panel.
- Importacion Excel: `catalogo/resources.py`, identifica por `sku` dentro de la tienda elegida en el
  formulario y valida con `full_clean`. Solo el superusuario crea categorias al importar. No importa fotos
  ni `stock_reservado`.
- Marca: azul y verde del logo en las variables de `tienda.css` y `panel.css`; recursos en `static/img/`. El
  encabezado del sitio muestra el simbolo estatico con el nombre salvo que haya un logo en Configuracion; el
  de cada tienda, su logo o su nombre, con una franja encima para volver a "Todas las tiendas".
  El acento es un verde mas oscuro que el de la hoja (`--mm-hoja`, solo decorativo) para que el texto blanco se lea.
- Inicio de tienda: `catalogo.services.categorias_de_portada(tienda)` trae las categorias con productos de
  la tienda y da a la que no tiene imagen la foto de uno de ellos.
- `core/migrations/0002` quita de la configuracion el logo o banner cuyo archivo ya no existe en el
  almacenamiento (se perdieron los que se subieron cuando los archivos iban al disco de Render).
- Fotos por SKU: `catalogo.services.asignar_foto_por_sku` usa el nombre del archivo como SKU (dentro de la
  tienda) y deja la foto como principal. La pagina del panel las envia una por una con `fetch` (cada foto se convierte y se sube al
  almacenamiento; en una sola peticion se agotaria el tiempo de Gunicorn). Sin JavaScript funciona con un POST normal.
- Acciones del admin: las descripciones pasan por formato `%`, asi que un `%` literal se escribe `%%`.
- `docs/esquema.sql` se genera con `sqlmigrate` sobre SQLite; regenerarlo si cambian las migraciones.
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
