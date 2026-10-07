# Multimix RD

Tienda online (Django) con precios en pesos dominicanos. El pedido se cierra por WhatsApp y el
pago se confirma a mano desde el panel.

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
- `core/` — ConfiguracionTienda (fila unica), CuentaBancaria, panel (AdminSite propio), filtro `moneda`,
  telefonos RD, paginas informativas, sitemap/robots, comando `cargar_demo`.
- `catalogo/` — Categoria, Producto, FotoProducto; vistas de inicio, catalogo y detalle.
- `promociones/` — Cupon y su validacion.
- `carrito/` — carrito en sesion (sin modelo).
- `pedidos/` — ZonaEnvio, Pedido, DetallePedido; checkout, confirmacion, mensaje de WhatsApp.
- `templates/`, `static/` — plantillas y recursos de la tienda y del panel.
- `docs/` — DESPLIEGUE.md y esquema.sql (referencia; las tablas las crea `migrate`).

## Reglas que no se rompen
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
- En los tests la cache es `DummyCache` para que cada prueba sea independiente.
- Telefonos guardados como 10 digitos (`8095551234`); para wa.me se antepone `1`.
- `PanelAdminConfig` vive en `config/apps.py` (no en `core/apps.py`: Django no admite dos AppConfig por
  defecto en un modulo). El sitio es `core.admin_site.PanelAdminSite`; el resumen sale de `core/panel.py`.
- Numero de pedido `MMX-AAAA-NNNNN` con la tabla `SecuenciaPedido` (una fila por año, bloqueada al crear).
- `Pedido.ip` guarda la IP para el limite anti-spam (`PEDIDOS_MAX_POR_IP` por `PEDIDOS_VENTANA_IP_MINUTOS`).
  Con `DEBUG=False` se lee de `X-Real-IP`, que pone Nginx.
- Ventas del panel = pedidos con `fecha_pago` y no cancelados. "Mas vendidos" = unidades en pedidos
  Pagado/Listo/Enviado/Entregado, con cache de 5 minutos.
- Contra entrega solo aplica a envio a domicilio; para recoger existe "Efectivo al recoger".
- Pedido pagado puede pasar directo a Entregado (el cliente lo recoge en el momento).
- El cupon vive en la sesion del carrito; el checkout lo revalida y `crear_pedido` lo bloquea y cuenta el uso.
- "Ya hice la transferencia" se marca en el checkout o en la pagina de confirmacion; nunca cambia el estado.
- Busqueda sin tildes: `Producto.texto_busqueda` (nombre + SKU + descripcion normalizados en `save()`).
  Ojo: `queryset.update()` de nombre/descripcion no lo refresca.
- Correo del cliente opcional en el checkout (el contacto es por WhatsApp).
- Los pedidos no se crean desde el panel; en su formulario solo se editan las notas internas.
- Los pedidos si se eliminan desde el panel (boton del detalle y accion de la lista), siempre con
  `pedidos.services.eliminar_pedido`: si aun se podia cancelar lo cancela primero (reserva y cupon); lo
  enviado o entregado no devuelve stock. El numero no se reutiliza y el pedido sale de las ventas del panel.
- Importacion Excel: `catalogo/resources.py`, identifica por `sku`, crea categorias que no existan y valida
  con `full_clean`. No importa fotos ni `stock_reservado`.
- Marca: azul y verde del logo en las variables de `tienda.css` y `panel.css`; recursos en `static/img/`. El
  encabezado muestra el simbolo estatico con `tienda.nombre` salvo que haya un logo subido en Configuracion.
  El acento es un verde mas oscuro que el de la hoja (`--mm-hoja`, solo decorativo) para que el texto blanco se lea.
- Portada: `catalogo.services.categorias_de_portada` da a cada categoria sin imagen la foto de uno de sus productos.
- `core/migrations/0002` quita de la configuracion el logo o banner cuyo archivo ya no existe en el
  almacenamiento (se perdieron los que se subieron cuando los archivos iban al disco de Render).
- Fotos por SKU: `catalogo.services.asignar_foto_por_sku` usa el nombre del archivo como SKU y deja la foto
  como principal. La pagina del panel las envia una por una con `fetch` (cada foto se convierte y se sube al
  almacenamiento; en una sola peticion se agotaria el tiempo de Gunicorn). Sin JavaScript funciona con un POST normal.
- Acciones del admin: las descripciones pasan por formato `%`, asi que un `%` literal se escribe `%%`.
- `docs/esquema.sql` se genera con `sqlmigrate` sobre SQLite; regenerarlo si cambian las migraciones.

## Pruebas manuales
- Los tests usan `assertRedirects(..., fetch_redirect_response=False)` cuando despues se revisan mensajes
  o la apertura automatica de WhatsApp: seguir la redireccion los consume.
