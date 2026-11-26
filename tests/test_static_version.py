"""Cache-busting de assets propios: un despliegue nuevo no debe servir CSS/JS viejo.

Regresión: tras desplegar la imagen en otro servidor, el navegador seguía con
un main.css en caché sin `.sidebar-section` → los títulos del menú heredaban
el color oscuro del body sobre el fondo oscuro del sidebar (modo claro).
"""
import hashlib
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / 'app' / 'static'


def _huella(rel):
    return hashlib.sha256((STATIC / rel).read_bytes()).hexdigest()[:12]


def test_css_y_js_propios_llevan_huella_del_contenido(app):
    with app.test_request_context():
        from flask import url_for
        for rel in ('css/main.css', 'css/variables.css', 'js/main.js'):
            assert url_for('static', filename=rel).endswith(f'/static/{rel}?v={_huella(rel)}')


def test_vendor_no_lleva_huella(app):
    # vendor/ ya versiona en la ruta (<lib>/<versión>/) y lleva SRI.
    with app.test_request_context():
        from flask import url_for
        url = url_for('static', filename='vendor/bootstrap/5.3.3/bootstrap.min.css')
        assert '?v=' not in url


def test_pagina_referencia_css_con_huella(auth_client):
    html = auth_client.get('/dashboard/').get_data(as_text=True)
    assert re.search(r'/static/css/main\.css\?v=[0-9a-f]{12}"', html)


def test_sidebar_define_color_propio():
    # Ningún texto del sidebar debe heredar el color del body (oscuro en light).
    css = (STATIC / 'css' / 'main.css').read_text(encoding='utf-8')
    bloque = re.search(r'\n\.sidebar \{([^}]*)\}', css).group(1)
    assert re.search(r'(?<!-)color:\s*var\(--sidebar-text\)', bloque)
