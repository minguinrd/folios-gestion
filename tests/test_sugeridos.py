"""Cantidad sugerida de certificados por tipo y centro (app/services/sugeridos.py)."""

from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.centro import Centro
from app.models.centro_objetivo import CentroObjetivo
from app.models.devolucion_folio import DevolucionFolio
from app.models.entrega_folio import EntregaFolio
from app.models.tipo_certificado import TipoCertificado
from app.services.sugeridos import sugerencias_centro
from tests.conftest import make_folio

HOY = date(2026, 11, 25)
_numero = iter(range(10000, 99999))


def _entregar(tipo, centro, user, fecha, devuelto_el=None, nulo=False):
    """Un folio entregado al centro; opcionalmente devuelto."""
    estado = 'devuelto' if devuelto_el else 'entregado'
    folio = make_folio(tipo, numero=next(_numero), estado=estado, nulo=nulo)
    db.session.add(EntregaFolio(folio_id=folio.id, fechaEntrega=fecha,
                                centroId=centro.id, userId=user.id))
    if devuelto_el:
        db.session.add(DevolucionFolio(folio_id=folio.id, fechaDevolucion=devuelto_el,
                                       centroId=centro.id, userId=user.id))
    db.session.flush()
    return folio


def _de(resultado, tipo):
    return next(r for r in resultado if r['tipo']['id'] == tipo.id)


# --- servicio ---


def test_sin_historial_sugiere_cero_y_cuenta_pendientes(app, tipo, centro, operador):
    _entregar(tipo, centro, operador, HOY - timedelta(days=20))
    db.session.commit()
    r = _de(sugerencias_centro(centro.id, HOY), tipo)
    assert r['origen'] == 'sin_historial'
    assert (r['objetivo'], r['pendientes'], r['sugerido']) == (0, 1, 0)


def test_consumo_de_ventana_y_objetivo_por_historial(app, tipo, centro, operador):
    """Centro antiguo: 12 devoluciones en 6 meses → 2/mes × 3 meses = objetivo 6."""
    inicio = HOY - timedelta(days=400)
    for i in range(12):
        _entregar(tipo, centro, operador, inicio, devuelto_el=HOY - timedelta(days=10 + i * 10))
    # Fuera de la ventana (hace ~9 meses): no cuenta.
    for _ in range(5):
        _entregar(tipo, centro, operador, inicio, devuelto_el=HOY - timedelta(days=280))
    # Dos pendientes en el centro.
    _entregar(tipo, centro, operador, HOY - timedelta(days=5))
    _entregar(tipo, centro, operador, HOY - timedelta(days=5))
    db.session.commit()
    r = _de(sugerencias_centro(centro.id, HOY), tipo)
    assert r['devueltos'] == 12
    assert r['consumo_mensual'] == 2.0
    assert (r['origen'], r['objetivo'], r['pendientes'], r['sugerido']) == ('historial', 6, 2, 4)


def test_centro_nuevo_divide_por_meses_reales(app, tipo, centro, operador):
    """Primera entrega hace 2 meses: 4 devueltos → 2/mes (no 4/6)."""
    primera = HOY - timedelta(days=round(2 * 30.44))
    for _ in range(4):
        _entregar(tipo, centro, operador, primera, devuelto_el=HOY - timedelta(days=3))
    db.session.commit()
    r = _de(sugerencias_centro(centro.id, HOY), tipo)
    assert r['consumo_mensual'] == 2.0
    assert r['objetivo'] == 6


def test_sugerido_nunca_negativo(app, tipo, centro, operador):
    for _ in range(3):
        _entregar(tipo, centro, operador, HOY - timedelta(days=5))
    db.session.add(CentroObjetivo(centroId=centro.id, tipoCert_id=tipo.id,
                                  cantidad=1, userId=operador.id))
    db.session.commit()
    r = _de(sugerencias_centro(centro.id, HOY), tipo)
    assert (r['objetivo'], r['pendientes'], r['sugerido']) == (1, 3, 0)


@pytest.mark.parametrize('cantidad', [0, 10])
def test_manual_reemplaza_historial(app, tipo, centro, operador, cantidad):
    for _ in range(6):
        _entregar(tipo, centro, operador, HOY - timedelta(days=400),
                  devuelto_el=HOY - timedelta(days=30))
    db.session.add(CentroObjetivo(centroId=centro.id, tipoCert_id=tipo.id,
                                  cantidad=cantidad, userId=operador.id))
    db.session.commit()
    r = _de(sugerencias_centro(centro.id, HOY), tipo)
    assert (r['origen'], r['objetivo'], r['sugerido']) == ('manual', cantidad, cantidad)


