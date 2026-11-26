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


# --- Folios: validaciones agrupadas en un menú ---


def test_validaciones_agrupadas_en_menu(admin_client):
    html = admin_client.get('/folios/').get_data(as_text=True)
    menu = html.split('id="menu-validar"', 1)[1].split('</ul>', 1)[0]
    for texto in ('Validar Digitado', 'Validar Nulos', 'Validar Escaneados'):
        assert texto in menu, texto
    assert 'class="btn btn-outline-success"' not in html.split('id="menu-validar"')[0][-600:]
    assert 'id="form-validar-escaneados"' in html, 'el POST de escaneados sigue disponible'


def test_menu_validar_oculto_sin_permisos(auth_client):
    assert 'id="menu-validar"' not in auth_client.get('/folios/').get_data(as_text=True)


# --- Migas de pan ---


def _migas(html):
    nav = re.search(r'<nav aria-label="Ruta de navegación">(.*?)</nav>', html, re.S)
    assert nav, 'faltan las migas de pan'
    return [re.sub(r'\s+', ' ', t).strip()
            for t in re.findall(r'<li class="breadcrumb-item[^"]*"[^>]*>(.*?)</li>', nav.group(1), re.S)]


def test_migas_detalle_y_objetivos_de_centro(admin_client, centro):
    detalle = _migas(admin_client.get(f'/centros/{centro.id}/detail').get_data(as_text=True))
    assert len(detalle) == 3
    assert 'Inicio' in detalle[0] and 'href="/centros/"' in detalle[1]
    assert detalle[2] == centro.name, 'la página actual va sin enlace'
    obj = _migas(admin_client.get(f'/centros/{centro.id}/objetivos').get_data(as_text=True))
    assert f'href="/centros/{centro.id}/detail"' in obj[2] and obj[3] == 'Objetivos'


def test_migas_importar_nulos_y_digitado(admin_client):
    assert _migas(admin_client.get('/folios/importar-nulos').get_data(as_text=True))[-1] == 'Validar nulos'
    assert _migas(admin_client.get('/folios/importar').get_data(as_text=True))[-1] == 'Validar digitado'


def test_migas_en_formularios_de_movimientos(admin_client, tipo):
    for url, ultimo in (('/entregas/create', 'Nueva entrega'),
                        ('/devoluciones/create', 'Nueva devolución'),
                        ('/recepcion/create', 'Nueva recepción'),
                        ('/usuarios/create', 'Nuevo usuario')):
        assert _migas(admin_client.get(url).get_data(as_text=True))[-1] == ultimo, url


def test_listados_principales_sin_migas(admin_client):
    for url in ('/folios/', '/centros/', '/dashboard/'):
        assert 'Ruta de navegación' not in admin_client.get(url).get_data(as_text=True), url


def test_todas_las_pantallas_con_migas_renderizan(admin_client, admin, tipo, centro,
                                                  folio_entregado, operador):
    """Humo: las 23 plantillas con migas abren sin error y muestran la ruta."""
    from datetime import date
    from app.models.devolucion_folio import DevolucionFolio
    from app.models.recepcion_folio import RecepcionFolio
    rec = RecepcionFolio(fecha=date(2026, 1, 5), anioCert=2026, tipoCert_id=tipo.id,
                         folioInicial=5000, folioFinal=5001, rangoId=77, userId=admin.id)
    dev_folio = make_folio(tipo, numero=6000, estado='devuelto', rangoId=78)
    from app.models.entrega_folio import EntregaFolio
    db.session.add_all([rec, EntregaFolio(folio_id=dev_folio.id, fechaEntrega=date(2026, 2, 1),
                                          centroId=centro.id, userId=admin.id)])
    db.session.flush()
    dev = DevolucionFolio(folio_id=dev_folio.id, fechaDevolucion=date(2026, 3, 1),
                          centroId=centro.id, userId=admin.id)
    db.session.add(dev)
    db.session.commit()
    urls = [
        '/centros/create', f'/centros/{centro.id}/detail', f'/centros/{centro.id}/edit',
        '/centros/importar', f'/centros/{centro.id}/objetivos',
        '/certificados/create', f'/certificados/{tipo.id}/edit',
        '/devoluciones/create', f'/devoluciones/{dev.id}/edit', '/devoluciones/importar',
        '/entregas/create', f'/entregas/{folio_entregado.entrega.id}/edit', '/entregas/importar',
        f'/folios/{folio_entregado.id}', '/folios/importar', '/folios/transferencias',
        f'/permisos/{operador.id}', '/recepcion/create', f'/recepcion/{rec.id}/edit',
        '/recepcion/importar', '/usuarios/create', f'/usuarios/{operador.id}/edit',
        '/inspecciones/entrega-antes-recepcion',
    ]
    assert len(urls) == 23
    for url in urls:
        resp = admin_client.get(url)
        assert resp.status_code == 200, (url, resp.status_code)
        assert 'Ruta de navegación' in resp.get_data(as_text=True), url
