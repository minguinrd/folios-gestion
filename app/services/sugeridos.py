"""Cantidad sugerida de certificados por tipo para un centro de salud.

Regla (por tipo de certificado activo):
  consumo mensual  = folios DEVUELTOS por el centro en la ventana
                     (SUGERIDO_VENTANA_MESES) / meses efectivos;
                     meses efectivos = min(ventana, meses desde la primera
                     entrega al centro), mínimo 1 — un centro nuevo no queda
                     subestimado por dividir entre meses en que no existía.
  existencia obj.  = objetivo manual (CentroObjetivo) si existe; si no,
                     ceil(consumo mensual × SUGERIDO_MESES_COBERTURA).
  pendientes       = folios entregados al centro y aún no devueltos (estado
                     'entregado', no nulos; las transferencias ya mueven
                     EntregaFolio.centroId al centro destino).
  sugerido         = max(0, existencia objetivo − pendientes).
  disponibles      = folios 'disponible' no nulos del tipo (informativo).

Todo con consultas agregadas por tipo (GROUP BY), no una por tipo.
"""

import math
from datetime import date, timedelta

from flask import current_app
from sqlalchemy import func

from app.extensions import db
from app.models.centro_objetivo import CentroObjetivo
from app.models.devolucion_folio import DevolucionFolio
from app.models.entrega_folio import EntregaFolio
from app.models.folio import Folio
from app.models.tipo_certificado import TipoCertificado

VENTANA_MESES_DEFAULT = 6
COBERTURA_MESES_DEFAULT = 3
DIAS_POR_MES = 30.44

MANUAL = 'manual'
HISTORIAL = 'historial'
SIN_HISTORIAL = 'sin_historial'


def parametros():
    """(ventana_meses, cobertura_meses) desde la config, con defaults."""
    cfg = current_app.config
    return (int(cfg.get('SUGERIDO_VENTANA_MESES', VENTANA_MESES_DEFAULT)),
            int(cfg.get('SUGERIDO_MESES_COBERTURA', COBERTURA_MESES_DEFAULT)))


def _por_tipo(query):
    return {tipo_id: int(n) for tipo_id, n in query.group_by(Folio.tipoCert_id).all()}


def sugerencias_centro(centro_id, hoy=None):
    """Lista de dicts por tipo activo (orden por nombre); ver docstring del módulo."""
    hoy = hoy or date.today()
    ventana, cobertura = parametros()
    inicio = hoy - timedelta(days=round(ventana * DIAS_POR_MES))

    devueltos = _por_tipo(
        db.session.query(Folio.tipoCert_id, func.count(DevolucionFolio.id))
        .join(Folio, Folio.id == DevolucionFolio.folio_id)
        .filter(DevolucionFolio.centroId == centro_id,
                DevolucionFolio.fechaDevolucion >= inicio,
                DevolucionFolio.fechaDevolucion <= hoy))
    pendientes = _por_tipo(
        db.session.query(Folio.tipoCert_id, func.count(EntregaFolio.id))
        .join(Folio, Folio.id == EntregaFolio.folio_id)
        .filter(EntregaFolio.centroId == centro_id,
                Folio.estado == 'entregado', Folio.nulo.is_(False)))
    disponibles = _por_tipo(
        db.session.query(Folio.tipoCert_id, func.count(Folio.id))
        .filter(Folio.estado == 'disponible', Folio.nulo.is_(False)))
    manuales = {o.tipoCert_id: o.cantidad for o in
                CentroObjetivo.query.filter_by(centroId=centro_id).all()}

    primera = db.session.query(func.min(EntregaFolio.fechaEntrega)) \
        .filter(EntregaFolio.centroId == centro_id).scalar()
    if primera is None:
        meses = ventana
    else:
        meses = min(ventana, max(1.0, (hoy - primera).days / DIAS_POR_MES))

    resultado = []
    tipos = TipoCertificado.query.filter_by(activo=True) \
        .order_by(TipoCertificado.name).all()
    for tipo in tipos:
        n_devueltos = devueltos.get(tipo.id, 0)
        consumo = n_devueltos / meses
        if tipo.id in manuales:
            objetivo, origen = manuales[tipo.id], MANUAL
        elif n_devueltos:
            # round(): evita que el ruido de float (2.0000001) suba un entero.
            objetivo, origen = math.ceil(round(consumo * cobertura, 6)), HISTORIAL
        else:
            objetivo, origen = 0, SIN_HISTORIAL
        n_pendientes = pendientes.get(tipo.id, 0)
        sugerido = max(0, objetivo - n_pendientes)
        n_disponibles = disponibles.get(tipo.id, 0)
        resultado.append({
            'tipo': {'id': tipo.id, 'nombre': tipo.name, 'color': tipo.color},
            'devueltos': n_devueltos,
            'consumo_mensual': round(consumo, 1),
            'pendientes': n_pendientes,
            'objetivo': objetivo,
            'origen': origen,
            'sugerido': sugerido,
            'disponibles': n_disponibles,
            'insuficiente': sugerido > n_disponibles,
        })
    return resultado
