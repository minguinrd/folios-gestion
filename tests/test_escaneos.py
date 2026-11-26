"""Módulo de escaneos: subir JPG de folios y marcarlos como escaneados."""

import os
from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage

from app.config import Config
from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.folio import Folio
from app.services.escaneos import guardar_y_matchear, validar_carpeta
from app.services.permisos import PERMISOS, puede
from tests.conftest import make_folio, make_user


def test_permiso_escaneos_existe_y_es_admin():
    assert 'escaneos.subir' in PERMISOS
    assert PERMISOS['escaneos.subir'] == ('Subir escaneos', 'admin')


def test_permiso_escaneos_por_rol(app):
    operador = make_user('operador', 'operador')
    lectura = make_user('lector', 'lectura')
    assert puede('escaneos.subir', operador) is False
    assert puede('escaneos.subir', lectura) is False


def test_config_scans_folder():
    assert Config.SCANS_FOLDER.endswith('scans')
    assert os.path.isabs(Config.SCANS_FOLDER)


@pytest.fixture()
def scans_dir(app, tmp_path):
    """Apunta SCANS_FOLDER a un tmp por test: nada toca la carpeta real."""
    path = tmp_path / 'scans'
    app.config['SCANS_FOLDER'] = str(path)
    return path


SOI = b'\xff\xd8\xff'  # firma JPEG: los helpers la anteponen al contenido
# Id del fixture `tipo` (primer TipoCertificado de la DB en memoria). Los
# tests de servicio sin fixture usan el mismo id: solo define la carpeta.
TIPO = 1


def jpg(nombre, data=b'JPEGDATA', crudo=False):
    return FileStorage(stream=BytesIO(data if crudo else SOI + data),
                       filename=nombre)


def test_servicio_guarda_y_marca(app, tipo, scans_dir):
    folio = make_folio(tipo, anio=2026, numero=1000)
    db.session.commit()
    with app.test_request_context():
        reporte = guardar_y_matchear([jpg('1000.jpg')], 2026, tipo.id, folio.id)
    assert reporte['marcados'] == 1
    assert reporte['resultados'][0]['estado'] == 'marcado'
    assert reporte['resultados'][0]['folios'] == 1
    assert folio.escaneado is True
    assert (scans_dir / '2026' / str(TIPO) / '1000.jpg').read_bytes() == SOI + b'JPEGDATA'


def test_servicio_marca_solo_el_tipo_elegido(app, tipo, scans_dir):
    """Regresión: mismo número y año en dos tipos → solo el del selector."""
    from app.models.tipo_certificado import TipoCertificado
    otro = TipoCertificado(name='Nacimientos', color='#0D6EFD', activo=True)
    db.session.add(otro)
    db.session.commit()
    f1 = make_folio(tipo, anio=2026, numero=1000)
    f2 = make_folio(otro, anio=2026, numero=1000, rangoId=2)
    db.session.commit()
    with app.test_request_context():
        reporte = guardar_y_matchear([jpg('1000.jpg')], 2026, otro.id, 1)
    assert f1.escaneado is False
    assert f2.escaneado is True
    assert reporte['resultados'][0]['folios'] == 1
    assert (scans_dir / '2026' / str(otro.id) / '1000.jpg').exists()
    assert not (scans_dir / '2026' / str(tipo.id) / '1000.jpg').exists()


def test_servicio_sin_coincidencia_guarda_igual(app, scans_dir):
    with app.test_request_context():
        reporte = guardar_y_matchear([jpg('9999.jpg')], 2026, TIPO, 1)
    assert reporte['sin_coincidencia'] == 1
    assert reporte['marcados'] == 0
    assert (scans_dir / '2026' / str(TIPO) / '9999.jpg').exists()


def test_servicio_nombres_invalidos_no_escriben(app, scans_dir):
    invalidos = ['1000 copia.jpg', '../../1000.jpg', 'abc.jpg',
                 '1000.png', '1000', '.jpg']
    with app.test_request_context():
        reporte = guardar_y_matchear([jpg(n) for n in invalidos], 2026, TIPO, 1)
    assert reporte['invalidos'] == len(invalidos)
    assert reporte['resultados'][0]['estado'] == 'nombre_invalido'
    assert not scans_dir.exists(), 'ningún inválido debe crear la carpeta'


