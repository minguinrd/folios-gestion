"""F3 — flujos de usuario: año dinámico, login accesible, loading en formularios.

Escribir tests primero: deben fallar antes de tocar templates/JS.
"""

from datetime import datetime
from pathlib import Path

from app.extensions import db
from tests.conftest import make_folio

TEMPLATES = Path(__file__).resolve().parent.parent / 'app' / 'templates'
STATIC = Path(__file__).resolve().parent.parent / 'app' / 'static'


def _login_html(client):
    resp = client.get('/auth/login')
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


# --- Año del filtro de folios derivado del reloj, no de un range hardcodeado ---

def test_opciones_anio_siguen_al_reloj(auth_client, monkeypatch, tipo):
    """Año en curso siempre presente (aunque aún no tenga folios); sin años
    futuros vacíos; los años con folios, aunque sean viejos."""
    from datetime import date as date_real
    import app.services.queries as queries

    class FakeDate:
        @staticmethod
        def today():
            return date_real(2040, 6, 1)

    monkeypatch.setattr(queries, 'date', FakeDate)
    make_folio(tipo, anio=2031, numero=1)
    db.session.commit()
    html = auth_client.get('/folios/').get_data(as_text=True)
    assert 'value="2040"' in html, 'el año actual no aparece en el filtro'
    assert 'value="2031"' in html, 'año con folios ausente'
    assert 'value="2044"' not in html, 'no debe ofrecer años futuros vacíos'


def test_template_folios_usa_anios_con_datos():
    src = (TEMPLATES / 'folios' / 'index.html').read_text(encoding='utf-8')
    assert 'for y in anios' in src, 'el filtro de año debe venir de los datos'
    assert 'range(2025' not in src and 'range(anio_actual' not in src


# --- Login: autocomplete + mostrar contraseña ---

def test_login_autocomplete(client):
    html = _login_html(client)
    assert 'autocomplete="username"' in html, 'falta autocomplete=username'
    assert 'autocomplete="current-password"' in html, 'falta autocomplete=current-password'
    assert 'toggle-password' in html, 'falta botón mostrar/ocultar contraseña'


# --- Formularios: estado de carga antidoble-submit ---

def test_main_js_tiene_helper_de_loading():
    js = (STATIC / 'js' / 'main.js').read_text(encoding='utf-8')
    assert 'data-loading' in js, 'main.js no implementa el helper data-loading'


def test_formulario_login_con_data_loading(client):
    html = _login_html(client)
    assert 'data-loading' in html, 'form de login sin data-loading'


def test_filtro_folios_inputmode_numeric(auth_client):
    html = auth_client.get('/folios/').get_data(as_text=True)
    assert 'inputmode="numeric"' in html, 'campo de búsqueda de folio sin inputmode'


def test_folios_un_solo_buscador(auth_client):
    """Un solo campo de búsqueda: el servidor (GET busqueda), sin tablaSearch cliente."""
    html = auth_client.get('/folios/').get_data(as_text=True)
    assert 'id="tableSearch"' not in html, 'sigue el buscador duplicado tableSearch'
    assert 'name="busqueda"' in html, 'falta el buscador servidor de folios'


# --- Dark mode ---

def test_toggle_dark_mode_presente(auth_client):
    html = auth_client.get('/dashboard/').get_data(as_text=True)
    assert 'id="theme-toggle"' in html, 'falta el botón de tema en el navbar'
    js = (STATIC / 'js' / 'main.js').read_text(encoding='utf-8')
    assert 'data-bs-theme' in js, 'main.js no conmuta data-bs-theme'
    assert 'localStorage' in js, 'la preferencia de tema no se persiste'


def test_variables_css_define_tema_oscuro():
    css = (STATIC / 'css' / 'variables.css').read_text(encoding='utf-8')
    assert '[data-bs-theme="dark"]' in css, 'sin tokens del tema oscuro'


# --- Fix pass de la revisión final ---

def test_dark_no_pisa_text_dark():
    """El override global .text-dark en dark deja texto invisible sobre bg-warning/info."""
    css = (STATIC / 'css' / 'variables.css').read_text(encoding='utf-8')
    assert '[data-bs-theme="dark"] .text-dark' not in css, \
        'override .text-dark en dark rompe badges/cabeceras sobre amarillo/cian'


def test_login_titulo_tema_adaptativo():
    """El título del login vive sobre la card (oscura en dark): usa text-body-emphasis."""
    src = (TEMPLATES / 'auth' / 'login.html').read_text(encoding='utf-8')
    assert 'text-dark' not in src, 'login aún usa text-dark (ilegible en dark)'
    assert 'text-body-emphasis' in src


def test_main_js_bfcache_spinner_y_entrada():
    """data-loading: reset en pageshow (bfcache) y soporte de <input type=submit>."""
    js = (STATIC / 'js' / 'main.js').read_text(encoding='utf-8')
    assert 'pageshow' in js, 'sin reset de estado tras restaurar desde bfcache'
    assert 'tagName' in js, 'el helper no distingue input de botón (spinner no renderiza)'
    assert 'restaurar' in js, 'sin función de restauración del botón'


def test_modal_kpi_guarda_contra_carreras(auth_client):
    html = auth_client.get('/dashboard/').get_data(as_text=True)
    assert 'kpiSolicitud' in html, 'sin token de solicitud: respuestas viejas pisan el modal'
