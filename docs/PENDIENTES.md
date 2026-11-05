# Pendientes (traspaso del 2026-11-03)

**Al dia el 2026-11-04:** los puntos 1 y 2 estan hechos. El sitio corre en `multimix-rd` (Virginia,
https://multimix-rd.onrender.com): la portada baja de 12-33 s a menos de 1 s. El servicio viejo `Multimix-RD-web` se
suspende (no borrar todavia). Ese dia tambien: videos de las tiendas dentro de la pagina y sin preguntas frecuentes.
Lo que sigue empieza en el punto 3.

**2026-11-05 (sin subir ni desplegar):** el anuncio de video lleva al lado el banner, el logo y 3 productos de la
tienda; escalera de premios de referidos (niveles 4 y 6). Migraciones nuevas: core/0027, referidos/0003,
tiendas/0025. El dueño ya tiene el correo `contacto.multimixrd@gmail.com`: falta Brevo (punto 3).

Notas para seguir el trabajo desde Claude Code en VS Code. Sin claves: las variables estan solo en Render.

## Lo que ya se hizo hoy

- **Commit `07edc73` en `main`** (subido a GitHub, todavia NO desplegado en Render):
  - Confirmacion del carrito global (`/carrito/confirmacion/<grupo>/`): cada tienda tiene su boton
    "Escribir a <tienda>" con su propio WhatsApp y el pedido escrito. Sin boton si la tienda no tiene numero.
  - Portada: fuera los cuadros "Entra y compra mas facil" y "Oferta destacada" (`tiendas.views._tarjetas_de_la_portada`).
  - Sin el boton flotante de volver arriba (`.mm-arriba` en `base.html`).
  - Menu "Ayuda": preguntas, WhatsApp y las dos primeras paginas de ayuda; lo demas sigue en el pie.
  - 701 pruebas pasan. Decision anotada en `docs/decisiones/sitio-y-diseno.md`.
- **Probado en local** con `cargar_demo`: carrito con dos tiendas, crear cuenta, pedido, WhatsApp de cada tienda
  (809-555-0123 y 829-555-0456) y limites anti-abuso de cuentas y pedidos por IP: todo funciona.

## Por que la tienda esta lenta (diagnostico)

- El 2026-11-02 la base paso a Supabase, Session pooler en **us-east-1 (Virginia)**.
- El servicio web de Render esta en **Oregon** (`Multimix-RD-web`, `srv-db1ent0u01pc73e41j10`, plan free).
- Cada consulta cruza el pais (~60-80 ms). La portada hace ~33 consultas: mas de 2 s solo esperando la base.
- Para confirmarlo, en el Shell de Render:
  `python manage.py shell -c "import time;from django.db import connection as c;k=c.cursor();t=time.time();[k.execute('SELECT 1') for _ in range(20)];print((time.time()-t)/20*1000,'ms')"`

## Pendiente, en este orden

1. **Desplegar `07edc73`** en `Multimix-RD-web`: Render -> Manual Deploy -> Deploy latest commit
   (el autodeploy esta apagado a proposito).
2. **Mudar el servicio a Virginia** (gratis por ahora; el dueño todavia no aprueba el plan Starter de $7):
   - Ya existe el servicio nuevo `multimix-rd` (`srv-dbkuijk9v7es73fdggqg`, region virginia, plan free,
     https://multimix-rd.onrender.com). Su primer deploy fallo porque no tiene variables.
   - Copiar TODAS las variables de entorno de `Multimix-RD-web` a `multimix-rd` (Render -> Environment).
   - Settings -> Health Check Path: `/salud/`.
   - Manual Deploy y revisar los logs.
   - Cuando funcione: suspender `Multimix-RD-web` (dos servicios free se pasan de las 750 h/mes) y actualizar
     `docs/RENDER.md` con el servicio y la URL nuevos.
   - Supabase no se toca: ya esta en us-east-1.
3. **Correo exclusivo del sitio**: el dueño lo crea (Gmail o Zoho con dominio propio) y se configura en
   Brevo/SMTP (`BREVO_API_KEY` o `EMAIL_HOST*`) y en `ConfiguracionTienda`. Probar "olvide mi contraseña".
4. **Antes de abrir al publico** (ver conversacion del 2026-11-03):
   - Respaldos: no hay ninguno automatico (`docs/RENDER.md`). Respaldo semanal o Supabase Pro.
   - Dominio propio (.com o .com.do) y agregarlo a `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS`. Ojo: HSTS con
     preload y subdominios esta activo.
   - Quitar datos de prueba (productos, tiendas, video "prueba", cuentas de prueba).
   - Compra de prueba real desde el celular de punta a punta.
   - Terminos, privacidad, devoluciones y envios con datos reales; que los revise un abogado.
   - UptimeRobot a `/salud/` y Google Search Console con `/sitemap.xml`.
   - Plan Starter ($7/mes) cuando el dueño lo apruebe: el plan free se duerme a los 15 min (30-50 s al despertar).
5. **Mejora de velocidad opcional**: cache de la portada (ya hay `LocMemCache`) y menos consultas con
   `select_related`/`prefetch_related`.
