"""Guardado de JPG de folios escaneados y marcado en la DB.

Layout en disco: <SCANS_FOLDER>/<anio>/<tipo_id>/<numero>.jpg. Un folio se
identifica por (año, tipo, número): con solo <anio>/<numero>.jpg (layout
anterior) dos tipos con el mismo número y año compartían archivo y un escaneo
marcaba los folios de ambos. La carpeta de tipo es el id (no el nombre): un
tipo renombrado no deja archivos huérfanos.

Archivos del layout anterior (<anio>/<numero>.jpg) se siguen leyendo en
validar_carpeta() y se pueden mover con migrar_legados()
(migrar_escaneos.py).

Un fallo por archivo (nombre inválido, error de disco) no aborta el lote:
cada archivo se procesa de forma independiente y queda reportado.
"""

import re
from pathlib import Path

from flask import current_app

from app.extensions import db
from app.models.folio import Folio
from app.services.audit import log_audit

# Nombre estricto: 1-10 dígitos + .jpg/.jpeg. El destino en disco se reconstruye
# desde el número parseado, así que el filename del cliente nunca toca el
# filesystem (no hay path traversal posible). El tope de 10 dígitos es el de
# Folio.folio (Integer) y garantiza que int() nunca lance: una captura más larga
# (>4300 dígitos) haría crashear el lote por el límite int↔str de CPython.
NOMBRE_RE = re.compile(r'^(\d{1,10})\.(jpg|jpeg)$', re.IGNORECASE)

ANIO_DIR_RE = re.compile(r'^\d{4}$')
TIPO_DIR_RE = re.compile(r'^\d{1,10}$')

MARCADO = 'marcado'
SIN_COINCIDENCIA = 'sin_coincidencia'
NOMBRE_INVALIDO = 'nombre_invalido'
CONTENIDO_INVALIDO = 'contenido_invalido'
ERROR_GUARDAR = 'error_guardar'

# Todo JPEG/JFIF/EXIF empieza con el marcador SOI FF D8 seguido de otro FF.
# El nombre solo no basta: un PNG/PDF/HTML renombrado a .jpg se guardaría.
FIRMA_JPEG = b'\xff\xd8\xff'


def es_jpeg(archivo):
    """True si el FileStorage empieza con la firma JPEG (deja el stream en 0)."""
    stream = archivo.stream
    try:
        cabecera = stream.read(len(FIRMA_JPEG))
    finally:
        stream.seek(0)
    return cabecera == FIRMA_JPEG


def _raiz():
    return Path(current_app.config['SCANS_FOLDER'])


def ruta_escaneo(anio, tipo_id, numero):
    """Ruta canónica del escaneo de un folio."""
    return _raiz() / str(anio) / str(tipo_id) / f'{numero}.jpg'


def guardar_y_matchear(archivos, anio, tipo_id, user_id):
    """Guarda cada JPG en <SCANS_FOLDER>/<anio>/<tipo_id>/<numero>.jpg y marca el folio.

    `archivos`: lista de FileStorage (MultipleFileField).
    `anio`, `tipo_id`: selectores del form (int) — mandan sobre el lote entero.
    Devuelve el reporte:
      {'resultados': [{'nombre', 'numero', 'estado', 'folios', 'reemplazado'}],
       'marcados', 'sin_coincidencia', 'invalidos', 'errores', 'reemplazados'}
    `invalidos` cuenta nombre inválido y contenido que no es JPEG.
    """
    reporte = {'resultados': [], 'marcados': 0, 'sin_coincidencia': 0,
               'invalidos': 0, 'errores': 0, 'reemplazados': 0}

    for archivo in archivos:
        nombre = archivo.filename or ''
        match = NOMBRE_RE.match(nombre)
        if not match:
            reporte['resultados'].append(
                {'nombre': nombre, 'numero': None, 'estado': NOMBRE_INVALIDO,
                 'folios': 0})
            reporte['invalidos'] += 1
            continue

        numero = int(match.group(1))
        if not es_jpeg(archivo):
            reporte['resultados'].append(
                {'nombre': nombre, 'numero': numero,
                 'estado': CONTENIDO_INVALIDO, 'folios': 0})
            reporte['invalidos'] += 1
            continue

        destino = ruta_escaneo(anio, tipo_id, numero)
        # Reemplazar un escaneo previo es válido (re-escaneo), pero no debe
        # pasar en silencio: se reporta por archivo.
        reemplazado = destino.exists()
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            archivo.save(destino)
        except OSError:
            reporte['resultados'].append(
                {'nombre': nombre, 'numero': numero, 'estado': ERROR_GUARDAR,
                 'folios': 0})
            reporte['errores'] += 1
            continue

        # (anio, tipo, folio) es único (uq_folios_anio_tipo_folio): 0 o 1.
        folio = Folio.query.filter_by(anioCert=anio, tipoCert_id=tipo_id,
                                      folio=numero).first()
        if folio is not None:
            if not folio.escaneado:
                log_audit(user_id, 'UPDATE', 'folios', folio.id,
                          {'escaneado': False}, {'escaneado': True})
                folio.escaneado = True
                db.session.commit()
            estado = MARCADO
            reporte['marcados'] += 1
        else:
            estado = SIN_COINCIDENCIA
            reporte['sin_coincidencia'] += 1
        if reemplazado:
            reporte['reemplazados'] += 1
        reporte['resultados'].append(
            {'nombre': nombre, 'numero': numero, 'estado': estado,
             'folios': 1 if folio is not None else 0,
             'reemplazado': reemplazado})

    return reporte


