"""Arreglos y mejoras de UI/UX (títulos, filtros, estados, menú, listados, rango)."""

import re

from app.extensions import db
from tests.conftest import make_folio, make_user


# --- Folios: título y filtro de año ---


def test_folios_titulo_es_el_modulo_no_la_marca(auth_client):
    html = auth_client.get('/folios/').get_data(as_text=True)
    h4 = re.search(r'<h4[^>]*>(.*?)</h4>', html, re.S).group(1)
    assert 'Folios' in h4
    assert 'Gestión de Folios' not in h4, 'el encabezado mostraba el nombre de la app'


def test_folios_filtro_anio_lista_los_anios_con_datos(auth_client, tipo):
    make_folio(tipo, anio=2021, numero=1, rangoId=1)
    make_folio(tipo, anio=2026, numero=2, rangoId=2)
    db.session.commit()
    html = auth_client.get('/folios/').get_data(as_text=True)
    select = re.search(r'<select id="anioCert".*?</select>', html, re.S).group(0)
    assert '<option value="2021"' in select, 'un año viejo con folios debe poder filtrarse'
    assert '<option value="2026"' in select
    assert '<option value="2030"' not in select, 'sin años futuros vacíos'


def test_reportes_filtro_anio_lista_los_anios_con_datos(auth_client, tipo):
    make_folio(tipo, anio=2019, numero=1, rangoId=1)
    db.session.commit()
    html = auth_client.get('/reportes/').get_data(as_text=True)
    select = re.search(r'<select id="anioCert".*?</select>', html, re.S).group(0)
    assert '<option value="2019"' in select


# --- Colores de estado ---


def test_estado_entregado_no_es_rojo_y_nulo_no_es_check_verde(auth_client, tipo):
    make_folio(tipo, numero=10, estado='entregado', rangoId=1)
    make_folio(tipo, numero=11, nulo=True, rangoId=2)
    db.session.commit()
    html = auth_client.get('/folios/').get_data(as_text=True)
    assert 'badge bg-danger">Entregado' not in html
    assert 'badge bg-info text-dark">Entregado' in html
    assert 'badge bg-danger">Nulo' in html, 'nulo = insignia roja'
    fila_nulo = html.split('>11</a>', 1)[1].split('</tr>', 1)[0]
    assert fila_nulo.count('fa-check-circle text-success') == 0, \
        'el ✓ verde de "nulo: sí" comunicaba algo positivo'


def test_detalle_folio_usa_los_mismos_colores(auth_client, tipo):
    folio = make_folio(tipo, numero=12, estado='entregado', nulo=True)
    db.session.commit()
    html = auth_client.get(f'/folios/{folio.id}').get_data(as_text=True)
    assert 'bg-info text-dark' in html and 'Entregado' in html
    assert 'badge bg-danger">Nulo' in html


def test_reportes_js_entregado_no_es_rojo():
    js = open('app/static/js/reports.js', encoding='utf-8').read()
    assert 'bg-danger">Entregado' not in js
    assert 'bg-info text-dark">Entregado' in js


# --- Barra superior: temporizador de sincronización ---


def test_temporizador_sync_oculto_sin_permiso(auth_client):
    assert 'id="sync-timer"' not in auth_client.get('/folios/').get_data(as_text=True)


def test_temporizador_sync_visible_para_admin(admin_client):
    assert 'id="sync-timer"' in admin_client.get('/folios/').get_data(as_text=True)


# --- Menú lateral agrupado ---


def test_menu_agrupado_para_admin(admin_client):
    html = admin_client.get('/folios/').get_data(as_text=True)
    for titulo in ('Operación', 'Control', 'Administración'):
        assert f'sidebar-section">{titulo}<' in html, f'falta la sección {titulo}'
    assert html.index('Operación') < html.index('Control') < html.index('Administración')


def test_menu_operador_sin_secciones_vacias(auth_client):
    html = auth_client.get('/folios/').get_data(as_text=True)
    assert 'sidebar-section">Operación<' in html
    assert 'sidebar-section">Administración<' not in html, 'sección sin opciones visibles'
    assert 'sidebar-section">Control<' not in html


# --- Listados: conteo y limpiar filtros ---


def test_folios_muestra_conteo(auth_client, tipo):
    for n in range(30):
        make_folio(tipo, numero=100 + n, rangoId=1)
    db.session.commit()
    html = auth_client.get('/folios/').get_data(as_text=True)
    assert 'Mostrando 1–25 de 30' in html


def test_conteo_usa_separador_de_miles():
    from app import create_app  # noqa: F401  (el filtro vive en la app)
    from app.utils import formato_miles
    assert formato_miles(5250) == '5.250'
    assert formato_miles(999) == '999'


def test_limpiar_filtros_solo_con_filtro_activo(auth_client):
    sin = auth_client.get('/folios/').get_data(as_text=True)
    con = auth_client.get('/folios/?estado=disponible').get_data(as_text=True)
    assert 'id="limpiar-filtros"' not in sin
    assert 'id="limpiar-filtros"' in con
    assert 'href="/folios/"' in con.split('id="limpiar-filtros"')[0][-200:]


def test_entregas_y_devoluciones_con_conteo_y_limpiar(auth_client):
    for url in ('/entregas/', '/devoluciones/'):
        html = auth_client.get(f'{url}?busqueda=1').get_data(as_text=True)
        assert 'id="limpiar-filtros"' in html, url
        assert 'Sin resultados' in html or 'Mostrando' in html, url


# --- Selección de folios por rango ---


def test_entrega_tiene_seleccion_por_rango_y_sugerido(admin_client, tipo):
    html = admin_client.get('/entregas/create').get_data(as_text=True)
    for id_ in ('rango-desde', 'rango-hasta', 'rango-aplicar', 'usar-sugerido'):
        assert f'id="{id_}"' in html, id_
    assert 'seleccion_rango.js' in html


def test_devolucion_tiene_seleccion_por_rango(admin_client, tipo):
    html = admin_client.get('/devoluciones/create').get_data(as_text=True)
    for id_ in ('rango-desde', 'rango-hasta', 'rango-aplicar'):
        assert f'id="{id_}"' in html, id_
    assert 'seleccion_rango.js' in html