def test_servicio_nombre_con_demasiados_digitos_no_crashea(app, scans_dir):
    # >4300 dígitos: int() lanzaría ValueError (límite CPython) y abortaría el
    # lote. Con el gate de 1-10 dígitos el nombre queda inválido y el resto sigue.
    nombre_largo = '9' * 5000 + '.jpg'
    with app.test_request_context():
        reporte = guardar_y_matchear(
            [jpg(nombre_largo), jpg('1000.jpg')], 2026, TIPO, 1)
    assert reporte['invalidos'] == 1
    assert reporte['resultados'][0]['estado'] == 'nombre_invalido'
    assert (scans_dir / '2026' / str(TIPO) / '1000.jpg').exists(), \
        'el válido del mismo lote debe procesarse igual'


def test_servicio_mayusculas_y_jpeg_aceptados(app, tipo, scans_dir):
    folio = make_folio(tipo, anio=2026, numero=1001)
    db.session.commit()
    with app.test_request_context():
        guardar_y_matchear([jpg('1001.JPG'), jpg('1001.jpeg')], 2026, TIPO, 1)
    assert folio.escaneado is True
    # El destino se reconstruye desde el número: siempre <numero>.jpg
    assert (scans_dir / '2026' / str(TIPO) / '1001.jpg').exists()


def test_servicio_sobrescribe(app, scans_dir):
    with app.test_request_context():
        guardar_y_matchear([jpg('1000.jpg', b'UNO')], 2026, TIPO, 1)
        guardar_y_matchear([jpg('1000.jpg', b'DOS')], 2026, TIPO, 1)
    assert (scans_dir / '2026' / str(TIPO) / '1000.jpg').read_bytes() == SOI + b'DOS'


def test_servicio_anio_distinto_no_matchea(app, tipo, scans_dir):
    folio = make_folio(tipo, anio=2025, numero=1000)
    db.session.commit()
    with app.test_request_context():
        reporte = guardar_y_matchear([jpg('1000.jpg')], 2026, TIPO, 1)
    assert reporte['sin_coincidencia'] == 1
    assert folio.escaneado is False
    assert (scans_dir / '2026' / str(TIPO) / '1000.jpg').exists(), 'el archivo va al año pedido'


def test_servicio_audita_solo_cambio(app, tipo, scans_dir):
    folio = make_folio(tipo, anio=2026, numero=1000)
    db.session.commit()
    with app.test_request_context():
        guardar_y_matchear([jpg('1000.jpg')], 2026, TIPO, 1)
        primera = AuditLog.query.filter_by(tabla='folios', registro_id=folio.id).count()
        guardar_y_matchear([jpg('1000.jpg')], 2026, TIPO, 1)
        segunda = AuditLog.query.filter_by(tabla='folios', registro_id=folio.id).count()
    assert primera == 1, 'el primer marcado debe auditar'
    assert segunda == 1, 're-subir no debe duplicar el log'


def escribir(scans_dir, anio, nombre):
    """Crea un JPG directamente en la carpeta (simula subida externa/FTP)."""
    carpeta = scans_dir / str(anio)
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / nombre).write_bytes(b'IMG')


# --- validar_carpeta: reconciliar scans/ contra la DB ---


def test_validar_marca_desde_carpeta(app, tipo, scans_dir):
    folio = make_folio(tipo, anio=2026, numero=1000)
    db.session.commit()
    escribir(scans_dir, 2026, '1000.jpg')
    with app.test_request_context():
        reporte = validar_carpeta(1)
    assert folio.escaneado is True
    assert reporte['marcados'] == 1
    assert reporte['desmarcados'] == 0
    log = AuditLog.query.filter_by(
        tabla='folios', registro_id=folio.id).one()
    assert log.datos_anteriores == {'escaneado': False}
    assert log.datos_nuevos == {'escaneado': True}


