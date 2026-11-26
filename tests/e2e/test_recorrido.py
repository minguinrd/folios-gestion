"""Recorrido de la interfaz en Chromium: lo que los tests con test_client no ven.

Fuentes e íconos locales, Chart.js, modales de Bootstrap, SweetAlert2, DataTables,
flatpickr, selección por rango, CSP sin violaciones y sin peticiones a otros orígenes.

Las pruebas van en orden y comparten página y datos (ver tests/e2e/servidor.py):
el objetivo manual de una alimenta el sugerido de la siguiente, la entrega
de una es la devolución de la otra. Correr el módulo completo.
"""
import re

import pytest
from playwright.sync_api import expect

from tests.e2e.servidor import CLAVE

pytestmark = pytest.mark.e2e


def login(page, base_url, usuario):
    page.goto(f'{base_url}/auth/login')
    page.fill('input[name=username]', usuario)
    page.fill('input[name=password]', CLAVE)
    page.click('[type=submit]')
    page.wait_for_url(re.compile(r'/dashboard/'))


@pytest.fixture(scope='module')
def pagina(navegador, vigia):
    ctx = navegador.new_context(viewport={'width': 1366, 'height': 900}, locale='es-DO')
    page = ctx.new_page()
    vigia.vigilar(page)
    yield page
    ctx.close()


@pytest.fixture(autouse=True)
def _captura_si_falla(request, pagina):
    request.node._pagina_e2e = pagina


def test_login_fuentes_e_iconos_locales(pagina, base_url):
    pagina.goto(f'{base_url}/auth/login')
    pagina.wait_for_load_state('networkidle')
    assert pagina.evaluate("document.fonts.check('16px \"Fira Sans\"')")
    fa = pagina.evaluate("getComputedStyle(document.querySelector('.fas, .fa-solid'), '::before').fontFamily")
    assert 'Font Awesome' in fa
    assert 'Dirección Provincial de Salud Santiago 1' in pagina.content()


def test_dashboard_grafico_y_modal_kpi(pagina, base_url):
    login(pagina, base_url, 'admin')
    pagina.wait_for_load_state('networkidle')
    assert pagina.evaluate("!!(window.Chart && Chart.getChart(document.getElementById('tendenciaChart')))")

    pagina.click('.kpi-card[data-kpi="entregado"]')
    expect(pagina.locator('#kpiModal')).to_be_visible()
    pagina.wait_for_timeout(500)  # Bootstrap ignora Escape durante la animación de apertura
    pagina.keyboard.press('Escape')
    expect(pagina.locator('#kpiModal')).to_be_hidden()

    pagina.focus('.kpi-card[data-kpi="nulo"]')
    pagina.keyboard.press('Enter')
    expect(pagina.locator('#kpiModal')).to_be_visible()
    assert 'Nulos' in pagina.locator('#kpiModal').inner_text()
    pagina.wait_for_timeout(500)
    pagina.keyboard.press('Escape')
    expect(pagina.locator('#kpiModal')).to_be_hidden()

    secciones = [s.strip().lower() for s in pagina.locator('.sidebar-section').all_inner_texts()]
    assert secciones == ['operación', 'control', 'administración']


def test_menu_lateral_cabe_en_la_ventana(pagina, base_url):
    pagina.goto(f'{base_url}/dashboard/')
    alto = pagina.evaluate("document.getElementById('sidebar-wrapper').scrollHeight")
    assert 0 < alto <= 900, f'el menú mide {alto}px en una ventana de 900px'



def test_folios_menu_validar_sweetalert_y_modal(pagina, base_url):
    pagina.goto(f'{base_url}/folios/')
    assert 'Mostrando 1–25 de 400' in pagina.content()

    pagina.click('#menu-validar')
    expect(pagina.locator('.dropdown-menu.show')).to_be_visible()
    pagina.click('#btn-validar-escaneados')
    expect(pagina.locator('.swal2-popup')).to_be_visible()
    pagina.wait_for_timeout(300)
    pagina.click('.swal2-cancel')
    expect(pagina.locator('.swal2-popup')).to_be_hidden()

    pagina.click('[data-editar-estado] >> nth=0')
    expect(pagina.locator('#statusModal')).to_be_visible()
    assert 'Folio:' in pagina.locator('#modal-info').inner_text()
    pagina.check('#modal-digitado')
    pagina.click('#btn-save-status')
    expect(pagina.locator('#statusModal')).to_be_hidden()
    pagina.wait_for_load_state('networkidle')

    pagina.goto(f'{base_url}/folios/?estado=digitado')
    assert 'Mostrando 1–1 de 1' in pagina.content()
    assert pagina.locator('#limpiar-filtros').is_visible()
    pagina.goto(f'{base_url}/folios/?estado=entregado')
    assert pagina.locator('.badge.bg-info:has-text("Entregado")').count() > 0


def test_avisos_no_tapan_el_encabezado(pagina, base_url):
    pagina.goto(f'{base_url}/folios/')
    pagina.evaluate("AppToast.mostrar('Aviso de prueba', 'info')")
    aviso = pagina.locator('.app-toast').last
    expect(aviso).to_be_visible()
    pagina.wait_for_timeout(350)  # animación de entrada
    a = aviso.bounding_box()
    e = pagina.locator('#contenido > .d-flex.justify-content-between').first.bounding_box()
    solapa = not (a['x'] + a['width'] <= e['x'] or e['x'] + e['width'] <= a['x']
                  or a['y'] + a['height'] <= e['y'] or e['y'] + e['height'] <= a['y'])
    assert not solapa, f'el aviso (y={a["y"]:.0f}) tapa el encabezado (y={e["y"]:.0f})'


