"""Content-Security-Policy con nonce por petición (sin JS inline no autorizado)."""

import re
from pathlib import Path

PLANTILLAS = Path(__file__).resolve().parent.parent / 'app' / 'templates'


def _nonce(resp):
    csp = resp.headers.get('Content-Security-Policy', '')
    m = re.search(r"script-src 'self' 'nonce-([A-Za-z0-9_-]+)'", csp)
    assert m, f'CSP sin nonce en script-src: {csp!r}'
    return m.group(1)


def test_csp_directivas_basicas(client):
    csp = client.get('/auth/login').headers['Content-Security-Policy']
    for directiva in ("default-src 'self'", "object-src 'none'", "base-uri 'self'",
                      "form-action 'self'", "frame-ancestors 'self'", "img-src 'self' data:",
                      "font-src 'self'", "connect-src 'self'"):
        assert directiva in csp, directiva
    assert "'unsafe-eval'" not in csp
    assert "script-src 'self' 'nonce-" in csp and "'unsafe-inline'" not in csp.split('script-src')[1].split(';')[0]


def test_nonce_distinto_por_peticion(client):
    assert _nonce(client.get('/auth/login')) != _nonce(client.get('/auth/login'))


def _scripts_inline_con_nonce(html, nonce):
    inline = re.findall(r'<script(?![^>]*\bsrc=)([^>]*)>', html)
    assert inline, 'la página debería tener al menos un script inline'
    for attrs in inline:
        assert f'nonce="{nonce}"' in attrs, f'script inline sin nonce: <script{attrs}>'


def test_todas_las_paginas_con_scripts_llevan_nonce(admin_client, tipo, centro):
    for url in ('/dashboard/', '/folios/', '/entregas/create', '/devoluciones/create',
                '/recepcion/create', f'/centros/{centro.id}/detail', '/auditoria/', '/usuarios/'):
        resp = admin_client.get(url)
        assert resp.status_code == 200, url
        _scripts_inline_con_nonce(resp.get_data(as_text=True), _nonce(resp))


def test_pagina_de_error_lleva_nonce(client):
    resp = client.get('/no-existe')
    assert resp.status_code == 404
    _scripts_inline_con_nonce(resp.get_data(as_text=True), _nonce(resp))


def test_sin_manejadores_inline_en_plantillas():
    patron = re.compile(r'\son[a-z]+\s*=\s*["\']', re.I)
    hallados = [f'{p.relative_to(PLANTILLAS)}:{n}'
                for p in PLANTILLAS.rglob('*.html')
                for n, linea in enumerate(p.read_text(encoding='utf-8').splitlines(), 1)
                if patron.search(linea)]
    assert not hallados, f'manejadores inline (bloqueados por la CSP): {hallados}'


def test_csp_modo_report_only(app, client):
    app.config['CSP_REPORT_ONLY'] = True
    resp = client.get('/auth/login')
    assert 'Content-Security-Policy-Report-Only' in resp.headers
    assert 'Content-Security-Policy' not in resp.headers
