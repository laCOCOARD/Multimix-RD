# Multimix RD

Sitio de tiendas en línea hecho con Django 5.2, con precios en pesos dominicanos (RD$). Reúne varias
**tiendas** de emprendedores: cada una tiene su catálogo, su carrito, su WhatsApp, sus cuentas y sus
pedidos. El cliente entra a una tienda, arma su carrito, confirma el pedido y lo envía por WhatsApp a
esa tienda; el pago (transferencia o efectivo) lo recibe y lo confirma el vendedor desde su panel.

- **Sitio:** portada con el directorio de tiendas (sin banner, para que no se confunda con una tienda) y
  buscador de productos de todas las tiendas.
- **Cada tienda:** inicio con ofertas, destacados, nuevos y más vendidos; catálogo con búsqueda y filtros;
  carrito propio; checkout con totales calculados en el servidor; confirmación con botón de WhatsApp.
- **Panel:** resumen de ventas y stock, productos (con importación desde Excel), pedidos, clientes,
  cupones, zonas de envío y cuentas bancarias. Cada vendedor ve solo lo de su tienda; el administrador
  principal ve todo y además administra las tiendas, las categorías y la configuración general.
- **Stack:** Python 3.13 (o 3.12), Django 5.2, Bootstrap 5 por CDN, JavaScript sin frameworks.
  SQLite en desarrollo; PostgreSQL (o MySQL 8) en producción. WhiteNoise sirve los archivos estáticos.

## Cómo funciona una compra

1. El cliente entra a una tienda desde la portada y agrega productos a su carrito (vive en la sesión, no
   necesita cuenta). Hay un carrito por tienda: para comprar en otra, sale y entra a la otra, y los
   carritos no se mezclan. Puede aplicar un cupón de esa tienda.
2. En el checkout elige recoger o envío a domicilio (por zona de la tienda) y la forma de pago:
   transferencia, efectivo al recoger o contra entrega. Los totales se calculan siempre en el servidor.
3. Al confirmar se crea el pedido en estado **Pendiente** y se reserva el stock. Cada tienda numera sus
   pedidos aparte con su prefijo: `MMX-AAAA-NNNNN`, `FIT-AAAA-NNNNN`...
4. La página de confirmación muestra las cuentas bancarias de la tienda y abre su WhatsApp con el pedido
   ya escrito.
   También permite abrir la factura como imagen PNG con un QR único para verificar el pedido.
   La verificación no muestra datos personales ni acredita el pago. El cliente puede avisar
   "Ya hice la transferencia"; eso no cambia el estado.
5. El vendedor confirma el pago y avanza el pedido desde el panel. Los pedidos pendientes que
   vencen los cancela el comando `cancelar_pedidos_vencidos`, que devuelve el stock.

## Requisitos

- Python 3.13 o 3.12
- Git

## Instalación en Windows (PowerShell)

```powershell
git clone <url-del-repositorio> multimix_rd
cd multimix_rd

py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-prod.txt

Copy-Item .env.example .env
# Genera una clave y pégala en SECRET_KEY dentro de .env:
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"

python manage.py migrate
python manage.py createsuperuser
python manage.py cargar_demo
python manage.py runserver
```

Si PowerShell no deja activar el entorno, ejecuta una vez
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Instalación en Linux / macOS

```bash
git clone <url-del-repositorio> multimix_rd
cd multimix_rd

python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-prod.txt

cp .env.example .env
# Genera una clave y pégala en SECRET_KEY dentro de .env:
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"

python manage.py migrate
python manage.py createsuperuser
python manage.py cargar_demo
python manage.py runserver
```

Se instala `requirements-prod.txt` también en desarrollo: `config/settings.py` importa `whitenoise` y
`dj-database-url`, que solo están en ese archivo. Con `requirements.txt` a secas el proyecto no arranca.

Luego abre:

- Sitio: <http://127.0.0.1:8000/>
- Panel: <http://127.0.0.1:8000/panel/> (la ruta sale de `ADMIN_URL` en `.env`)

### Rutas

Del sitio:

