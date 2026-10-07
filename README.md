# Multimix RD

Tienda en línea hecha con Django 5.2. Vende productos de varias categorías con precios en pesos
dominicanos (RD$). El cliente arma su carrito, confirma el pedido y lo envía por WhatsApp; el pago
(transferencia o efectivo) se confirma desde el panel de administración.

- **Tienda:** inicio con ofertas, destacados, nuevos y más vendidos; catálogo con búsqueda y filtros;
  carrito; checkout con totales calculados en el servidor; confirmación con botón de WhatsApp.
- **Panel:** resumen de ventas y stock, productos (con importación desde Excel), pedidos, cupones,
  zonas de envío, cuentas bancarias y configuración de la tienda.
- **Stack:** Python 3.13 (o 3.12), Django 5.2, Bootstrap 5 por CDN, JavaScript sin frameworks.
  SQLite en desarrollo; PostgreSQL (o MySQL 8) en producción.

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
pip install -r requirements.txt

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
pip install -r requirements.txt

cp .env.example .env
# Genera una clave y pégala en SECRET_KEY dentro de .env:
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"

python manage.py migrate
python manage.py createsuperuser
python manage.py cargar_demo
python manage.py runserver
```

Luego abre:

- Tienda: <http://127.0.0.1:8000/>
- Panel: <http://127.0.0.1:8000/panel/> (la ruta sale de `ADMIN_URL` en `.env`)

`cargar_demo` crea 6 categorías, 20 productos con imágenes, el cupón `BIENVENIDO10` (10 % en compras
desde RD$ 1,000.00), zonas de envío, una cuenta bancaria, la configuración de la tienda y 4 pedidos de
ejemplo. Se puede ejecutar varias veces sin duplicar nada y no pisa los datos que ya hayas cambiado.

## Configuración (.env)

| Variable | Para qué sirve |
| --- | --- |
| `SECRET_KEY` | Clave secreta de Django. Obligatoria y distinta en cada instalación. |
| `DEBUG` | `True` en desarrollo, `False` en producción. |
| `ALLOWED_HOSTS` | Dominios permitidos, separados por coma. |
| `CSRF_TRUSTED_ORIGINS` | Orígenes con esquema, separados por coma (`https://tudominio.com`). |
| `ADMIN_URL` | Ruta del panel, sin barras (`panel`). Cámbiala en producción. |
| `DB_ENGINE` | `sqlite`, `postgresql` o `mysql`. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Datos de conexión. Con SQLite solo se usa `DB_NAME` (nombre del archivo). |

Con `DEBUG=False` se activan solas las cookies seguras, HSTS, la redirección a HTTPS y
`SECURE_PROXY_SSL_HEADER`.

### Cambiar de base de datos

No hay que tocar código: solo `.env` y el driver.

**PostgreSQL** (recomendado en producción):

```bash
pip install -r requirements-prod.txt
```

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

Entra a `/panel/` con el usuario creado con `createsuperuser`.

**Portada.** Ventas del día y del mes (pedidos cobrados), pedidos pendientes, productos con stock bajo
o agotados, últimos pedidos y los 5 más vendidos.

**Configuración de la tienda.** Nombre, logo, contacto, número de WhatsApp (solo dígitos con código de
país, por ejemplo `18095551234`), dirección para recoger, banner, días en que un producto cuenta como
nuevo, umbral de stock bajo, horas para vencer pedidos pendientes, si se muestra la cantidad exacta y
si se permite pagar contra entrega. Solo existe una configuración: no se puede crear otra ni borrarla.
Los cambios pueden tardar hasta un minuto en verse en la tienda.

**Productos.**
- La lista muestra foto, precio, oferta, almacén, reservado y disponible con color (verde: normal,
  naranja: stock bajo, rojo: agotado). Destacado, nuevo y activo se editan desde la misma lista.
- *Stock reservado* lo maneja el sistema: sube cuando entra un pedido y baja cuando se entrega o se
  cancela. El almacén no puede quedar por debajo de lo reservado.
- Las fotos se suben en JPG, PNG o WebP (hasta 5 MB); se ajustan a 1200 px y se guardan en WebP.
- **Fotos por SKU** (botón de la lista): sube muchas fotos a la vez. El nombre de cada archivo es el SKU
  del producto (`123785.jpg`) y la foto queda como principal; al terminar lista las que no encontraron
  producto. Se puede elegir reemplazar las fotos que ya tenía cada producto.
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

**Cupones, zonas de envío, categorías y cuentas bancarias** se administran desde sus secciones. Los
cupones muestran sus usos (`usados / máximo`).

### Pedidos vencidos

```bash
python manage.py cancelar_pedidos_vencidos
```

Cancela los pedidos pendientes más viejos que las horas configuradas y libera su stock. En producción
se programa con cron (ver `docs/DESPLIEGUE.md`).

## Importar productos desde Excel

1. En **Productos**, pulsa **Plantilla de Excel** para descargar `plantilla_productos.xlsx`.
2. Llena una fila por producto:

   | Columna | Contenido |
   | --- | --- |
   | `sku` | Código único. Si ya existe, el producto se **actualiza**; si no, se **crea**. |
   | `nombre` | Nombre del producto. |
   | `categoria` | Nombre de la categoría. Si no existe, se crea. |
   | `descripcion` | Texto libre (opcional). |
   | `precio` | Precio normal, sin símbolo: `1250.00` |
   | `precio_oferta` | Opcional. Debe ser menor que el precio. |
   | `oferta_inicio`, `oferta_fin` | Opcionales. Formato `2026-01-15 08:00:00`. |
   | `stock_almacen` | Unidades en almacén. |
   | `destacado`, `nuevo`, `activo` | `1` (sí) o `0` (no). |

3. Pulsa **Importar**, elige el archivo y el formato `xlsx`.
4. Revisa la vista previa: muestra qué se crea, qué se actualiza y los errores por fila. Si hay
   errores no se importa nada.
5. Confirma la importación.

Las fotos y el stock reservado no se importan. **Exportar** descarga el catálogo con las mismas
columnas, así que sirve para editar precios o stock en bloque y volver a importar.

## Tests

```bash
python manage.py test
```

Cubren carrito, cupones, costo de envío, reserva/descuento/liberación de stock, transiciones de
estado, mensaje de WhatsApp, checkout y panel.

## Personalizar los colores

- Tienda: variables al inicio de `static/css/tienda.css` (`--mm-primario`, `--mm-acento`, ...).
- Panel: variables al inicio de `static/css/panel.css`.

## Estructura

```
config/       settings, urls, wsgi
core/         configuración de la tienda, cuentas bancarias, panel, utilidades, cargar_demo
catalogo/     categorías, productos, fotos; inicio, catálogo y detalle
promociones/  cupones
carrito/      carrito en la sesión
pedidos/      zonas, pedidos, checkout, confirmación, mensaje de WhatsApp
templates/    plantillas de la tienda y del panel
static/       CSS y JavaScript
docs/         DESPLIEGUE.md y esquema.sql (referencia)
```

La lógica de negocio está en `services.py` de cada app. Publicación en un servidor:
[docs/DESPLIEGUE.md](docs/DESPLIEGUE.md).
