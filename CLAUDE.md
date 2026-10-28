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

## Antes de tocar codigo (lo que rompe cosas en cualquier parte)
- CSP sin 'unsafe-inline' en scripts: nada de `<script>` sin `src` ni `onclick=` en plantillas (lo revisa
  `core/test_seguridad.py`); el JS va en `static/js/`. `form-action 'self'`.
- Migraciones que cambian datos y esquema de una tabla: en archivos separados (PostgreSQL no deja alterar la tabla
  en la transaccion que cambio sus filas). Siempre aditivas; produccion corre `migrate` al desplegar.
- El campo `tienda` de los formularios del panel nunca se excluye (oculto o deshabilitado): si no, las unicidades por
  tienda fallan con IntegrityError. `tienda.usuarios.add()` a secas no da permisos: `dar_acceso_al_panel`.
- Correos con `transaction.on_commit` (`core.correo.enviar`, nunca lanza): en pruebas, `captureOnCommitCallbacks`.
- Al agrupar con `annotate` Django ignora el `ordering` del modelo: ordenar a mano. En acciones del admin un `%` es `%%`.
- El cliente nunca ve existencias ni cuantos productos hay (pedido del dueño el 2026-10-27); nada inventado (reseñas,
  stock, plazos, pagos). Paleta: carbon `#111827` y ambar `#F59E0B` (variables de `tienda.css`).
- Fotos con nombre generado (`NombreUnico`, uuid): Supabase rechaza tildes y ñ. Las tarjetas usan `url_tarjeta`.
- Publicar: `docs/RENDER.md`, "Publicar un cambio sin riesgo" (cherry-pick en `multimix_rd_github`, Manual Deploy).

## Donde esta cada decision (leer el archivo del tema antes de cambiarlo)
- `docs/decisiones/pagos-y-planes.md` — cada tienda cobra lo suyo, planes y cargos, videos, comprobantes privados,
  reparto viejo del sitio, ITBIS, cupones, envio gratis. Ver tambien `docs/PAGOS.md`.
- `docs/decisiones/catalogo-y-pedidos.md` — variantes, disponibilidad, importacion y fotos por SKU, carrito, checkout,
  estados y eliminacion de pedidos, factura y QR, fecha de entrega, "avisame".
- `docs/decisiones/sitio-y-diseno.md` — portada y promociones, cabecera, barra del telefono, filas, marca, buscador,
  directorio, vender, politicas, PWA, JSON-LD, miniaturas y medicion (fase 4).
- `docs/decisiones/cuentas-y-seguridad.md` — CSP, referrer del pedido, entrar, cuentas de clientes, limite de intentos,
  IP, correo confirmado, cuenta obligatoria, WhatsApp con codigo de pais.
- `docs/decisiones/tecnico.md` — tareas periodicas sin cron, imagenes, correos, Supabase, rutas, migracion a
  subtiendas, particularidades de Django y del admin.
- `docs/RENDER.md` (despliegue, base, buckets), `docs/WHATSAPP.md`, `docs/esquema.sql` (referencia).

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
