#!/bin/sh
# Entrypoint de la imagen: migra la base (si AUTO_MIGRATE no es "false") y
# luego ejecuta el comando del servicio (gunicorn por defecto).
# El sync-worker pone AUTO_MIGRATE=false: solo `app` migra.
set -e

if [ "${AUTO_MIGRATE:-true}" != "false" ]; then
    FLASK_APP=run.py python migrar_al_arrancar.py
fi

exec "$@"