def test_centro_migas_datatables_y_objetivo_manual(pagina, base_url):
    pagina.goto(f'{base_url}/centros/')
    pagina.click('text=Hospital Central')
    pagina.wait_for_url(re.compile(r'/detail'))
    pagina.wait_for_load_state('networkidle')
    assert pagina.locator('nav[aria-label="Ruta de navegación"]').inner_text().count('Centros') == 1
    assert pagina.locator('.dataTables_wrapper').count() > 0

    pagina.click('text=Ajustar objetivos')
    pagina.fill('input[id^=objetivo_] >> nth=0', '40')  # Defunciones (orden alfabético)
    pagina.click('button:has-text("Guardar objetivos")')
    pagina.wait_for_url(re.compile(r'/detail'))
    fila = pagina.locator('#card-sugeridos tr:has-text("Defunciones")').inner_text()
    assert '28' in fila and 'Manual' in fila, fila  # objetivo 40 − 12 pendientes


def test_entrega_sugerido_rango_y_guardado(pagina, base_url):
    pagina.goto(f'{base_url}/entregas/create')
    pagina.select_option('#centroId', label='Hospital Central')
    expect(pagina.locator('#panel-sugeridos')).to_be_visible()
    assert 'Defunciones: sugerido 28' in pagina.locator('#lista-sugeridos').inner_text()

    pagina.select_option('#tipo-select', label='Defunciones')
    pagina.wait_for_function("document.querySelectorAll('#folio-select option').length > 100")
    expect(pagina.locator('#usar-sugerido')).to_be_visible()
    pagina.click('#usar-sugerido')
    expect(pagina.locator('#selected-count')).to_have_text('28 seleccionados')
    expect(pagina.locator('#resumen-inicial')).to_have_text('1030')  # el más bajo disponible

    pagina.fill('#rango-desde', '1100')
    pagina.fill('#rango-hasta', '1109')
    pagina.press('#rango-hasta', 'Enter')  # aplica el rango, no envía el formulario
    expect(pagina.locator('#selected-count')).to_have_text('10 seleccionados')
    assert '/entregas/create' in pagina.url

    # flatpickr deja el input en solo lectura: la fecha se fija con su API
    pagina.evaluate("document.querySelector('#fechaEntrega')._flatpickr.setDate('20/11/2026', true, 'd/m/Y')")
    pagina.click('input[type=submit][value^="Registrar"]')
    pagina.wait_for_url(re.compile(r'/entregas/$'))
    assert '10 entregas registradas' in pagina.content()
    assert 'Mostrando 1–' in pagina.content()


def test_devolucion_rango_sobre_pendientes(pagina, base_url):
    pagina.goto(f'{base_url}/devoluciones/create')
    pagina.select_option('#centro-select', label='Hospital Central')
    pagina.select_option('#tipo-select', label='Defunciones')
    pagina.wait_for_function("document.querySelectorAll('#folio-select option').length > 0")
    pagina.fill('#rango-desde', '1100')
    pagina.fill('#rango-hasta', '1104')
    pagina.click('#rango-aplicar')
    expect(pagina.locator('#selected-count')).to_have_text('5 seleccionados')


def test_marca_institucion_en_barra_superior(pagina, base_url):
    pagina.goto(f'{base_url}/marca/')
    pagina.fill('#institucion', 'Hospital Regional de Prueba')
    pagina.click('form[enctype] [type=submit]')
    pagina.wait_for_load_state('networkidle')
    expect(pagina.locator('nav.navbar')).to_contain_text('Hospital Regional de Prueba')


def test_tema_oscuro_y_pagina_de_error(pagina, base_url, vigia):
    pagina.goto(f'{base_url}/dashboard/')
    pagina.click('#theme-toggle')
    assert pagina.evaluate("document.documentElement.getAttribute('data-bs-theme')") == 'dark'
    pagina.click('#theme-toggle')
    assert pagina.evaluate("document.documentElement.getAttribute('data-bs-theme')") == 'light'

    pagina.goto(f'{base_url}/no-existe')
    radio = pagina.evaluate("getComputedStyle(document.querySelector('.btn-primary')).borderRadius")
    assert radio != '0px', 'la página de error quedó sin estilos'
    esperado = [p for p in vigia.problemas if 'status of 404' in p]  # el 404 buscado
    assert len(esperado) == 1
    vigia.problemas.remove(esperado[0])


def test_operador_movil_menu_reducido(navegador, base_url, vigia):
    ctx = navegador.new_context(viewport={'width': 390, 'height': 844})
    try:
        page = ctx.new_page()
        vigia.vigilar(page)
        login(page, base_url, 'operador')
        page.goto(f'{base_url}/folios/')
        secciones = [s.strip().lower() for s in page.locator('.sidebar-section').all_inner_texts()]
        assert secciones == ['operación']
        assert page.locator('#sync-timer').count() == 0
        page.click('#toggle-sidebar')
        expect(page.locator('.sidebar-section').first).to_be_in_viewport()
    finally:
        ctx.close()


def test_csp_bloquea_script_inyectado(pagina, base_url, vigia):
    """Un <script> sin nonce (como el de una inyección) no se ejecuta."""
    pagina.goto(f'{base_url}/dashboard/')
    pagina.evaluate("""() => {
        const s = document.createElement('script');
        s.textContent = 'window.__inyectado = true';
        document.body.appendChild(s);
    }""")
    pagina.wait_for_timeout(100)
    assert pagina.evaluate('window.__inyectado === undefined')
    bloqueos = [p for p in vigia.problemas if 'Content Security Policy' in p]
    assert bloqueos, 'el navegador no reportó la violación de CSP'
    for p in bloqueos:  # la violación es lo esperado aquí, no un problema
        vigia.problemas.remove(p)
