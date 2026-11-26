# folios-gestion

Sistema de seguimiento de folios de certificados para una Dirección Provincial
de Salud: recepción de rangos, entrega/devolución a centros de salud, escaneos
y reportes. Interfaz en español, Flask + MariaDB.

> **Desde 1.10.0 la imagen se publica aquí (`m809/folios-gestion`).** Hasta
> 1.9.0 estaba en `soportedpss1/folios-gestion`, que ya no recibe versiones.
> Para actualizar un servidor existente vea *Actualizar desde 1.9.x* abajo.

- **App:** Flask 3 + SQLAlchemy + Flask-Login + Flask-WTF + Flask-Limiter
- **UI:** Jinja2 + Bootstrap 5 + jQuery + SweetAlert2 (mensajes como toasts
  flotantes, confirmaciones con tema de la app, responsive)
- **Servidor:** Gunicorn (4 workers) en el puerto `8089`
- **Extras:** Redis (rate limits compartidos), MariaDB 11.4, worker de
  sincronización con Google Sheets (APScheduler)
- **Exports:** PDF (WeasyPrint) y Excel (openpyxl) — las librerías de
  pango/cairo ya vienen en la imagen

## Quickstart

```bash
mkdir -p /opt/folios && cd /opt/folios
#   docker-compose.deploy.yml   compose que usa esta imagen (no compila)
#   .env.example                plantilla de variables
#   docs/despliegue.md          guía completa
# Código y docs: https://github.com/minguinrd/folios-gestion
curl -fsSLO https://raw.githubusercontent.com/minguinrd/folios-gestion/main/docker-compose.deploy.yml
curl -fsSLO https://raw.githubusercontent.com/minguinrd/folios-gestion/main/.env.example
curl -fsSL -o despliegue.md https://raw.githubusercontent.com/minguinrd/folios-gestion/main/docs/despliegue.md

cp .env.example .env && chmod 600 .env
# editar .env: SECRET_KEY, DB_PASSWORD, DB_ROOT_PASSWORD
echo "SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')"

mkdir -p scans secrets && sudo chown -R 1000:1000 scans secrets

docker compose -f docker-compose.deploy.yml up -d

# Orden correcto: migraciones primero, init_db después
# (init_db hace create_all y dejaría el esquema fuera de alembic_version)
docker compose -f docker-compose.deploy.yml exec -e FLASK_APP=run.py app flask db upgrade
docker compose -f docker-compose.deploy.yml exec app python init_db.py

open http://localhost:8089
```

`init_db.py` crea el usuario **admin** con una contraseña aleatoria que se
imprime **una sola vez** en consola.

El compose de despliegue usa la imagen publicada:

```yaml
services:
  app:
    image: m809/folios-gestion:1.11.0
    ports:
      - "8089:8089"
    env_file: .env
    # ... db (mariadb:11.4) + redis, healthchecks y volúmenes
```

## Configuración (`.env`)

| Variable | Requerida | Notas |
|----------|-----------|-------|
| `SECRET_KEY` | sí | sin ella (o con valor de ejemplo) la app no arranca |
| `DB_HOST` | sí | `db` (nombre del servicio MariaDB en compose) |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | sí | usuario de app con privilegios solo sobre `DB_NAME` |
| `DB_ROOT_PASSWORD` | sí | solo se usa en el primer arranque del volumen |
| `SESSION_COOKIE_SECURE` / `TRUST_PROXY` | no | `true` solo detrás de reverse proxy con TLS |
| `TZ` | no | default `America/Santo_Domingo`; timestamps en UTC, UI en local |
| `RATELIMIT_DEFAULT` | no | default `300 per hour` (`/health` exento) |
| `GOOGLE_SHEET_ID` / `GOOGLE_SERVICE_ACCOUNT_JSON` | no | sincronización con Google Sheets |
| `REPORTE_PDF_MAX_FILAS` | no | default `5000`; tope de filas del PDF de Reportes (el Excel no tiene tope) |
| `SUGERIDO_VENTANA_MESES` / `SUGERIDO_MESES_COBERTURA` | no | default `6` / `3`; cálculo de la cantidad sugerida por centro |

## Notas de operación

- **Puerto:** `8089` (HTTP). Detrás de proxy TLS activar
  `SESSION_COOKIE_SECURE=true` + `TRUST_PROXY=true`.
- **Carpeta `scans/`:** debe pertenecer a UID `1000` (`chown 1000:1000 scans`)
  — el contenedor corre como `appuser`; si Docker la crea como root, las
  subidas de escaneos fallan. Estructura: `scans/<año>/<id del tipo>/<número>.jpg`.