def test_excluye_nulos_transferidos_y_tipos_inactivos(app, tipo, centro, operador):
    otro_centro = Centro(name='Otro', activo=True)
    inactivo = TipoCertificado(name='Viejo', color='#000000', activo=False)
    db.session.add_all([otro_centro, inactivo])
    db.session.flush()
    _entregar(tipo, centro, operador, HOY, nulo=True)            # anulado: no cuenta
    transferido = _entregar(tipo, centro, operador, HOY)
    transferido.entrega.centroId = otro_centro.id               # ya es del otro centro
    _entregar(inactivo, centro, operador, HOY)
    db.session.commit()
    resultado = sugerencias_centro(centro.id, HOY)
    assert [r['tipo']['id'] for r in resultado] == [tipo.id], 'solo tipos activos'
    assert resultado[0]['pendientes'] == 0
    assert _de(sugerencias_centro(otro_centro.id, HOY), tipo)['pendientes'] == 1


def test_disponibles_insuficientes(app, tipo, centro, operador):
    make_folio(tipo, numero=next(_numero))  # 1 disponible en almacén
    db.session.add(CentroObjetivo(centroId=centro.id, tipoCert_id=tipo.id,
                                  cantidad=5, userId=operador.id))
    db.session.commit()
    r = _de(sugerencias_centro(centro.id, HOY), tipo)
    assert (r['sugerido'], r['disponibles'], r['insuficiente']) == (5, 1, True)


def test_ventana_y_cobertura_configurables(app, tipo, centro, operador):
    for _ in range(6):
        _entregar(tipo, centro, operador, HOY - timedelta(days=400),
                  devuelto_el=HOY - timedelta(days=20))
    db.session.commit()
    app.config['SUGERIDO_VENTANA_MESES'] = 3
    app.config['SUGERIDO_MESES_COBERTURA'] = 1
    r = _de(sugerencias_centro(centro.id, HOY), tipo)
    assert (r['consumo_mensual'], r['objetivo']) == (2.0, 2)


# --- rutas ---


def test_detalle_muestra_tarjeta_sugeridos(auth_client, tipo, centro):
    text = auth_client.get(f'/centros/{centro.id}/detail').get_data(as_text=True)
    assert 'Sugerido por tipo de certificado' in text
    assert tipo.name in text
    assert 'Sin historial' in text
    assert 'Ajustar objetivos' not in text, 'operador no gestiona centros'


def test_detalle_admin_ve_boton_objetivos(admin_client, tipo, centro):
    text = admin_client.get(f'/centros/{centro.id}/detail').get_data(as_text=True)
    assert f'/centros/{centro.id}/objetivos' in text


def test_objetivos_bloqueado_para_operador(auth_client, tipo, centro):
    resp = auth_client.post(f'/centros/{centro.id}/objetivos',
                            data={f'objetivo_{tipo.id}': '5'}, follow_redirects=True)
    assert 'No tiene permisos' in resp.get_data(as_text=True)
    assert CentroObjetivo.query.count() == 0


def test_objetivos_crear_actualizar_borrar_audita(admin_client, tipo, centro):
    url = f'/centros/{centro.id}/objetivos'
    campo = f'objetivo_{tipo.id}'

    resp = admin_client.post(url, data={campo: '8'}, follow_redirects=True)
    assert '1 objetivo actualizado' in resp.get_data(as_text=True)
    assert CentroObjetivo.query.one().cantidad == 8
    assert 'value="8"' in admin_client.get(url).get_data(as_text=True)

    admin_client.post(url, data={campo: '3'})
    assert CentroObjetivo.query.one().cantidad == 3

    resp = admin_client.post(url, data={campo: '3'}, follow_redirects=True)
    assert 'Sin cambios' in resp.get_data(as_text=True)

    admin_client.post(url, data={campo: ''})
    assert CentroObjetivo.query.count() == 0, 'vacío vuelve al cálculo automático'

    acciones = [a.accion for a in AuditLog.query.filter_by(tabla='centro_objetivos')
                .order_by(AuditLog.id)]
    assert acciones == ['INSERT', 'UPDATE', 'DELETE']


@pytest.mark.parametrize('valor', ['-1', 'abc', '2.5', '²', '100001'])
def test_objetivos_valores_invalidos(admin_client, tipo, centro, valor):
    resp = admin_client.post(f'/centros/{centro.id}/objetivos',
                             data={f'objetivo_{tipo.id}': valor})
    assert resp.status_code == 400
    assert 'ingrese un entero' in resp.get_data(as_text=True)
    assert CentroObjetivo.query.count() == 0


def test_api_sugeridos(auth_client, tipo, centro):
    resp = auth_client.get(f'/centros/{centro.id}/api/sugeridos')
    assert resp.status_code == 200
    datos = resp.get_json()
    assert datos[0]['tipo']['nombre'] == tipo.name
    assert {'sugerido', 'pendientes', 'objetivo', 'origen'} <= set(datos[0])


def test_api_sugeridos_centro_inexistente(auth_client):
    assert auth_client.get('/centros/999999/api/sugeridos').status_code == 404


def test_api_sugeridos_requiere_login(client, centro):
    assert client.get(f'/centros/{centro.id}/api/sugeridos').status_code == 302


def test_formulario_entrega_tiene_panel_sugeridos(admin_client, tipo, centro):
    text = admin_client.get('/entregas/create').get_data(as_text=True)
    assert 'id="panel-sugeridos"' in text
    assert '/api/sugeridos' in text
    assert 'innerHTML = s' not in text
