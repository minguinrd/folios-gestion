"""Librerías de terceros servidas desde static/vendor (sin CDN)."""

import base64
import hashlib
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / 'app'
PLANTILLAS = list((RAIZ / 'templates').rglob('*.html')) + [RAIZ / '__init__.py']
REF = re.compile(
    r"""(?:src|href)="\{\{ url_for\('static', filename='(vendor/[^']+)'\) \}\}"([^>]*)>""")


def test_sin_assets_externos():
    externos = re.compile(r'https://(cdn\.|cdnjs\.|code\.jquery|fonts\.g|unpkg)')
    hallados = [f'{p.relative_to(RAIZ)}' for p in PLANTILLAS
                if externos.search(p.read_text(encoding='utf-8'))]
    assert not hallados, f'assets desde CDN/externo en: {hallados}'


def test_vendor_existe_y_coincide_con_su_integrity():
    revisados = 0
    for p in PLANTILLAS:
        for ruta, resto in REF.findall(p.read_text(encoding='utf-8')):
            archivo = RAIZ / 'static' / ruta
            assert archivo.is_file(), f'{p.name}: falta {ruta}'
            sri = re.search(r'integrity="(sha\d+)-([^"]+)"', resto)
            if sri:
                real = base64.b64encode(
                    hashlib.new(sri.group(1), archivo.read_bytes()).digest()).decode()
                assert real == sri.group(2), f'{ruta}: no coincide con su integrity'
            revisados += 1
    assert revisados >= 12


def test_fuentes_locales_referenciadas_existen():
    css = (RAIZ / 'static/vendor/fira/css/fonts.css').read_text(encoding='utf-8')
    fa = (RAIZ / 'static/vendor/fontawesome/6.5.1/css/all.min.css').read_text(encoding='utf-8')
    for base, texto in ((RAIZ / 'static/vendor/fira/css', css),
                        (RAIZ / 'static/vendor/fontawesome/6.5.1/css', fa)):
        urls = set(re.findall(r'url\((\.\./[^)]+)\)', texto))
        assert urls
        for u in urls:
            assert (base / u).resolve().is_file(), f'fuente faltante: {u}'


def test_sweetalert_version_fija():
    base = (RAIZ / 'templates/base.html').read_text(encoding='utf-8')
    assert 'sweetalert2@11"' not in base, 'versión flotante + integrity = script bloqueado'
    assert 'vendor/sweetalert2/11.26.25/' in base


def test_static_vendor_se_sirve(client):
    resp = client.get('/static/vendor/bootstrap/5.3.3/bootstrap.min.css')
    assert resp.status_code == 200
    assert b'Bootstrap' in resp.data[:200]