- **Healthchecks:** `app` responde `GET /health`; `sync-worker` se marca
  unhealthy si su scheduler deja de latir (>10 min).
- **Permisos:** roles `admin` / `operador` / `lectura` más permisos
  granulares por usuario (Usuarios → Permisos). Recepción y escaneos son de
  admin por defecto; un admin puede concederlos.
- **Copias:** respaldo JSON desde la UI (Copias) o dump SQL desde el
  contenedor `db` con `mariadb-dump` (ver `docs/despliegue.md`).
- **Migraciones:** `FLASK_APP=run.py flask db upgrade` dentro del contenedor
  `app`; bases creadas con `init_db.py` (sin `alembic_version`) requieren
  `flask db stamp <revisión>` una vez — ver README → "Síntoma Table '…'
  already exists".
- **Rotar credenciales MariaDB:** cambiar `.env` no cambia la contraseña ya
  inicializada en el volumen — ver README (Rotar credenciales de MariaDB).

## Actualizar desde 1.10.x

```bash
cd /opt/folios
# respaldo, compose nuevo (tag 1.11.0) y migración 0011
docker compose -f docker-compose.deploy.yml exec db sh -c \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mariadb-dump -uroot "$MYSQL_DATABASE"' > respaldo_pre_1.11.sql
curl -fsSLO https://raw.githubusercontent.com/minguinrd/folios-gestion/main/docker-compose.deploy.yml
docker compose -f docker-compose.deploy.yml pull && docker compose -f docker-compose.deploy.yml up -d
docker compose -f docker-compose.deploy.yml exec -e FLASK_APP=run.py app flask db upgrade
```

Novedades de 1.11.0:

- **Corrige los diálogos de confirmación** (SweetAlert2): en 1.10.0 y
  anteriores el navegador podía bloquear el script por un cambio en el CDN.
- **Sin dependencia de internet:** Bootstrap, íconos, calendarios, tablas,
  gráficos y fuentes se sirven desde la propia imagen.
- **Content-Security-Policy** con nonce por petición. Si alguna página
  fallara por la política, `CSP_REPORT_ONLY=true` en `.env` la deja solo
  informando, sin redesplegar.
- Institución y departamento configurables en **Marca** (barra superior,
  acceso y PDF).
- Interfaz: menú lateral por secciones, migas de pan, conteo de resultados y
  "Limpiar" en los listados, selección de folios por rango y "Usar
  sugerido" al entregar, menú "Validar" en Folios, colores de estado
  coherentes (Entregado azul, Nulo rojo).

## Actualizar desde 1.9.x

Pasar primero por los pasos de 1.10 (abajo) y luego los de 1.11 (arriba).

```bash
cd /opt/folios
docker compose -f docker-compose.deploy.yml exec db sh -c \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mariadb-dump -uroot "$MYSQL_DATABASE"' > respaldo_pre_1.10.sql
# compose nuevo (apunta a m809/folios-gestion) y revisar FOLIOS_IMAGE en .env
curl -fsSLO https://raw.githubusercontent.com/minguinrd/folios-gestion/main/docker-compose.deploy.yml
docker compose -f docker-compose.deploy.yml pull && docker compose -f docker-compose.deploy.yml up -d
docker compose -f docker-compose.deploy.yml exec -e FLASK_APP=run.py app flask db upgrade
# escaneos al formato por tipo: primero simula, luego mueve
docker compose -f docker-compose.deploy.yml exec app python migrar_escaneos.py
docker compose -f docker-compose.deploy.yml exec app python migrar_escaneos.py --aplicar
```

Novedades de 1.10.0: cantidad sugerida de certificados por tipo en cada
centro (y como ayuda al entregar), escaneos separados por tipo de
certificado, importación de digitado/nulos con columnas `anio`/`tipo` (las
filas ambiguas ya no marcan todos los años y tipos) y export Excel completo
en reportes grandes. Detalle en `docs/despliegue.md` §9.

## Tags

- `m809/folios-gestion:1.11.0` — versión fija, recomendada en
  producción
- `m809/folios-gestion:latest` — última build, para pruebas

Para probar otra versión sin editar el compose: `FOLIOS_IMAGE=...:tag` en el
`.env`.

## Documentación

La guía completa de despliegue (`.env` anotado, reverse proxy TLS, copias y
restauración, actualización y troubleshooting) vive en `docs/despliegue.md`
del proyecto, junto a `docker-compose.deploy.yml` y `.env.example`.
