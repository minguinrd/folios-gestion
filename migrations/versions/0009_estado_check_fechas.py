"""CHECK de folios.estado e índices de fecha en entregas/devoluciones

Revision ID: 0009_estado_check_fechas
Revises: 0008_transferencias
Create Date: 2026-11-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0009_estado_check_fechas'
down_revision = '0008_transferencias'
branch_labels = None
depends_on = None

ESTADOS = ('disponible', 'entregado', 'devuelto', 'perdido')


def upgrade():
    # Un estado fuera de catálogo haría fallar el ALTER con un error opaco de
    # MariaDB: se detecta antes y se explica qué corregir.
    bind = op.get_bind()
    invalidos = bind.execute(sa.text(
        "SELECT estado, COUNT(*) FROM folios "
        "WHERE estado IS NOT NULL AND estado NOT IN :estados GROUP BY estado"
    ).bindparams(sa.bindparam('estados', expanding=True)),
        {'estados': list(ESTADOS)}).fetchall()
    if invalidos:
        detalle = ', '.join(f'{e!r} ({n})' for e, n in invalidos)
        raise RuntimeError(
            'folios.estado tiene valores fuera de catálogo: ' + detalle
            + '. Corríjalos (UPDATE folios SET estado=...) y repita el upgrade.')

    with op.batch_alter_table('folios', schema=None) as batch_op:
        batch_op.create_check_constraint(
            'ck_folios_estado',
            "estado IN ('disponible', 'entregado', 'devuelto', 'perdido')")

    with op.batch_alter_table('entrega_folios', schema=None) as batch_op:
        batch_op.create_index('idx_entrega_fecha', ['fechaEntrega'], unique=False)

    with op.batch_alter_table('devolucion_folios', schema=None) as batch_op:
        batch_op.create_index('idx_devolucion_fecha', ['fechaDevolucion'], unique=False)


def downgrade():
    with op.batch_alter_table('devolucion_folios', schema=None) as batch_op:
        batch_op.drop_index('idx_devolucion_fecha')

    with op.batch_alter_table('entrega_folios', schema=None) as batch_op:
        batch_op.drop_index('idx_entrega_fecha')

    with op.batch_alter_table('folios', schema=None) as batch_op:
        batch_op.drop_constraint('ck_folios_estado', type_='check')
