"""Listado de centros: fecha de la última entrega y la última devolución."""

from datetime import date
from io import BytesIO

from openpyxl import load_workbook

from app.extensions import db
from app.models.centro import Centro
from app.models.devolucion_folio import DevolucionFolio
from app.models.entrega_folio import EntregaFolio
from tests.conftest import make_folio

Y = 2026


def _seed(tipo, centro, operador):
    """Dos entregas (1/6 y 15/6) y una devolución (10/6) al centro; otro centro sin movimientos."""
    f1 = make_folio(tipo, anio=Y, numero=9001, estado='devuelto')
    f2 = make_folio(tipo, anio=Y, numero=9002, estado='entregado')
    db.session.add_all([
        EntregaFolio(folio_id=f1.id, fechaEntrega=date(Y, 6, 1),
                     centroId=centro.id, userId=operador.id),
        EntregaFolio(folio_id=f2.id, fechaEntrega=date(Y, 6, 15),
                     centroId=centro.id, userId=operador.id),
        DevolucionFolio(folio_id=f1.id, fechaDevolucion=date(Y, 6, 10),
                        centroId=centro.id, userId=operador.id),
    ])
    vacio = Centro(name='Centro Sin Movimientos', activo=True)
    db.session.add(vacio)
    db.session.commit()
    return vacio


def test_listado_muestra_ultima_entrega_y_devolucion(auth_client, tipo, centro, operador):
    _seed(tipo, centro, operador)
    text = auth_client.get('/centros/').get_data(as_text=True)
    assert 'Última entrega' in text and 'Última devolución' in text
    # La más reciente de cada tipo, no la primera.
    assert 'data-order="2026-06-15"' in text and '15/06/2026' in text
    assert 'data-order="2026-06-10"' in text and '10/06/2026' in text
    assert '01/06/2026' not in text


def test_centro_sin_movimientos_muestra_sin_registro(auth_client, tipo, centro, operador):
    _seed(tipo, centro, operador)
    text = auth_client.get('/centros/').get_data(as_text=True)
    fila = text.split('Centro Sin Movimientos', 1)[1].split('</tr>', 1)[0]
    assert fila.count('Sin registro') == 2


def test_listado_vacio_colspan_cubre_las_columnas(auth_client):
    text = auth_client.get('/centros/').get_data(as_text=True)
    assert 'colspan="7"' in text


def test_export_excel_lista_incluye_fechas(auth_client, tipo, centro, operador):
    _seed(tipo, centro, operador)
    resp = auth_client.get('/centros/export/excel')
    filas = list(load_workbook(BytesIO(resp.data)).active.iter_rows(values_only=True))
    assert filas[0][5:] == ('Última entrega', 'Última devolución')
    por_nombre = {f[1]: f for f in filas[1:]}
    assert por_nombre[centro.name][5:] == ('15/06/2026', '10/06/2026')
    assert por_nombre['Centro Sin Movimientos'][5:] == ('-', '-')


def test_export_pdf_lista_incluye_fechas(auth_client, tipo, centro, operador, monkeypatch):
    """Revisa el HTML que se pasa a WeasyPrint (sin depender de pango/cairo)."""
    import weasyprint
    capturado = {}

    class HTMLFalso:
        def __init__(self, string):
            capturado['html'] = string

        def write_pdf(self):
            return b'%PDF-falso'

    monkeypatch.setattr(weasyprint, 'HTML', HTMLFalso)
    _seed(tipo, centro, operador)
    resp = auth_client.get('/centros/export/pdf')
    assert resp.status_code == 200
    html = capturado['html']
    assert 'Última entrega' in html and 'Última devolución' in html
    assert '15/06/2026' in html and '10/06/2026' in html