def test_validar_desmarca_si_carpeta_del_anio_existe_vacia(app, tipo, scans_dir):
    folio = make_folio(tipo, anio=2026, numero=1000, escaneado=True)
    db.session.commit()
    (scans_dir / '2026').mkdir(parents=True)  # carpeta existe, sin archivos
    with app.test_request_context():
        reporte = validar_carpeta(1)
    assert folio.escaneado is False, 'carpeta existente sin archivo ⇒ desmarcar'
    assert reporte['desmarcados'] == 1
    log = AuditLog.query.filter_by(
        tabla='folios', registro_id=folio.id).one()
    assert log.datos_anteriores == {'escaneado': True}
    assert log.datos_nuevos == {'escaneado': False}


def test_validar_no_desmarca_si_falta_carpeta_de_anio(app, tipo, scans_dir):
    # Raíz existe pero sin subcarpeta 2026: volumen a medio montar no debe
    # borrar los marcados de ese año.
    folio = make_folio(tipo, anio=2026, numero=1000, escaneado=True)
    db.session.commit()
    scans_dir.mkdir(parents=True)
    with app.test_request_context():
        reporte = validar_carpeta(1)
    assert folio.escaneado is True
    assert reporte['desmarcados'] == 0
    assert reporte['anios_sin_carpeta'] == [2026]


def test_validar_sin_carpeta_raiz_no_toca_nada(app, tipo, scans_dir):
    folio = make_folio(tipo, anio=2026, numero=1000, escaneado=True)
    db.session.commit()
    assert not scans_dir.exists()
    with app.test_request_context():
        reporte = validar_carpeta(1)
    assert reporte['error_raiz'] is True
    assert folio.escaneado is True, 'sin carpeta raíz no se desmarca nada'
    assert reporte['marcados'] == 0
    assert reporte['desmarcados'] == 0
    assert AuditLog.query.count() == 0


def test_validar_ignora_archivos_invalidos_y_de_la_raiz(app, tipo, scans_dir):
    folio = make_folio(tipo, anio=2026, numero=1000)
    db.session.commit()
    escribir(scans_dir, 2026, '1000.jpg')
    escribir(scans_dir, 2026, 'copia 2026.jpg')   # nombre inválido
    (scans_dir / 'suelto.jpg').write_bytes(b'X')   # suelto en la raíz
    with app.test_request_context():
        reporte = validar_carpeta(1)
    assert folio.escaneado is True, 'el inválido no aborta la validación'
    assert reporte['archivos'] == 1
    assert reporte['ignorados'] == 2


def test_validar_idempotente_audita_solo_cambio(app, tipo, scans_dir):
    folio = make_folio(tipo, anio=2026, numero=1000)
    db.session.commit()
    escribir(scans_dir, 2026, '1000.jpg')
    with app.test_request_context():
        validar_carpeta(1)
        validar_carpeta(1)
    logs = AuditLog.query.filter_by(tabla='folios', registro_id=folio.id)
    assert logs.count() == 1, 're-validar no debe duplicar el log'


# --- botón / endpoint en el módulo de folios ---


def test_validar_endpoint_requiere_login(client):
    assert client.post('/folios/validar-escaneados').status_code == 302


def test_validar_endpoint_sin_permiso_redirige(client):
    make_user('lector', 'lectura')
    client.post('/auth/login',
                data={'username': 'lector', 'password': 'pass12345'})
    resp = client.post('/folios/validar-escaneados', follow_redirects=True)
    assert resp.status_code == 200
    assert 'No tiene permisos' in resp.get_data(as_text=True)


def test_validar_endpoint_marca_y_flash(admin_client, folio, scans_dir):
    escribir(scans_dir, 2026, '1000.jpg')
    resp = admin_client.post('/folios/validar-escaneados',
                            follow_redirects=True)
    assert resp.status_code == 200
    assert folio.escaneado is True
    text = resp.get_data(as_text=True)
    assert 'Validación completada' in text
    assert '1 folio marcado' in text


def test_validar_endpoint_sin_carpeta_flash_error(admin_client, folio, scans_dir):
    folio.escaneado = True
    db.session.commit()
    resp = admin_client.post('/folios/validar-escaneados',
                            follow_redirects=True)
    assert resp.status_code == 200
    assert 'No existe la carpeta de escaneados' in resp.get_data(as_text=True)
    assert folio.escaneado is True


