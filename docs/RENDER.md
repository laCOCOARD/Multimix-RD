# Multimix RD en Render

Cómo está desplegado el sitio hoy y cómo mantenerlo. Para un servidor propio (VPS) ver `DESPLIEGUE.md`.

## Servicios

| Qué             | Dónde                                                                          |
| --------------- | ------------------------------------------------------------------------------ |
| Sitio web       | Render, servicio web `Multimix-RD-web` (plan gratis), rama `main` de GitHub     |
| Base de datos   | PostgreSQL de Render `Multimix-RD` (plan gratis: **se borra a los 30 días**)    |
| Fotos           | Supabase Storage, bucket público `multimix-media`                               |
| Correos         | Brevo, por su API                                                               |

- **Build:** `pip install -r requirements-prod.txt && python manage.py collectstatic --noinput`
- **Start:** `python manage.py migrate`, crea o actualiza el superusuario con `DJANGO_SUPERUSER_*` y arranca
  Gunicorn. Las migraciones corren solas en cada despliegue.
- **Despliegue:** manual. Tras subir a GitHub: *Manual Deploy → Deploy latest commit*.
- **Health Check Path** (Settings): `/salud/`. Responde `ok` si el sitio y la base funcionan.

## Variables de entorno

| Variable                                                | Para qué                                                              |
| ------------------------------------------------------- | --------------------------------------------------------------------- |
| `SECRET_KEY`                                            | Clave de Django. Larga, única y secreta.                              |
| `DEBUG`                                                 | `False`.                                                              |
| `DATABASE_URL`                                          | Conexión a PostgreSQL (la *Internal Database URL* de Render).          |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`                 | Solo si se usa un dominio propio; el de Render se agrega solo.        |
| `ADMIN_URL`                                             | Ruta del panel (por defecto `panel`). Conviene cambiarla.             |
| `DJANGO_SUPERUSER_USERNAME`, `_EMAIL`, `_PASSWORD`      | Administrador principal. Su contraseña se repone en cada arranque.    |
| `MEDIA_STORAGE=supabase` y las seis `SUPABASE_*`        | Fotos y comprobantes en Supabase.                                     |
| `BREVO_API_KEY`                                         | Clave **API** de Brevo (no la SMTP). Sin ella no sale ningún correo.  |
| `DEFAULT_FROM_EMAIL`                                    | Remitente verificado en Brevo: `Multimix RD <correo@dominio>`.        |
| `SITIO_URL`                                             | Solo con dominio propio, para los enlaces de los correos.             |
| `PAGOS_PROVEEDOR_TARJETA`                               | Vacía hasta tener la pasarela (ver `PAGOS.md`).                       |

El plan gratis de Render bloquea SMTP: por eso el correo va por la API de Brevo. Se prueba en
**Panel → Configuración general → Enviar correo de prueba**.

## Lo que el plan gratis no tiene

- **Tareas programadas.** El sitio las reemplaza: como mucho una vez por hora, una visita cualquiera cancela
  los pedidos pendientes vencidos y limpia sesiones caducadas (`core/tareas.py`).
- **Disco permanente.** Nada se guarda en el servidor: las fotos van a Supabase y los registros a la consola
  de Render.
- **Siempre encendido.** El servicio se duerme sin visitas; la primera carga tarda. Al dormirse se reinician
  los contadores del límite de intentos de inicio de sesión.
- **Respaldos de la base.** No hay ninguno automático.

## Respaldar la base y pasarla a otra

La base gratis **se borra 30 días después de crearla**. Antes de esa fecha hay que copiar los datos a una base
nueva. Se hace desde la PC, con el proyecto y su entorno virtual. Este procedimiento se ensayó completo sobre
SQLite; conviene repetirlo con calma la primera vez sobre PostgreSQL.

1. **Copia de seguridad.** En Render, abre la base y copia la *External Database URL*. En PowerShell, dentro
   del proyecto:

   ```powershell
   $env:DATABASE_URL = "<External Database URL de la base actual>"
   $env:MEDIA_STORAGE = "local"; $env:PYTHONUTF8 = "1"
   .venv\Scripts\python manage.py dumpdata --natural-foreign --natural-primary `
       --exclude contenttypes --exclude auth.permission --exclude sessions --exclude admin.logentry `
       -o respaldo.json
   ```

   Guarda `respaldo.json` fuera del repositorio: contiene datos de clientes.

2. **Base nueva.** Crea otra base PostgreSQL en Render y copia su *External Database URL*.

3. **Cargar los datos** en la base nueva:

   ```powershell
   $env:DATABASE_URL = "<External Database URL de la base NUEVA>"
   .venv\Scripts\python manage.py migrate
   .venv\Scripts\python manage.py loaddata respaldo.json
   ```

4. **Cambiar el sitio de base.** En el servicio web, pon en `DATABASE_URL` la *Internal Database URL* de la
   base nueva y despliega. Comprueba el catálogo, un pedido y el panel antes de borrar la base anterior.

5. Cierra la terminal o limpia las variables: `Remove-Item Env:DATABASE_URL`.

Las fotos no se mueven: siguen en Supabase y la base solo guarda sus rutas.

## Pendiente antes de vender en serio

- Pasar la base a un plan de pago (o repetir el traslado cada mes) y tener respaldos periódicos.
- Dominio propio: mejora la confianza y que los correos no caigan en spam.
- Escribir y publicar las páginas de políticas (Panel → Páginas informativas).
- Bucket privado para los comprobantes de pago (hoy comparten el bucket público de las fotos).
- Afiliación con AZUL o CardNET para aceptar tarjetas (`PAGOS.md`).
