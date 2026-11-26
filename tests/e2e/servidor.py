"""Servidor para las pruebas E2E: la app sobre una SQLite sembrada.

Uso (lo lanza tests/e2e/conftest.py): python -m tests.e2e.servidor <puerto> <directorio>
Crea <directorio>/e2e.db y <directorio>/scans; nunca toca la base configurada en .env.
"""
import os
import sys
from datetime import date, timedelta

CLAVE = 'Clave-E2E-2026'


def configurar_entorno(directorio):
    os.environ.update(
        SECRET_KEY='e2e-' + 'x' * 40,
        DATABASE_URL='sqlite:///' + os.path.join(directorio, 'e2e.db'),
        RATELIMIT_STORAGE_URI='memory://',
        RATELIMIT_DEFAULT='100000 per hour',
        SCANS_FOLDER=os.path.join(directorio, 'scans'),
        FLASK_CONFIG='production',
    )


def sembrar(db):
    """Datos fijos que el recorrido da por supuestos (ver test_recorrido.py)."""
    from app.models import (Usuario, Centro, TipoCertificado, Folio, EntregaFolio,
                            DevolucionFolio, RecepcionFolio)

    admin = Usuario(name='Admin E2E', username='admin', email='a@e2e.local', rol='admin', activo=True)
    admin.set_password(CLAVE)
    op = Usuario(name='Operador E2E', username='operador', email='o@e2e.local', rol='operador', activo=True)
    op.set_password(CLAVE)
    tipos = [TipoCertificado(name=n, color=c, activo=True) for n, c in
             (('Defunciones', '#1E40AF'), ('Nacimientos Nacionales', '#198754'))]
    centros = [Centro(name=n, activo=True) for n in ('Hospital Central', 'CPN Norte', 'Clínica Sur')]
    db.session.add_all([admin, op] + tipos + centros)
    db.session.flush()

    # 200 folios (1000–1199) por tipo
    for i, t in enumerate(tipos):
        db.session.add(RecepcionFolio(fecha=date(2026, 1, 10), anioCert=2026, tipoCert_id=t.id,
                                      folioInicial=1000, folioFinal=1199, rangoId=i + 1, userId=admin.id))
        for n in range(1000, 1200):
            db.session.add(Folio(rangoId=i + 1, anioCert=2026, tipoCert_id=t.id, folio=n, estado='disponible'))
    db.session.flush()

    # Defunciones 1000–1029 entregados al Hospital Central hace 150 días; 18 ya devueltos.
    # Quedan 12 pendientes en el centro → con objetivo manual 40 el sugerido es 28.
    hoy = date.today()
    folios = Folio.query.filter_by(tipoCert_id=tipos[0].id).order_by(Folio.folio).all()
    for k, f in enumerate(folios[:30]):
        f.estado = 'entregado'
        db.session.add(EntregaFolio(folio_id=f.id, fechaEntrega=hoy - timedelta(days=150),
                                    centroId=centros[0].id, userId=admin.id))
        if k < 18:
            f.estado = 'devuelto'
            db.session.add(DevolucionFolio(folio_id=f.id, fechaDevolucion=hoy - timedelta(days=10 + k * 5),
                                           centroId=centros[0].id, userId=admin.id))
    folios[40].nulo = True
    db.session.commit()


def main():
    puerto, directorio = int(sys.argv[1]), sys.argv[2]
    configurar_entorno(directorio)
    os.makedirs(os.environ['SCANS_FOLDER'], exist_ok=True)

    from app import create_app
    from app.config import Config
    from app.extensions import db

    app = create_app(Config)
    with app.app_context():
        db.drop_all()
        db.create_all()
        sembrar(db)
    print(f'servidor E2E listo en :{puerto}', flush=True)
    app.run(host='127.0.0.1', port=puerto, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
