"""Versión de la app: el archivo VERSION es la única fuente.

`app/version.py` lee el archivo VERSION de la raíz del repo (viaja en la
imagen Docker) y `create_app` lo expone como `app.config['APP_VERSION']` y
como `app_version` en todos los templates. El footer del sidebar lo muestra;
no hay números de versión hardcodeados.
"""

import re
from pathlib import Path

from app.version import leer_version


def test_leer_version_lee_el_archivo_del_repo():
    esperada = Path(__file__).resolve().parent.parent \
        .joinpath('VERSION').read_text(encoding='utf-8').strip()
    assert esperada, 'el repo debe mantener el archivo VERSION'
    assert leer_version() == esperada


def test_leer_version_fallback_dev(monkeypatch):
    monkeypatch.setattr('app.version.RUTA_VERSION',
                        Path('/no/existe/VERSION'))
    assert leer_version() == 'dev'


def test_sidebar_muestra_la_version(admin_client):
    text = admin_client.get('/dashboard/',
                            follow_redirects=True).get_data(as_text=True)
    bloque = re.search(r'<div class="sidebar-footer">.*?</div>', text, re.S)
    assert bloque, 'el sidebar tiene footer con versión'
    assert f'v{leer_version()}' in bloque.group(0)
    assert 'v1.0.0' not in text, 'sin versión hardcodeada'


# --- La documentación de despliegue sigue a VERSION ---
# Si se sube VERSION y se olvida actualizar el tag citado, los servidores
# seguirían bajando la imagen anterior (o la doc de Docker Hub quedaría vieja).

RAIZ = Path(__file__).resolve().parent.parent


def test_compose_de_despliegue_usa_la_version_actual():
    compose = (RAIZ / 'docker-compose.deploy.yml').read_text(encoding='utf-8')
    tags = set(re.findall(r'm809/folios-gestion:([0-9][\w.]*)', compose))
    assert tags == {leer_version()}, f'tags en el compose {tags} ≠ VERSION'


def test_readme_y_dockerhub_citan_la_version_actual():
    v = leer_version()
    readme = (RAIZ / 'README.md').read_text(encoding='utf-8')
    assert f'(tags: `{v}`, `latest`)' in readme
    hub = (RAIZ / 'docker-hub-description.md').read_text(encoding='utf-8')
    assert f'image: m809/folios-gestion:{v}' in hub
    assert f'`m809/folios-gestion:{v}` — versión fija' in hub
    assert f'Novedades de {v}' in hub, 'falta la sección de novedades de la versión'


def test_descripcion_dockerhub_valida():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'dockerhub_descripcion', RAIZ / 'scripts' / 'dockerhub_descripcion.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    datos = mod.payload()
    assert 0 < len(datos['description']) <= 100
    assert datos['full_description'].startswith('# folios-gestion')