def _inventario(raiz):
    """Recorre la raíz: (exactos, legados, anios_con_carpeta, archivos, ignorados).

    exactos: {(anio, tipo_id, numero)} del layout <anio>/<tipo>/<n>.jpg.
    legados: {(anio, numero): Path} del layout anterior <anio>/<n>.jpg.
    """
    exactos, legados, anios = set(), {}, set()
    archivos = ignorados = 0
    for hijo in raiz.iterdir():
        if hijo.is_file():
            # Suelto en la raíz: no pertenece a ningún año.
            ignorados += 1
            continue
        if not ANIO_DIR_RE.match(hijo.name):
            continue
        anio = int(hijo.name)
        anios.add(anio)
        for entrada in hijo.iterdir():
            if entrada.is_dir():
                if not TIPO_DIR_RE.match(entrada.name):
                    continue
                tipo_id = int(entrada.name)
                for archivo in entrada.iterdir():
                    if not archivo.is_file():
                        continue
                    match = NOMBRE_RE.match(archivo.name)
                    if match:
                        exactos.add((anio, tipo_id, int(match.group(1))))
                        archivos += 1
                    else:
                        ignorados += 1
                continue
            match = NOMBRE_RE.match(entrada.name)
            if match:
                legados[(anio, int(match.group(1)))] = entrada
                archivos += 1
            else:
                ignorados += 1
    return exactos, legados, anios, archivos, ignorados


def _folios_por_anio_numero(pares):
    """{(anio, numero): [Folio, ...]} para los pares dados."""
    por_anio = {}
    for anio, numero in pares:
        por_anio.setdefault(anio, set()).add(numero)
    resultado = {}
    for anio, numeros in por_anio.items():
        for folio in Folio.query.filter(
                Folio.anioCert == anio, Folio.folio.in_(numeros)).all():
            resultado.setdefault((folio.anioCert, folio.folio), []).append(folio)
    return resultado