| Ruta                          | Página                                            |
| ----------------------------- | ------------------------------------------------- |
| `/`                           | Portada con el directorio de tiendas              |
| `/buscar/`                    | Productos de todas las tiendas, con búsqueda      |
| `/terminos/`                  | Términos: quién vende y quién responde            |
| `/pedido/<token>/`            | Confirmación del pedido (enlace privado por UUID) |
| `/pedido/<token>/factura.png` | Imagen de factura/comprobante del pedido          |
| `/pedido/<token>/verificar/`  | Verificación pública del pedido desde el QR       |
| `/sitemap.xml`, `/robots.txt` | SEO                                               |

De cada tienda, todas bajo `/tienda/<tienda>/`:

| Ruta                                 | Página                                             |
| ------------------------------------ | -------------------------------------------------- |
| (raíz)                               | Inicio: ofertas, destacados, nuevos y más vendidos |
| `catalogo/`, `categoria/<slug>/`     | Catálogo con búsqueda y filtros                    |
| `producto/<slug>/`                   | Detalle del producto                               |
| `carrito/`                           | Carrito y cupón de la tienda                       |
| `pedido/checkout/`                   | Checkout                                           |
| `como-comprar/`, `envios-y-retiros/` | Formas de pago, cuentas y zonas de la tienda       |

Los enlaces de cuando había una sola tienda (`/catalogo/`, `/producto/<slug>/`, `/carrito/`...) redirigen
a la tienda más antigua.

`cargar_demo` crea dos tiendas de ejemplo (Multimix RD y Rincón Fitness) con 6 categorías, 24 productos
con imágenes, un cupón de 10 % por tienda (`BIENVENIDO10` y `FIT10`), zonas de envío, cuentas bancarias y
5 pedidos de ejemplo. Se puede ejecutar varias veces sin duplicar nada y no pisa los datos que ya hayas
cambiado. Si ya existe una tienda, la primera recibe el catálogo principal.

## Configuración (.env)

| Variable                                                                           | Para qué sirve                                                                                                                          |
| ---------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `SECRET_KEY`                                                                       | Clave secreta de Django. Obligatoria y distinta en cada instalación.                                                                    |
| `DEBUG`                                                                            | `True` en desarrollo, `False` en producción.                                                                                            |
| `ALLOWED_HOSTS`                                                                    | Dominios permitidos, separados por coma.                                                                                                |
| `CSRF_TRUSTED_ORIGINS`                                                             | Orígenes con esquema, separados por coma (`https://tudominio.com`).                                                                     |
| `ADMIN_URL`                                                                        | Ruta del panel, sin barras (`panel`). Cámbiala en producción.                                                                           |
| `DB_ENGINE`                                                                        | `sqlite`, `postgresql` o `mysql`.                                                                                                       |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`                          | Datos de conexión. Con SQLite solo se usa `DB_NAME` (nombre del archivo).                                                               |
| `DATABASE_URL`                                                                     | Opcional. Si existe, **manda sobre** `DB_ENGINE` y las `DB_*` (`postgres://usuario:clave@host:5432/base`). Con `DEBUG=False` exige SSL. |
| `RENDER_EXTERNAL_HOSTNAME`                                                         | La pone Render sola; se agrega a `ALLOWED_HOSTS` y a `CSRF_TRUSTED_ORIGINS`.                                                            |
| `MEDIA_STORAGE`                                                                    | `local` (por defecto) o `supabase` para guardar las imágenes en Supabase Storage.                                                       |
| `SUPABASE_URL`, `SUPABASE_S3_ENDPOINT`, `SUPABASE_S3_REGION`, `SUPABASE_S3_BUCKET` | Datos de proyecto, endpoint S3, región y bucket; se copian de Supabase.                                                                 |
| `SUPABASE_S3_ACCESS_KEY_ID`, `SUPABASE_S3_SECRET_ACCESS_KEY`                       | Credenciales S3 para el servidor. Nunca se publican en el navegador.                                                                    |

