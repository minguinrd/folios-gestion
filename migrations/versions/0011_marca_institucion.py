"""institución y departamento configurables en la marca

Revision ID: 0011_marca_institucion
Revises: 0010_centro_objetivos
Create Date: 2026-11-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0011_marca_institucion'
down_revision = '0010_centro_objetivos'
branch_labels = None
depends_on = None


def upgrade():
    # NULL = texto por defecto (app/models/marca.py): la fila existente no
    # cambia lo que muestra hasta que un admin lo edite.
    with op.batch_alter_table('marca_config', schema=None) as batch_op:
        batch_op.add_column(sa.Column('institucion', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('departamento', sa.String(length=120), nullable=True))


def downgrade():
    with op.batch_alter_table('marca_config', schema=None) as batch_op:
        batch_op.drop_column('departamento')
        batch_op.drop_column('institucion')
