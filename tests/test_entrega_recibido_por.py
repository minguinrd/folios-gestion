"""Nombre de quien recibe la entrega (`entrega_folios.recibidoPor`)."""

from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.entrega_folio import EntregaFolio
from tests.conftest import make_folio


def _crear(client, folio, centro, recibido):
    return client.post('/entregas/create', data={
        'folio_ids': [folio.id], 'fechaEntrega': '28/09/2026',
        'centroId': centro.id, 'recibidoPor': recibido,
    }, follow_redirects=True)


def test_formulario_muestra_campo(auth_client):
    html = auth_client.get('/entregas/create').get_data(as_text=True)
    assert 'id="recibidoPor"' in html
    assert 'Recibido por' in html


def test_crear_guarda_nombre_normalizado_y_audita(auth_client, tipo, centro):
    folio = make_folio(tipo, numero=5001)
    resp = _crear(auth_client, folio, centro, '  Ana   Pérez ')
    assert resp.status_code == 200
    entrega = EntregaFolio.query.filter_by(folio_id=folio.id).one()
    assert entrega.recibidoPor == 'Ana Pérez'
    log = AuditLog.query.filter_by(tabla='entrega_folios', registro_id=entrega.id).one()
    assert 'Ana Pérez' in str(log.datos_nuevos)


def test_crear_sin_nombre_rechazado(auth_client, tipo, centro):
    folio = make_folio(tipo, numero=5002)
    resp = _crear(auth_client, folio, centro, '   ')
    assert 'Indique el nombre de quien recibe los folios.' in resp.get_data(as_text=True)
    db.session.refresh(folio)
    assert folio.estado == 'disponible'
    assert EntregaFolio.query.count() == 0


def test_crear_nombre_largo_rechazado(auth_client, tipo, centro):
    folio = make_folio(tipo, numero=5003)
    _crear(auth_client, folio, centro, 'x' * 121)
    assert EntregaFolio.query.count() == 0


def test_editar_completa_nombre_y_listado_lo_muestra(auth_client, folio_entregado):
    entrega = folio_entregado.entrega
    assert entrega.recibidoPor is None
    assert '—' in auth_client.get('/entregas/').get_data(as_text=True)

    resp = auth_client.post(f'/entregas/{entrega.id}/edit', data={
        'folio_id': folio_entregado.id, 'fechaEntrega': '01/09/2026',
        'centroId': entrega.centroId, 'recibidoPor': 'Juan Gómez',
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(entrega)
    assert entrega.recibidoPor == 'Juan Gómez'
    assert 'Juan Gómez' in auth_client.get('/entregas/').get_data(as_text=True)


# --- Reportes: columna "Entregado a" en PDF y Excel ---

def test_reporte_excel_columna_entregado_a(admin_client, folio_entregado):
    from io import BytesIO
    from openpyxl import load_workbook

    folio_entregado.entrega.recibidoPor = 'Ana Pérez'
    db.session.commit()
    resp = admin_client.get('/reportes/export/excel')
    filas = list(load_workbook(BytesIO(resp.data)).active.iter_rows(values_only=True))
    col = filas[0].index('Entregado a')
    assert filas[0][col - 1] == 'Entregado por'
    assert filas[1][col] == 'Ana Pérez'


def test_reporte_excel_entregado_a_vacio_es_guion(admin_client, folio_entregado):
    from io import BytesIO
    from openpyxl import load_workbook

    resp = admin_client.get('/reportes/export/excel')
    filas = list(load_workbook(BytesIO(resp.data)).active.iter_rows(values_only=True))
    assert filas[1][filas[0].index('Entregado a')] == '-'


def test_reporte_pdf_columna_entregado_a_escapada(admin_client, folio_entregado,
                                                 monkeypatch):
    from tests.test_ui_lote5 import _capturar_pdf

    fake = _capturar_pdf(monkeypatch)
    folio_entregado.entrega.recibidoPor = 'Ana <b>Pérez</b>'
    db.session.commit()
    assert admin_client.get('/reportes/export/pdf').status_code == 200
    html = fake.captured[0]
    assert '<th>Entregado a</th>' in html
    assert '<td>Ana &lt;b&gt;Pérez&lt;/b&gt;</td>' in html