Para Supabase, crea un bucket **público** para las imágenes y activa la conexión S3 de Storage.
Copia el endpoint, la región y las claves S3 desde el panel de Supabase. Pon `MEDIA_STORAGE=supabase`
solo después de cargar al bucket las imágenes existentes de `media/`; las rutas guardadas por Django
se conservan. Las claves S3 dan acceso amplio al almacenamiento y deben quedar solo en las variables
de entorno del servidor.

Con `DEBUG=False` se activan solas las cookies seguras, HSTS, la redirección a HTTPS y
`SECURE_PROXY_SSL_HEADER`. Además hay que ejecutar `python manage.py collectstatic` antes de arrancar:
los estáticos se sirven con WhiteNoise desde `staticfiles/` con nombres versionados, y sin ese paso las
páginas fallan. Con `DEBUG=True` no hace falta.

Los errores de la aplicación quedan en `logs/multimix.log` (rota a los 2 MB, guarda 5 archivos).

### Cambiar de base de datos

No hay que tocar código: solo `.env` (y el driver, en el caso de MySQL).

**PostgreSQL** (recomendado en producción; el driver ya viene en `requirements-prod.txt`):

```ini
DB_ENGINE=postgresql
DB_NAME=multimix
DB_USER=multimix
DB_PASSWORD=tu-clave
DB_HOST=localhost
DB_PORT=5432
```

**MySQL 8** (8.0.16 o superior, para que respete las restricciones CHECK):

```bash
pip install mysqlclient
```

