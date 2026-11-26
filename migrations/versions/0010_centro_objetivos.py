"""existencia objetivo manual por centro y tipo (cantidad sugerida)

Revision ID: 0010_centro_objetivos
Revises: 0009_estado_check_fechas
Create Date: 2026-11-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0010_centro_objetivos'
down_revision = '0009_estado_check_fechas'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'centro_objetivos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('centroId', sa.Integer(), nullable=False),
        sa.Column('tipoCert_id', sa.Integer(), nullable=False),
        sa.Column('cantidad', sa.Integer(), nullable=False),
        sa.Column('userId', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint('cantidad >= 0', name='ck_centro_objetivos_cantidad'),
        sa.ForeignKeyConstraint(['centroId'], ['centros.id'], ),
        sa.ForeignKeyConstraint(['tipoCert_id'], ['tipo_certificados.id'], ),
        sa.ForeignKeyConstraint(['userId'], ['usuarios.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('centroId', 'tipoCert_id',
                            name='uq_centro_objetivos_centro_tipo'),
    )
    op.create_index('idx_centro_objetivos_tipo', 'centro_objetivos',
                    ['tipoCert_id'], unique=False)
    op.create_index('idx_centro_objetivos_userId', 'centro_objetivos',
                    ['userId'], unique=False)


def downgrade():
    op.drop_index('idx_centro_objetivos_userId', table_name='centro_objetivos')
    op.drop_index('idx_centro_objetivos_tipo', table_name='centro_objetivos')
    op.drop_table('centro_objetivos')
