"""Fixtures del recorrido en navegador (Playwright + Chromium headless).

No corre con la suite normal: `pytest.ini` excluye el marcador `e2e`.
    pip install -r requirements-e2e.txt && playwright install chromium
    python3 -m pytest -m e2e
Sin Playwright instalado, estas pruebas se omiten.
"""
import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

pytest.importorskip('playwright.sync_api', reason='requiere requirements-e2e.txt')
from playwright.sync_api import sync_playwright  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _puerto_libre():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture(scope='session')
def base_url(tmp_path_factory):
    """Levanta tests/e2e/servidor.py en un puerto libre y devuelve su URL."""
    directorio = tmp_path_factory.mktemp('e2e')
    puerto = _puerto_libre()
    log = open(directorio / 'servidor.log', 'w')
    proc = subprocess.Popen([sys.executable, '-m', 'tests.e2e.servidor', str(puerto), str(directorio)],
                            cwd=RAIZ, stdout=log, stderr=subprocess.STDOUT)
    url = f'http://127.0.0.1:{puerto}'
    try:
        for _ in range(150):
            if proc.poll() is not None:
                break
            try:
                urllib.request.urlopen(url + '/health', timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        else:
            raise RuntimeError('el servidor E2E no respondió a tiempo')
        if proc.poll() is not None:
            log.flush()
            raise RuntimeError('el servidor E2E terminó:\n' + (directorio / 'servidor.log').read_text())
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        log.close()


@pytest.fixture(scope='session')
def navegador():
    with sync_playwright() as p:
        nav = p.chromium.launch()
        yield nav
        nav.close()


class Vigia:
    """Junta errores de consola/JS, violaciones de CSP, peticiones fallidas y externas."""

    def __init__(self, base):
        self.base = base
        self.problemas = []

    def vigilar(self, page):
        page.on('console', self._consola)
        page.on('pageerror', lambda e: self.problemas.append(f'JS: {e}'))
        page.on('requestfailed', lambda r: self.problemas.append(f'falló {r.url} {r.failure}'))
        page.on('response', self._respuesta)

    def _consola(self, msg):
        if msg.type in ('error', 'warning') and 'favicon' not in msg.text:
            self.problemas.append(f'consola {msg.type}: {msg.text[:200]}')

    def _respuesta(self, r):
        if not r.url.startswith(self.base):
            self.problemas.append(f'petición externa: {r.url}')
        elif r.status >= 400 and not r.url.endswith('/no-existe'):
            self.problemas.append(f'HTTP {r.status} {r.url}')


@pytest.fixture(scope='module')
def vigia(base_url):
    return Vigia(base_url)


@pytest.fixture(autouse=True)
def sin_problemas_de_navegador(vigia):
    """Cada prueba falla si dejó errores de consola, CSP o red."""
    vigia.problemas.clear()
    yield
    assert not vigia.problemas, '\n'.join(vigia.problemas)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    resultado = yield
    rep = resultado.get_result()
    if rep.when == 'call' and rep.failed:
        page = getattr(item, '_pagina_e2e', None)
        if page is not None:
            destino = os.path.join(RAIZ, '.pytest_cache', 'e2e', item.name + '.png')
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            try:
                page.screenshot(path=destino, full_page=True)
                rep.sections.append(('captura E2E', destino))
            except Exception:  # la página pudo cerrarse
                pass
