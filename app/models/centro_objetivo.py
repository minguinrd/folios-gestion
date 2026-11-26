from app.extensions import db
from app.utils import utcnow


class CentroObjetivo(db.Model):
    """Existencia objetivo manual de un tipo de certificado en un centro.

    Reemplaza al objetivo calculado desde el historial de devoluciones
    (app/services/sugeridos.py). Sin fila = cálculo automático. La cantidad
    es la existencia que el centro debería tener, no lo que hay que entregar:
    el sugerido descuenta los folios que el centro ya tiene pendientes.
    """
    __tablename__ = 'centro_objetivos'
    __table_args__ = (
        # Su columna líder (centroId) sirve también de índice para la FK.
        db.UniqueConstraint('centroId', 'tipoCert_id',
                            name='uq_centro_objetivos_centro_tipo'),
        db.Index('idx_centro_objetivos_tipo', 'tipoCert_id'),
        db.Index('idx_centro_objetivos_userId', 'userId'),
        db.CheckConstraint('cantidad >= 0', name='ck_centro_objetivos_cantidad'),
    )

    id = db.Column(db.Integer, primary_key=True)
    centroId = db.Column(db.Integer, db.ForeignKey('centros.id'), nullable=False)
    tipoCert_id = db.Column(db.Integer, db.ForeignKey('tipo_certificados.id'),
                            nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    userId = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            'centroId': self.centroId,
            'tipoCert_id': self.tipoCert_id,
            'cantidad': self.cantidad,
        }