# Nota: un solo usuario por test. El fixture `app` mantiene un app context
# activo y Flask lo reusa en cada request ⇒ `g._login_user` (caché de
# Flask-Login) se comparte entre clients del mismo test: un segundo login
# vería al usuario anterior. Con un solo client por test, `g` nace limpio.
def test_boton_visible_para_admin(admin_client):
    text = admin_client.get('/folios/').get_data(as_text=True)
    assert 'Validar Escaneados' in text


def test_boton_oculto_para_operador(auth_client):
    text = auth_client.get('/folios/').get_data(as_text=True)
    assert 'Validar Escaneados' not in text, \
        'operador no debe ver el botón (ya no tiene escaneos.subir)'


def test_boton_oculto_para_lectura(client):
    make_user('lector', 'lectura')
    client.post('/auth/login',
                data={'username': 'lector', 'password': 'pass12345'})
    text = client.get('/folios/').get_data(as_text=True)
    assert 'Validar Escaneados' not in text, \
        'lectura no debe ver el botón (no tiene escaneos.subir)'


def post_subir(client, anio, archivos, tipo=TIPO):
    """archivos: lista de (nombre, contenido_bytes)."""
    data = {
        'anio': anio,
        'tipo': tipo,
        'archivos': [(BytesIO(SOI + contenido), nombre)
                     for nombre, contenido in archivos],
    }
    return client.post('/escaneos/subir', data=data,
                       content_type='multipart/form-data')


def test_subir_requiere_login(client):
    assert client.get('/escaneos/subir').status_code == 302


def test_subir_sin_permiso_redirige(client):
    from tests.conftest import make_user
    make_user('lector', 'lectura')
    client.post('/auth/login', data={'username': 'lector', 'password': 'pass12345'})
    resp = client.get('/escaneos/subir', follow_redirects=True)
    assert resp.status_code == 200
    assert 'No tiene permisos' in resp.get_data(as_text=True)


def test_subir_muestra_form(admin_client):
    resp = admin_client.get('/escaneos/subir')
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert 'Subir Escaneos' in text
    assert 'multiple' in text  # input multi-archivo


def test_subir_marca_folio(admin_client, folio, scans_dir):
    resp = post_subir(admin_client, folio.anioCert, [('1000.jpg', b'IMG')])
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert 'Marcado' in text
    assert folio.escaneado is True
    assert (scans_dir / '2026' / str(TIPO) / '1000.jpg').exists()


def test_subir_sin_anio_no_escribe(admin_client, folio, scans_dir):
    resp = post_subir(admin_client, '', [('1000.jpg', b'IMG')])
    assert 'Seleccione un año' in resp.get_data(as_text=True)
    assert folio.escaneado is False
    assert not scans_dir.exists()


def test_subir_anio_inexistente_no_escribe(admin_client, folio, scans_dir):
    resp = post_subir(admin_client, 1999, [('1000.jpg', b'IMG')])
    assert 'Not a valid choice' in resp.get_data(as_text=True)
    assert folio.escaneado is False
    assert not scans_dir.exists()


def test_subir_archivo_repetido_en_lote(admin_client, folio, scans_dir):
    # Dos archivos con el mismo número en un mismo request: gana el último
    # (sobrescritura) y el folio queda marcado igual.
    resp = post_subir(admin_client, 2026,
                      [('1000.jpg', b'UNO'), ('1000.jpg', b'DOS')])
    assert resp.status_code == 200
    assert folio.escaneado is True
    assert (scans_dir / '2026' / str(TIPO) / '1000.jpg').read_bytes() == SOI + b'DOS'


def test_subir_lote_mixto(admin_client, folio, scans_dir):
    resp = post_subir(admin_client, 2026, [
        ('1000.jpg', b'OK'),      # match → marcado
        ('nada.jpg', b'X'),       # nombre inválido → no se escribe
        ('9999.jpg', b'Y'),       # sin folio → guardado, sin coincidencia
    ])
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert folio.escaneado is True, 'un inválido no aborta el lote'
    assert (scans_dir / '2026' / str(TIPO) / '9999.jpg').exists()
    assert not (scans_dir / '2026' / str(TIPO) / 'nada.jpg').exists()
    assert 'Nombre inválido' in text
    assert 'Sin coincidencia' in text


