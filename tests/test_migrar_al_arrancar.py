"""Decisión del auto-migrate del entrypoint (migrar_al_arrancar.decidir)."""

from pathlib import Path

from sqlalchemy import create_engine, text

from migrar_al_arrancar import SIN_STAMP, UPGRADE, decidir

RAIZ = Path(__file__).resolve().parent.parent


def _decidir(sql):
    engine = create_engine('sqlite://')
    with engine.connect() as conn:
        for s in sql:
            conn.execute(text(s))
        return decidir(conn)


def test_base_vacia_migra():
    assert _decidir([]) == UPGRADE


def test_con_revision_migra():
    assert _decidir([
        'CREATE TABLE usuarios (id INTEGER)',
        'CREATE TABLE alembic_version (version_num VARCHAR(32))',
        "INSERT INTO alembic_version VALUES ('0011_marca_institucion')",
    ]) == UPGRADE


def test_tablas_sin_alembic_no_migra():
    """init_db.py (create_all) sin stamp: upgrade fallaría en 0001."""
    assert _decidir(['CREATE TABLE usuarios (id INTEGER)']) == SIN_STAMP


def test_alembic_vacia_con_tablas_no_migra():
    assert _decidir([
        'CREATE TABLE usuarios (id INTEGER)',
        'CREATE TABLE alembic_version (version_num VARCHAR(32))',
    ]) == SIN_STAMP


def test_entrypoint_migra_salvo_auto_migrate_false():
    script = (RAIZ / 'docker-entrypoint.sh').read_text(encoding='utf-8')
    assert 'migrar_al_arrancar.py' in script
    assert '"${AUTO_MIGRATE:-true}" != "false"' in script
    assert script.rstrip().endswith('exec "$@"')
    assert 'ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]' in \
        (RAIZ / 'Dockerfile').read_text(encoding='utf-8')


def test_solo_app_migra_en_compose():
    """Dos contenedores corriendo el mismo DDL a la vez: el worker no migra."""
    for nombre in ('docker-compose.yml', 'docker-compose.deploy.yml'):
        compose = (RAIZ / nombre).read_text(encoding='utf-8')
        worker = compose.split('sync-worker:')[-1].split('\n  db:')[0]
        assert 'AUTO_MIGRATE: "false"' in worker, nombre