def validar_carpeta(user_id):
    """Reconcilia <SCANS_FOLDER> contra la DB: marca y desmarca `escaneado`.

      - <anio>/<tipo>/<n>.jpg marca el folio (anio, tipo, n).
      - <anio>/<n>.jpg (layout anterior) marca solo si exactamente UN folio
        tiene (anio, n); si hay varios es ambiguo: no marca ni desmarca
        ninguno de ellos (se reporta en `ambiguos`).
      - Folios marcados sin archivo → False, solo si la subcarpeta de su año
        existe (año sin carpeta = volumen a medio montar: no se desmarca nada
        de ese año).
    Raíz ausente → error_raiz y cero cambios. Archivos con nombre inválido o
    sueltos en la raíz → ignorados (solo se reportan).
    Devuelve {'error_raiz', 'marcados', 'desmarcados', 'archivos',
    'ignorados', 'ambiguos', 'legados', 'anios_sin_carpeta'}.
    """
    raiz = _raiz()
    reporte = {'error_raiz': False, 'marcados': 0, 'desmarcados': 0,
               'archivos': 0, 'ignorados': 0, 'ambiguos': 0, 'legados': 0,
               'anios_sin_carpeta': []}
    if not raiz.is_dir():
        reporte['error_raiz'] = True
        return reporte

    exactos, legados, anios_con_carpeta, archivos, ignorados = _inventario(raiz)
    reporte['archivos'], reporte['ignorados'] = archivos, ignorados
    reporte['legados'] = len(legados)

    # Folios con archivo: exactos + legados inequívocos. Los pares legados
    # ambiguos quedan "protegidos": no se tocan en ningún sentido.
    con_archivo = set()  # ids de folio
    protegidos = set()   # (anio, numero) legados ambiguos
    pares = {(a, n) for a, _, n in exactos} | set(legados)
    candidatos = _folios_por_anio_numero(pares)
    for (anio, numero), folios in candidatos.items():
        for folio in folios:
            if (anio, folio.tipoCert_id, numero) in exactos:
                con_archivo.add(folio.id)
        if (anio, numero) in legados:
            if len(folios) == 1:
                con_archivo.add(folios[0].id)
            else:
                protegidos.add((anio, numero))
    reporte['ambiguos'] = len(protegidos)

    for folios in candidatos.values():
        for folio in folios:
            if folio.id in con_archivo and not folio.escaneado:
                log_audit(user_id, 'UPDATE', 'folios', folio.id,
                          {'escaneado': False}, {'escaneado': True})
                folio.escaneado = True
                reporte['marcados'] += 1

    # Desmarcar: solo años cuya carpeta existe y sin archivo correspondiente.
    sin_carpeta = set()
    for folio in Folio.query.filter_by(escaneado=True).all():
        if folio.anioCert not in anios_con_carpeta:
            sin_carpeta.add(folio.anioCert)
            continue
        if folio.id in con_archivo or (folio.anioCert, folio.folio) in protegidos:
            continue
        log_audit(user_id, 'UPDATE', 'folios', folio.id,
                  {'escaneado': True}, {'escaneado': False})
        folio.escaneado = False
        reporte['desmarcados'] += 1

    reporte['anios_sin_carpeta'] = sorted(sin_carpeta)
    if reporte['marcados'] or reporte['desmarcados']:
        db.session.commit()
    return reporte


def migrar_legados(aplicar=False):
    """Mueve <anio>/<n>.jpg (layout anterior) a <anio>/<tipo_id>/<n>.jpg.

    Solo se mueve un archivo si exactamente UN folio tiene (anio, n) y el
    destino no existe. El resto se deja en su lugar y se reporta:
      - ambiguos: varios folios (tipos) con ese año y número — hay que
        decidir a mano a qué tipo pertenece el escaneo;
      - sin_folio: ningún folio con ese año y número;
      - conflictos: el destino ya existe (no se sobrescribe).
    `aplicar=False` (default) solo informa qué haría.
    Devuelve {'movidos': [(origen, destino)], 'ambiguos': [Path],
    'sin_folio': [Path], 'conflictos': [Path]}.
    """
    raiz = _raiz()
    reporte = {'movidos': [], 'ambiguos': [], 'sin_folio': [], 'conflictos': []}
    if not raiz.is_dir():
        return reporte
    _, legados, _, _, _ = _inventario(raiz)
    candidatos = _folios_por_anio_numero(set(legados))
    for (anio, numero), origen in sorted(legados.items()):
        folios = candidatos.get((anio, numero), [])
        if not folios:
            reporte['sin_folio'].append(origen)
            continue
        if len(folios) > 1:
            reporte['ambiguos'].append(origen)
            continue
        destino = ruta_escaneo(anio, folios[0].tipoCert_id, numero)
        if destino.exists():
            reporte['conflictos'].append(origen)
            continue
        if aplicar:
            destino.parent.mkdir(parents=True, exist_ok=True)
            origen.rename(destino)
        reporte['movidos'].append((origen, destino))
    return reporte
