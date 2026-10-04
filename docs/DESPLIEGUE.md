# Despliegue en un VPS con Ubuntu

Guía para publicar Multimix RD en Ubuntu 24.04 con PostgreSQL, Gunicorn, Nginx y SSL de Let's Encrypt.
En los ejemplos el dominio es `multimixrd.com` y el proyecto vive en `/srv/multimix`. Cambia ambos por
los tuyos.

## 1. Registro A del dominio

En el panel de tu proveedor de dominio crea dos registros que apunten a la IP pública del VPS:

| Tipo | Nombre | Valor |
| --- | --- | --- |
| A | `@` | IP del VPS |
| A | `www` | IP del VPS |

Comprueba que ya propagó antes de pedir el certificado: `dig +short multimixrd.com`.

## 2. Paquetes del sistema

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-dev build-essential git \
    postgresql postgresql-contrib nginx certbot python3-certbot-nginx
python3 --version   # debe ser 3.12 o 3.13
```

Crea un usuario sin privilegios para la aplicación:

```bash
sudo adduser --system --group --home /srv/multimix multimix
```

## 3. PostgreSQL: base y usuario

```bash
sudo -u postgres psql
```

```sql
CREATE USER multimix WITH PASSWORD 'una-clave-larga-y-unica';
CREATE DATABASE multimix OWNER multimix ENCODING 'UTF8';
ALTER ROLE multimix SET client_encoding TO 'utf8';
ALTER ROLE multimix SET timezone TO 'America/Santo_Domingo';
\q
```

## 4. Código y entorno virtual

```bash
sudo -u multimix -H bash
cd /srv/multimix
git clone <url-del-repositorio> app
cd app
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements-prod.txt
```

## 5. `.env` de producción

```bash
cp .env.example .env
.venv/bin/python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
nano .env
chmod 600 .env
```

```ini
SECRET_KEY='pega-aqui-la-clave-generada'
DEBUG=False
ALLOWED_HOSTS=multimixrd.com,www.multimixrd.com
CSRF_TRUSTED_ORIGINS=https://multimixrd.com,https://www.multimixrd.com
ADMIN_URL=gestion-mmx

DB_ENGINE=postgresql
DB_NAME=multimix
DB_USER=multimix
DB_PASSWORD=una-clave-larga-y-unica
DB_HOST=localhost
DB_PORT=5432
```

Usa una `ADMIN_URL` que no sea obvia. Con `DEBUG=False` la aplicación exige HTTPS, marca las cookies
como seguras y envía HSTS.

## 6. Migraciones, estáticos y administrador

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py check --deploy
mkdir -p media
exit   # vuelve a tu usuario con sudo
```

Las tablas las crea `migrate`; `docs/esquema.sql` es solo de referencia. No ejecutes `cargar_demo` en
producción salvo que quieras los productos de ejemplo.

## 7. Gunicorn con systemd

`/etc/systemd/system/multimix.socket`:

```ini
[Unit]
Description=Socket de Gunicorn para Multimix RD

[Socket]
ListenStream=/run/multimix.sock
SocketUser=www-data

[Install]
WantedBy=sockets.target
```

`/etc/systemd/system/multimix.service`:

```ini
[Unit]
Description=Gunicorn de Multimix RD
Requires=multimix.socket
After=network.target postgresql.service

[Service]
User=multimix
Group=multimix
WorkingDirectory=/srv/multimix/app
ExecStart=/srv/multimix/app/.venv/bin/gunicorn config.wsgi:application \
    --workers 3 --timeout 60 --bind unix:/run/multimix.sock \
    --access-logfile - --error-logfile -
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now multimix.socket multimix.service
sudo systemctl status multimix.service
```

Los registros se leen con `journalctl -u multimix -f`; los de la aplicación quedan además en
`/srv/multimix/app/logs/multimix.log`.

## 8. Nginx (static y media)

`/etc/nginx/sites-available/multimix`:

```nginx
server {
    listen 80;
    server_name multimixrd.com www.multimixrd.com;

    client_max_body_size 12M;

    location /static/ {
        alias /srv/multimix/app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public";
    }

    location /media/ {
        alias /srv/multimix/app/media/;
        expires 30d;
        add_header Cache-Control "public";
        add_header X-Content-Type-Options nosniff;
    }

    location / {
        proxy_pass http://unix:/run/multimix.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

`X-Forwarded-Proto` le dice a Django que la visita llegó por HTTPS y `X-Real-IP` es la IP que usa el
límite de pedidos por conexión. Nginx los sobrescribe siempre, así que un visitante no puede falsearlos.

Nginx debe poder leer los archivos:

```bash
sudo chmod 755 /srv/multimix /srv/multimix/app
sudo ln -s /etc/nginx/sites-available/multimix /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

## 9. SSL con Certbot

```bash
sudo certbot --nginx -d multimixrd.com -d www.multimixrd.com --redirect
sudo certbot renew --dry-run
```

Certbot modifica el sitio de Nginx para servir HTTPS y redirigir HTTP, y deja la renovación programada.

Cortafuegos:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

## 10. Respaldo diario y pedidos vencidos (cron)

Guarda la clave de la base para que `pg_dump` no la pida:

```bash
sudo -u multimix -H bash -c 'echo "localhost:5432:multimix:multimix:una-clave-larga-y-unica" > ~/.pgpass && chmod 600 ~/.pgpass'
sudo -u multimix mkdir -p /srv/multimix/respaldos
```

`/srv/multimix/respaldar.sh`:

```bash
#!/bin/bash
set -euo pipefail
DESTINO=/srv/multimix/respaldos
FECHA=$(date +%F)
pg_dump -h localhost -U multimix -Fc multimix > "$DESTINO/multimix_$FECHA.dump"
tar -czf "$DESTINO/media_$FECHA.tar.gz" -C /srv/multimix/app media
# Conserva los últimos 14 días.
find "$DESTINO" -type f -mtime +14 -delete
```

```bash
sudo chown multimix:multimix /srv/multimix/respaldar.sh
sudo chmod 750 /srv/multimix/respaldar.sh
sudo crontab -u multimix -e
```

```cron
# Respaldo diario a las 2:30 a.m.
30 2 * * * /srv/multimix/respaldar.sh >> /srv/multimix/respaldos/respaldo.log 2>&1
# Cada 30 minutos: cancela los pedidos pendientes vencidos y libera su stock.
*/30 * * * * cd /srv/multimix/app && .venv/bin/python manage.py cancelar_pedidos_vencidos >> logs/vencidos.log 2>&1
```

Copia los respaldos fuera del servidor cada cierto tiempo. Para restaurar:

```bash
pg_restore -h localhost -U multimix -d multimix --clean --if-exists multimix_2026-01-15.dump
```

## 11. Actualizar con git pull

```bash
sudo -u multimix -H bash
cd /srv/multimix/app
git pull
.venv/bin/pip install -r requirements-prod.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
exit
sudo systemctl restart multimix.service
```

Haz un respaldo (`/srv/multimix/respaldar.sh`) antes de una actualización que traiga migraciones.

## Lista de comprobación

- [ ] `https://multimixrd.com` abre con candado y `http://` redirige a `https://`.
- [ ] El panel abre en `https://multimixrd.com/<ADMIN_URL>/`.
- [ ] En Configuración están el número de WhatsApp, la dirección y el horario.
- [ ] Hay al menos una cuenta bancaria activa y las zonas de envío con sus tarifas.
- [ ] Un pedido de prueba llega hasta WhatsApp y aparece en el panel.
- [ ] `sudo crontab -u multimix -l` muestra el respaldo y `cancelar_pedidos_vencidos`.