def test_subir_lote_mixto_con_png(admin_client, folio, scans_dir):
    # Un .png en el lote no debe rechazar el request completo: el JPG válido
    # se guarda y el folio se marca; el .png se reporta como nombre inválido
    # sin escribir nada en disco.
    resp = post_subir(admin_client, 2026, [
        ('escaneo.png', b'PNGDATA'),  # extensión no permitida → inválido
        ('1000.jpg', b'OK'),          # match → marcado
    ])
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert folio.escaneado is True, 'un no-JPG no aborta el lote'
    assert (scans_dir / '2026' / str(TIPO) / '1000.jpg').read_bytes() == SOI + b'OK'
    assert not (scans_dir / '2026' / str(TIPO) / 'escaneo.png').exists()
    assert not (scans_dir / '2026' / str(TIPO) / 'escaneo.jpg').exists()
    assert 'Nombre inválido' in text


def test_contenido_no_jpeg_rechazado_y_no_se_escribe(app, tipo, scans_dir):
    folio = make_folio(tipo, anio=2026, numero=1000)
    db.session.commit()
    with app.test_request_context():
        reporte = guardar_y_matchear(
            [jpg('1000.jpg', b'\x89PNG\r\n', crudo=True)], 2026, TIPO, 1)
    assert reporte['invalidos'] == 1
    assert reporte['resultados'][0]['estado'] == 'contenido_invalido'
    assert not (scans_dir / '2026' / str(TIPO) / '1000.jpg').exists()
    assert db.session.get(Folio, folio.id).escaneado is False


def test_reemplazo_se_reporta(app, tipo, scans_dir):
    make_folio(tipo, anio=2026, numero=1000)
    db.session.commit()
    with app.test_request_context():
        primero = guardar_y_matchear([jpg('1000.jpg', b'UNO')], 2026, TIPO, 1)
        segundo = guardar_y_matchear([jpg('1000.jpg', b'DOS')], 2026, TIPO, 1)
    assert primero['reemplazados'] == 0
    assert primero['resultados'][0]['reemplazado'] is False
    assert segundo['reemplazados'] == 1
    assert segundo['resultados'][0]['reemplazado'] is True


# --- layout <anio>/<tipo_id>/<n>.jpg y compatibilidad con el anterior ---


def escribir_exacto(scans_dir, anio, tipo_id, nombre):
    carpeta = scans_dir / str(anio) / str(tipo_id)
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / nombre).write_bytes(SOI + b'IMG')


def _dos_tipos(tipo):
    from app.models.tipo_certificado import TipoCertificado
    otro = TipoCertificado(name='Nacimientos', color='#198754', activo=True)
    db.session.add(otro)
    db.session.flush()
    f1 = make_folio(tipo, anio=2026, numero=1000, rangoId=1)
    f2 = make_folio(otro, anio=2026, numero=1000, rangoId=2)
    db.session.commit()
    return otro, f1, f2


def test_validar_layout_por_tipo_marca_solo_ese_tipo(app, tipo, scans_dir):
    otro, f1, f2 = _dos_tipos(tipo)
    escribir_exacto(scans_dir, 2026, otro.id, '1000.jpg')
    with app.test_request_context():
        reporte = validar_carpeta(1)
    assert f2.escaneado is True
    assert f1.escaneado is False
    assert reporte['marcados'] == 1
    assert reporte['archivos'] == 1


def test_validar_desmarca_tipo_sin_archivo(app, tipo, scans_dir):
    otro, f1, f2 = _dos_tipos(tipo)
    f1.escaneado = True
    db.session.commit()
    escribir_exacto(scans_dir, 2026, otro.id, '1000.jpg')
    with app.test_request_context():
        reporte = validar_carpeta(1)
    assert f1.escaneado is False, 'el archivo es del otro tipo'
    assert f2.escaneado is True
    assert reporte['desmarcados'] == 1


