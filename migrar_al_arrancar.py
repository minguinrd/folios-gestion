"""Aplica las migraciones pendientes al arrancar el contenedor `app`.

Lo invoca `docker-entrypoint.sh` antes de gunicorn (desactivable con
AUTO_MIGRATE=false). Sin esto, desplegar una imagen con una migración nueva
dejaba la app "healthy" pero con 500 en cada consulta a la tabla cambiada
(`Unknown column …`) hasta que alguien corría `flask db upgrade` a mano.

Casos:
- base vacía o con revisión de alembic → `upgrade` a head.
- tablas de la app pero sin revisión (creada con `init_db.py` / create_all,
  nunca stampeada) → NO migra: `upgrade` intentaría recrear tablas desde
  0001 y fallaría con "Table already exists". Avisa cómo stampear y deja
  arrancar la app (el esquema puede estar al día).
- cualquier error de migración → código 1: el contenedor no arranca con un
  esquema a medias (docker lo reintenta según `restart:`).
"""
import sys

from sqlalchemy import inspect, text

UPGRADE = 'upgrade'
SIN_STAMP = 'sin_stamp'

# Nombre del lock de MariaDB: dos contenedores app arrancando a la vez no
# deben correr el mismo DDL en paralelo.
LOCK = 'folios_auto_migrate'
LOCK_TIMEOUT_S = 300


def decidir(conn):
    """UPGRADE o SIN_STAMP según el estado de la base (ver docstring)."""
    tablas = set(inspect(conn).get_table_names())
    if 'alembic_version' in tablas:
        if conn.execute(text('SELECT version_num FROM alembic_version')).first():
            return UPGRADE
    tablas_app = tablas - {'alembic_version'}
    return SIN_STAMP if tablas_app else UPGRADE


def main():
    from flask_migrate import upgrade

    from app import create_app
    from app.extensions import db

    app = create_app()
    with app.app_context():
        with db.engine.connect() as conn:
            mysql = conn.dialect.name in ('mysql', 'mariadb')
            if mysql:
                ok = conn.execute(text('SELECT GET_LOCK(:n, :t)'),
                                  {'n': LOCK, 't': LOCK_TIMEOUT_S}).scalar()
                if ok != 1:
                    print('[auto-migrate] ERROR: no se obtuvo el lock de migración '
                          f'en {LOCK_TIMEOUT_S} s.', file=sys.stderr)
                    return 1
            try:
                decision = decidir(conn)
                # Cierra la transacción implícita de la lectura: con
                # REPEATABLE READ el DDL de upgrade (otra conexión) no debe
                # esperar a este snapshot.
                conn.rollback()
                if decision == SIN_STAMP:
                    print('[auto-migrate] AVISO: la base tiene tablas pero no tiene '
                          'revisión de alembic (creada con init_db.py). No se migra. '
                          'Ejecute una vez `flask db stamp <revisión que ya tiene el '
                          'esquema>` (ver README → "Síntoma Table \'…\' already '
                          'exists"); desde entonces se migrará sola al arrancar.',
                          file=sys.stderr)
                    return 0
                print('[auto-migrate] Aplicando migraciones pendientes…', flush=True)
                upgrade()
                print('[auto-migrate] Esquema al día.', flush=True)
                return 0
            except Exception as exc:  # noqa: BLE001 — se reporta y aborta el arranque
                print(f'[auto-migrate] ERROR al migrar: {exc}', file=sys.stderr)
                return 1
            finally:
                if mysql:
                    conn.execute(text('SELECT RELEASE_LOCK(:n)'), {'n': LOCK})


if __name__ == '__main__':
    sys.exit(main())
