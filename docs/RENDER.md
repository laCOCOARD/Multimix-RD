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
- **Panel:** la ruta sale de `ADMIN_URL` y no es `/panel/`. Nada del sitio la enlaza ni la menciona (tampoco
  `robots.txt`): guárdala en tus favoritos.
- **Google:** en `*.onrender.com` el `robots.txt` lo responde Render con `Disallow: /` (la petición no llega a
  Django), así que el sitio no se indexa. Con un dominio propio se sirve el nuestro, que sí deja ver el catálogo.

## Variables de entorno

| Variable                                                | Para qué                                                              |
| ------------------------------------------------------- | --------------------------------------------------------------------- |
| `SECRET_KEY`                                            | Clave de Django. Larga, única y secreta.                              |
| `DEBUG`                                                 | `False`.                                                              |
| `DATABASE_URL`                                          | Conexión a PostgreSQL (la *Internal Database URL* de Render).          |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`                 | Solo si se usa un dominio propio; el de Render se agrega solo.        |
| `ADMIN_URL`                                             | Ruta del panel (por defecto `panel`). Conviene cambiarla.             |
| `DJANGO_SUPERUSER_USERNAME`, `_EMAIL`, `_PASSWORD`      | Administrador principal. Su contraseña se repone en cada arranque.    |
| `MEDIA_STORAGE=supabase` y las seis `SUPABASE_*`        | Fotos en Supabase.                                                    |
| `SUPABASE_S3_BUCKET_PRIVADO`                            | Bucket **privado** para los comprobantes de pago (ver abajo).         |
| `SUPABASE_S3_BUCKET_VIDEOS`                             | Bucket **público** para los videos de las tiendas (ver abajo).        |
| `CABECERA_IP`                                           | Solo si cambia el proxy. Por defecto `CF-Connecting-IP` en Render.    |
| `VERIFICAR_CORREO`                                      | `0` para no pedir que se confirme el correo antes de comprar.         |
| `BREVO_API_KEY`                                         | Clave **API** de Brevo (no la SMTP). Sin ella no sale ningún correo.  |
| `DEFAULT_FROM_EMAIL`                                    | Remitente verificado en Brevo: `Multimix RD <correo@dominio>`.        |
| `SITIO_URL`                                             | Solo con dominio propio, para los enlaces de los correos.             |
| `PAGOS_PROVEEDOR_TARJETA`                               | Vacía hasta tener la pasarela (ver `PAGOS.md`).                       |
| `WHATSAPP_TOKEN`, `WHATSAPP_NUMERO_ID`                  | Opcionales: avisos automáticos por WhatsApp (ver `WHATSAPP.md`).      |

El plan gratis de Render bloquea SMTP: por eso el correo va por la API de Brevo. Se prueba en
**Panel → Configuración general → Enviar correo de prueba**.

### Comprobantes en un bucket privado

Los comprobantes de transferencia llevan datos bancarios: no deben estar en el bucket público de las fotos.

1. En Supabase → Storage → *New bucket*: nombre `multimix-privado`, **sin** marcar *Public bucket*. (Ya está
   creado desde el 2026-10-19; con las claves S3 también se crea con `create_bucket` y nace privado.)
2. En Render, la variable `SUPABASE_S3_BUCKET_PRIVADO=multimix-privado` (usa las mismas claves S3).
3. Despliega. Los comprobantes nuevos van al privado y los de antes se pasan solos, de cinco en cinco, con
   las tareas periódicas. En el panel se ven igual (Pagos → el pago → Comprobante), a través del sitio.

Mientras falte la variable, siguen en el bucket público y el detalle del pago lo avisa.

### Videos de las tiendas en su propio bucket

El bucket de las fotos (`multimix-media`) solo acepta imágenes, así que los videos (plan Premium) van a otro.

1. En Supabase → Storage → *New bucket*: nombre `multimix-videos`, **con** *Public bucket* marcado. En sus
   ajustes, *Allowed MIME types* `video/mp4` (o vacío) y un límite de archivo de 50 MB o más.
2. En Render, la variable `SUPABASE_S3_BUCKET_VIDEOS=multimix-videos` (usa las mismas claves S3).
3. Despliega. Desde ahí las tiendas con un plan que incluya videos pueden subirlos en Panel → Videos de las tiendas.

Mientras falte la variable, el panel no deja subir videos y se lo explica al administrador.

### IP del visitante

Los límites por IP (pedidos, cuentas nuevas, intentos de entrar) leen `CF-Connecting-IP`, que pone Cloudflare
delante de Render en cada visita. `X-Forwarded-For` no sirve: Render deja la primera IP tal como la manda el
visitante. Si los registros de Render muestran *La visita no trae la IP en HTTP_CF_CONNECTING_IP*, esa cabecera
no está llegando: los límites por cuenta y por correo siguen funcionando, pero hay que elegir otra con
`CABECERA_IP`. Para comprobarlo, la IP queda guardada en cada pedido (Panel → Pedidos → el pedido).

## Lo que el plan gratis no tiene

- **Tareas programadas.** El sitio las reemplaza: como mucho una vez por hora, una visita cualquiera cancela
  los pedidos pendientes vencidos y limpia sesiones caducadas (`core/tareas.py`).
- **Disco permanente.** Nada se guarda en el servidor: las fotos van a Supabase y los registros a la consola
  de Render.
- **Siempre encendido.** El servicio se duerme sin visitas; la primera carga tarda. Los límites de intentos
  se cuentan en la base (`core.Intento`), así que no se reinician al dormirse.
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

## Publicar un cambio sin riesgo

El repositorio de GitHub tiene otra historia que la copia local (ver `CLAUDE.md`): los cambios se llevan con
`git cherry-pick` en la carpeta `multimix_rd_github` (rama `github-main`). El auto-deploy de Render está apagado.

1. **Antes:** `.venv\Scripts\python manage.py check`, `makemigrations --check` y `test` en la PC; todo debe pasar.
   Si la base está por caducar, haz primero la copia de seguridad (sección anterior).
2. **Llevar los commits:** en `C:\Users\elies\multimix_rd_github`, comprueba que `git diff --stat main github-main`
   esté vacío salvo lo nuevo, luego `git cherry-pick <commits>` en orden y `git push origin github-main:main`.
3. **Desplegar:** en Render, *Manual Deploy → Deploy latest commit*. El arranque corre `migrate` solo.
4. **Comprobar:** `/salud/` responde "ok", el log de Render no tiene errores, la portada, una ficha, el carrito
   y el panel abren. Si algo falla, *Rollback* en Render vuelve al despliegue anterior: las migraciones de estas
   fases solo agregan tablas o columnas, así que el código anterior sigue funcionando con ellas.

### Rediseño (fases 1 a 4, 2026-10-27) y videos de las tiendas

| Commit | Qué trae | Migraciones |
|---|---|---|
| Videos de las tiendas | Videos del plan Premium | `core/0021`, `planes/0003`, `planes/0004` (Premium con 1 video) |
| Fase 1 | Portada, paleta carbón y ámbar, corazón en las tarjetas | — |
| Fase 2 | `/vender/` y solicitudes de tiendas | `tiendas/0017` (tabla nueva) |
| Fase 3 | Buscador con tiendas y filtros, ficha con "Vendido por" | — |
| Fase 4 | Miniaturas de las fotos, medición del negocio, topes de versiones | `catalogo/0017` (columna nueva), `core/0022` (tabla nueva) |

- Ninguna migración borra ni cambia datos, salvo `planes/0004`, que pone 1 video al plan Premium si tenía 0.
- **Variables:** ninguna obligatoria. `SUPABASE_S3_BUCKET_VIDEOS` solo para habilitar los videos (sección del
  bucket de videos); sin ella el sitio funciona igual y no ofrece subirlos.
- **Miniaturas:** las fotos nuevas las traen. Las que ya están en Supabase se completan solas, de cinco en cinco,
  con las tareas periódicas (una vez por hora con visitas). Mientras tanto se usa la foto grande: nada se rompe.
  Para hacerlas todas de una vez desde la PC: `$env:DATABASE_URL="<External Database URL>"`, las variables
  `SUPABASE_*` del `.env` y `.venv\Scripts\python manage.py crear_miniaturas`.
- **Dependencias:** `requirements*.txt` tienen ahora tope en la siguiente versión mayor (Render instala lo más nuevo
  en cada despliegue). Para subir de versión mayor, cámbialo a propósito y prueba antes.

## Pendiente antes de vender en serio

- Pasar la base a un plan de pago (o repetir el traslado cada mes) y tener respaldos periódicos.
- Dominio propio: mejora la confianza y que los correos no caigan en spam.
- Revisar las páginas de políticas (Panel → Páginas informativas) y completar la razón social y el RNC.
- Afiliación con AZUL o CardNET para aceptar tarjetas (`PAGOS.md`).
