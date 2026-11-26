"""Worker de sincronización automática a Google Sheets.

Corre como proceso aparte del servidor web (los 4 workers de gunicorn no tienen
timer propio). Lee la configuración (activo, frecuencia, retraso tras fallo)
desde la tabla sync_config en cada tick, así la UI puede cambiarla sin reiniciar.

Uso:  python run_worker.py     (en Docker: servicio sync-worker de compose)
"""
import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app import create_app
from app.config import DevelopmentConfig, ProductionConfig
from app.models.sync_config import debe_ejecutar, get_config, registrar_intento
from app.services.gsheets import ErrorSincronizacion, sincronizar
from app.utils import utcnow

CONFIGS = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
}

TICK_MINUTOS = 1
logger = logging.getLogger('sync_worker')

# Latido para el healthcheck de compose: cada tick toca este archivo; si el
# scheduler muere o se cuelga, su mtime envejece y el contenedor queda
# "unhealthy" (ver healthcheck.py / docker-compose.yml).
HEARTBEAT = os.environ.get('WORKER_HEARTBEAT', '/tmp/sync_worker_heartbeat')


def latido(ruta=None):
    """Actualiza el mtime del archivo de latido (nunca rompe el tick)."""
    ruta = ruta or HEARTBEAT
    try:
        with open(ruta, 'a'):
            pass
        os.utime(ruta, None)
    except OSError:
        logger.warning('No se pudo escribir el latido en %s', ruta)


def tick(app):
    """Un paso del worker: si la config lo dice, sincroniza y persiste estado."""
    latido()
    with app.app_context():
        try:
            cfg = get_config()
            if not debe_ejecutar(cfg, utcnow()):
                return
        except Exception:
            logger.exception('No se pudo leer sync_config')
            return

        logger.info('Sync automático a Google Sheets…')
        try:
            counts = sincronizar()
        except ErrorSincronizacion as exc:
            logger.error('Sync falló: %s', exc)
            registrar_intento(cfg, error=str(exc))
        except Exception as exc:
            logger.exception('Sync falló con error inesperado')
            registrar_intento(cfg, error=f'Error inesperado al sincronizar: {exc}')
        else:
            logger.info('Sync OK: %s', counts)
            registrar_intento(cfg, counts=counts)


def main():
    config_name = os.environ.get('FLASK_CONFIG', 'production')
    app = create_app(CONFIGS.get(config_name, ProductionConfig))

    scheduler = BlockingScheduler(timezone='UTC')
    scheduler.add_job(
        tick,
        trigger=IntervalTrigger(minutes=TICK_MINUTOS),
        args=[app],
        id='sync_sheets',
        max_instances=1,          # un tick a la vez (un sync > 60 s no se solapa)
        coalesce=True,            # ticks atrasados → uno solo
        misfire_grace_time=300,
    )
    latido()
    logger.info('Worker de sincronización arrancado (tick cada %s min)', TICK_MINUTOS)
    scheduler.start()


if __name__ == '__main__':
    main()
