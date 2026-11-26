"""nombre de quien recibe la entrega

Revision ID: 0012_entrega_recibido_por
Revises: 0011_marca_institucion
Create Date: 2026-11-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0012_entrega_recibido_por'
down_revision = '0011_marca_institucion'
branch_labels = None
depends_on = None


def upgrade():
    # Nullable: las entregas existentes (y las importadas desde Excel) no
    # tienen el dato; el formulario de nueva entrega lo exige.
    with op.batch_alter_table('entrega_folios', schema=None) as batch_op:
        batch_op.add_column(sa.Column('recibidoPor', sa.String(length=120), nullable=True))


def downgrade():
    with op.batch_alter_table('entrega_folios', schema=None) as batch_op:
        batch_op.drop_column('recibidoPor')