def test_validar_legado_ambiguo_no_marca_ni_desmarca(app, tipo, scans_dir):
    otro, f1, f2 = _dos_tipos(tipo)
    f1.escaneado = True  # marcado por el comportamiento anterior
    db.session.commit()
    escribir(scans_dir, 2026, '1000.jpg')  # layout anterior, 2 candidatos
    with app.test_request_context():
        reporte = validar_carpeta(1)
    assert f1.escaneado is True, 'ambiguo: no se desmarca'
    assert f2.escaneado is False, 'ambiguo: no se marca'
    assert reporte['ambiguos'] == 1
    assert reporte['legados'] == 1
    assert AuditLog.query.count() == 0


def test_validar_endpoint_avisa_ambiguos(admin_client, tipo, scans_dir):
    _dos_tipos(tipo)
    escribir(scans_dir, 2026, '1000.jpg')
    text = admin_client.post('/folios/validar-escaneados',
                             follow_redirects=True).get_data(as_text=True)
    assert 'coinciden con varios tipos' in text
    assert 'migrar_escaneos.py' in text


def test_migrar_legados_simula_y_aplica(app, tipo, scans_dir):
    from app.services.escaneos import migrar_legados
    otro, _, _ = _dos_tipos(tipo)
    unico = make_folio(tipo, anio=2026, numero=2000, rangoId=3)
    db.session.commit()
    escribir(scans_dir, 2026, '1000.jpg')   # ambiguo
    escribir(scans_dir, 2026, '2000.jpg')   # único → se mueve
    escribir(scans_dir, 2026, '3000.jpg')   # sin folio
    with app.test_request_context():
        simulado = migrar_legados()
        assert (scans_dir / '2026' / '2000.jpg').exists(), 'simular no mueve'
        aplicado = migrar_legados(aplicar=True)
    for rep in (simulado, aplicado):
        assert [o.name for o, _ in rep['movidos']] == ['2000.jpg']
        assert [p.name for p in rep['ambiguos']] == ['1000.jpg']
        assert [p.name for p in rep['sin_folio']] == ['3000.jpg']
    assert not (scans_dir / '2026' / '2000.jpg').exists()
    assert (scans_dir / '2026' / str(unico.tipoCert_id) / '2000.jpg').exists()
    assert (scans_dir / '2026' / '1000.jpg').exists(), 'ambiguo queda en su lugar'


def test_migrar_legados_no_sobrescribe(app, tipo, scans_dir):
    from app.services.escaneos import migrar_legados
    make_folio(tipo, anio=2026, numero=2000)
    db.session.commit()
    escribir(scans_dir, 2026, '2000.jpg')
    escribir_exacto(scans_dir, 2026, tipo.id, '2000.jpg')
    with app.test_request_context():
        rep = migrar_legados(aplicar=True)
    assert rep['movidos'] == []
    assert [p.name for p in rep['conflictos']] == ['2000.jpg']
    assert (scans_dir / '2026' / '2000.jpg').exists()


def test_subir_sin_tipo_no_escribe(admin_client, folio, scans_dir):
    resp = post_subir(admin_client, 2026, [('1000.jpg', b'IMG')], tipo='')
    assert 'Seleccione un tipo de certificado' in resp.get_data(as_text=True)
    assert folio.escaneado is False
    assert not scans_dir.exists()


def test_subir_muestra_carpeta_por_tipo(admin_client, tipo):
    text = admin_client.get('/escaneos/subir').get_data(as_text=True)
    assert f'&lt;año&gt;/{tipo.id}/</code> — {tipo.name}' in text


def test_script_migrar_escaneos_simula_por_defecto(app, tipo, scans_dir,
                                                   monkeypatch, capsys):
    import migrar_escaneos
    make_folio(tipo, anio=2026, numero=2000)
    db.session.commit()
    escribir(scans_dir, 2026, '2000.jpg')
    monkeypatch.setattr(migrar_escaneos, 'create_app', lambda: app)
    assert migrar_escaneos.main([]) == 0
    salida = capsys.readouterr().out
    assert 'Se moverían: 1' in salida
    assert '--aplicar' in salida
    assert (scans_dir / '2026' / '2000.jpg').exists()
    assert migrar_escaneos.main(['--aplicar']) == 0
    assert 'Movidos: 1' in capsys.readouterr().out
    assert (scans_dir / '2026' / str(tipo.id) / '2000.jpg').exists()