```sql
CREATE DATABASE multimix CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

```ini
DB_ENGINE=mysql
DB_NAME=multimix
DB_USER=multimix
DB_PASSWORD=tu-clave
DB_HOST=localhost
DB_PORT=3306
```

En ambos casos, después ejecuta `python manage.py migrate`.

## Uso del panel

Entra a `/panel/` con el usuario creado con `createsuperuser`: es el **administrador principal** y ve
todas las tiendas.

### Tiendas y vendedores

Para abrir una tienda nueva (solo el administrador principal):

1. **Usuarios → Añadir**: crea el usuario del vendedor con su contraseña.
2. **Tiendas → Añadir**: escribe el nombre, deja vacíos _Dirección web_ y _Prefijo de pedidos_ (se generan
   solos) o escríbelos, y pasa al usuario a _Vendedores_. Al guardar, ese usuario ya puede entrar al panel.
3. El vendedor completa su tienda desde el panel: logo, banner, WhatsApp, dirección para recoger, redes y
   si acepta contra entrega; y carga sus productos, zonas de envío, cuentas bancarias y cupones.

Al llenar el formulario de una tienda:

- **Logo e imagen del banner:** JPG, PNG o WebP de hasta 5 MB. Si al guardar aparece algún error, el
  navegador olvida las imágenes elegidas: hay que corregir el error y **volver a elegirlas** (el panel lo
  avisa arriba). También se pueden subir después, editando la tienda.
- **WhatsApp:** se puede escribir como `829-555-1234`; a los números dominicanos se les agrega solo el `1`
  del código de país, que WhatsApp necesita para abrir el chat correcto.

- El enlace de la tienda es `/tienda/<dirección-web>/`. El prefijo (`FIT`) inicia sus números de pedido
  y no se puede cambiar después.
- **Activa** apagada oculta la tienda y sus productos del sitio sin borrar nada.
- Un vendedor ve y cambia **solo lo de su tienda**: productos, pedidos, clientes, cupones, zonas y
  cuentas. No ve lo de otras tiendas, ni las categorías, la configuración general o los usuarios. Sus
  permisos salen del grupo _Vendedores_, que se crea solo.
- Una tienda puede tener varios vendedores, y un usuario puede estar en varias tiendas.
- Una tienda con productos o pedidos no se puede borrar; se apaga.

**Portada.** Ventas del día y del mes (pedidos cobrados), pedidos pendientes, productos con stock bajo
o agotados, últimos pedidos y los 5 más vendidos. El vendedor ve los de su tienda; el administrador
principal ve el total del sitio y las ventas del mes por tienda.

**Configuración general** (administrador principal). Nombre del sitio, logo, descripción (sale al pie de
la portada y en los buscadores), contacto, días en que un producto cuenta como nuevo, umbral de stock
bajo, horas para vencer pedidos pendientes y si se muestra la cantidad exacta. La portada del sitio no
tiene banner: el banner es de cada tienda. Solo existe una configuración: no se puede crear otra ni
borrarla. Los cambios pueden tardar hasta un minuto en verse en el sitio.

**Productos.**

- La lista muestra foto, precio, oferta, almacén, reservado y disponible con color (verde: normal,
  naranja: stock bajo, rojo: agotado). Destacado, nuevo y activo se editan desde la misma lista.
- _Stock reservado_ lo maneja el sistema: sube cuando entra un pedido y baja cuando se entrega o se
  cancela. El almacén no puede quedar por debajo de lo reservado.
- Las fotos se suben en JPG, PNG o WebP (hasta 5 MB); se ajustan a 1200 px y se guardan en WebP.
- El SKU no se repite dentro de una tienda; dos tiendas sí pueden usar el mismo.
- **Fotos por SKU** (botón de la lista): sube muchas fotos a la vez. El nombre de cada archivo es el SKU
  del producto (`123785.jpg`) y la foto queda como principal; al terminar lista las que no encontraron
  producto. Se puede elegir reemplazar las fotos que ya tenía cada producto. Solo busca entre los
  productos de la tienda; quien administra varias elige cuál.
- Acciones masivas: destacar, activar/desactivar, poner oferta de X % con fechas y quitar oferta.

**Pedidos.**

- Entran como **Pendiente**. El cliente puede avisar "Ya hice la transferencia", pero el estado solo
  lo cambia el administrador, con los botones del detalle o las acciones de la lista.
- Transferencia: Pendiente → Pagado → Listo para recoger / Enviado → Entregado.
- Efectivo (al recoger o contra entrega): puede pasar directo a Listo para recoger / Enviado, y queda
  pagado al marcarse Entregado.
- Se puede cancelar desde Pendiente, Pagado o Listo para recoger: se libera el stock y se devuelve el
  uso del cupón.
- Al pasar a Enviado o Entregado el stock sale del almacén (una sola vez).
- El teléfono del cliente abre un chat de WhatsApp con él.
- Se pueden eliminar del historial, en cualquier estado, con el botón **Eliminar** del detalle o la acción
  "Eliminar pedidos seleccionados" de la lista; ambos piden confirmación. Si el pedido seguía pendiente,
  pagado o listo para recoger, primero se cancela (libera el stock y el uso del cupón). Uno enviado o
  entregado se borra sin devolver unidades al almacén. Lo eliminado deja de contar en las ventas del panel.

**Clientes** (botón en Pedidos y en la portada). Lista de quienes han pedido en la tienda, por teléfono:
nombre, WhatsApp, cantidad de pedidos, total comprado y último pedido. Sale de los pedidos; quien compra
en dos tiendas aparece en cada una por separado.

**Cupones, zonas de envío y cuentas bancarias** son de cada tienda y se administran desde sus secciones.
Los cupones muestran sus usos (`usados / máximo`). Las **categorías** son comunes a todas las tiendas y
las administra el administrador principal.

### Pedidos vencidos

```bash
python manage.py cancelar_pedidos_vencidos
```

Cancela los pedidos pendientes más viejos que las horas configuradas y libera su stock. En producción
se programa con cron (ver `docs/DESPLIEGUE.md`).

## Importar productos desde Excel

1. En **Productos**, pulsa **Plantilla de Excel** para descargar `plantilla_productos.xlsx`.
2. Llena una fila por producto:

   | Columna                        | Contenido                                                                     |
   | ------------------------------ | ----------------------------------------------------------------------------- |
   | `sku`                          | Código único en la tienda. Si ya existe, se **actualiza**; si no, se **crea**. |
   | `nombre`                       | Nombre del producto.                                                          |
   | `categoria`                    | Nombre de la categoría. Debe existir (el administrador principal sí las crea al importar). |
   | `descripcion`                  | Texto libre (opcional).                                                       |
   | `precio`                       | Precio normal, sin símbolo: `1250.00`                                         |
   | `precio_oferta`                | Opcional. Debe ser menor que el precio.                                       |
   | `oferta_inicio`, `oferta_fin`  | Opcionales. Formato `2026-01-15 08:00:00`.                                    |
   | `stock_almacen`                | Unidades en almacén.                                                          |
   | `destacado`, `nuevo`, `activo` | `1` (sí) o `0` (no).                                                          |

3. Pulsa **Importar**, elige el archivo y el formato `xlsx`. Quien administra varias tiendas elige
   también en cuál se importa; nunca se tocan productos de otra tienda.
4. Revisa la vista previa: muestra qué se crea, qué se actualiza y los errores por fila. Si hay
   errores no se importa nada.
5. Confirma la importación.

Las fotos y el stock reservado no se importan. **Exportar** descarga el catálogo con las mismas
columnas, así que sirve para editar precios o stock en bloque y volver a importar.

## Tests

```bash
python manage.py test
```

Son más de 200 pruebas. Cubren carrito, cupones, costo de envío, reserva/descuento/liberación de stock,
transiciones de estado, mensaje de WhatsApp, checkout, panel, el aislamiento entre tiendas (sitio y
panel) y la migración de una sola tienda a subtiendas. Usan una base temporal y no tocan `db.sqlite3`.

## Marca y colores

- Colores de la tienda: variables al inicio de `static/css/tienda.css` (`--mm-primario`, `--mm-acento`, ...).
  Hoy son el azul y el verde del logo.
- Colores del panel: variables al inicio de `static/css/panel.css`.
- Recursos de la marca en `static/img/`: `logo-simbolo.webp` (encabezado y portada), `favicon.png`,
  `apple-touch-icon.png` y `compartir.jpg` (la imagen que aparece al compartir un enlace de la tienda).
- Si en Configuración general se sube un logo, ese reemplaza al símbolo con el nombre en el encabezado del
  sitio.
- La portada del sitio es clara y sin banner: título, buscador y las tarjetas de las tiendas. Cada tarjeta
  muestra la imagen del banner de la tienda arriba y su logo en un círculo (o su inicial si no tiene).
- Cada tienda muestra su propio logo (o su nombre) y su banner; sobre su encabezado hay una franja para
  volver a "Todas las tiendas".
- En el inicio de una tienda, la categoría que no tiene imagen muestra la foto de uno de sus productos.

## Estructura

```
config/       settings, urls, wsgi, middleware de registro de errores
tiendas/      tiendas (subtiendas), vendedores y aislamiento del panel; portada y buscador del sitio
core/         configuración general, cuentas bancarias, panel, utilidades, cargar_demo
catalogo/     categorías, productos, fotos; inicio, catálogo y detalle de cada tienda
promociones/  cupones
carrito/      carrito en la sesión, uno por tienda
pedidos/      zonas, pedidos, clientes, checkout, confirmación, mensaje de WhatsApp
templates/    plantillas de la tienda y del panel
static/       CSS y JavaScript
docs/         DESPLIEGUE.md y esquema.sql (referencia)
```

La lógica de negocio está en `services.py` de cada app.

## Publicar la tienda

- **VPS con Ubuntu** (PostgreSQL, Gunicorn, Nginx y SSL): guía paso a paso en
  [docs/DESPLIEGUE.md](docs/DESPLIEGUE.md).
- **Render u otra plataforma administrada:** define `SECRET_KEY`, `DEBUG=False`, `DATABASE_URL` y
  `ADMIN_URL`; instala `requirements-prod.txt`; ejecuta `migrate` y `collectstatic --noinput`; arranca
  con `gunicorn config.wsgi:application`. Dos cosas a tener en cuenta:
  - Las fotos subidas (`media/`) solo se sirven con `DEBUG=True` o desde Nginx. En una plataforma sin
    disco persistente se pierden en cada despliegue y nadie las entrega: hace falta un disco montado
    y algo que sirva `/media/`, o un almacenamiento externo.
  - El límite de pedidos por IP lee la cabecera `X-Real-IP`. Si el proxy de la plataforma no la envía,
    todos los visitantes cuentan como una misma IP y el límite (5 pedidos por hora) se alcanza pronto.
