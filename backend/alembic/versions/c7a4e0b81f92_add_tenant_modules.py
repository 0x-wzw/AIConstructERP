"""add tenant_modules (per-tenant module enablement)

Backs the module registry: one row per (tenant, module) overriding the module's
default_enabled. Absence of a row ⇒ default. Platform admins bypass gating.

Revision ID: c7a4e0b81f92
Revises: b3d9f1a26c47
Create Date: 2026-07-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7a4e0b81f92'
down_revision: Union[str, Sequence[str], None] = 'b3d9f1a26c47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'tenant_modules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('module_name', sa.String(length=50), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'module_name', name='uq_tenant_module'),
    )
    op.create_index(op.f('ix_tenant_modules_tenant_id'), 'tenant_modules',
                    ['tenant_id'], unique=False)
    op.create_index(op.f('ix_tenant_modules_module_name'), 'tenant_modules',
                    ['module_name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_tenant_modules_module_name'), table_name='tenant_modules')
    op.drop_index(op.f('ix_tenant_modules_tenant_id'), table_name='tenant_modules')
    op.drop_table('tenant_modules')
