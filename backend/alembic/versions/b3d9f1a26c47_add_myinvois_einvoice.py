"""add MyInvois (LHDN) e-invoice fields, lines, and per-tenant config

Extends e_invoices with the Malaysia LHDN MyInvois clearance fields, adds a
per-line e_invoice_lines table (MyInvois validates per line), and a
per-tenant myinvois_config table holding issuer identity + API credentials
(client secret stored encrypted).

Revision ID: b3d9f1a26c47
Revises: a2f7c9d4e810
Create Date: 2026-07-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b3d9f1a26c47'
down_revision: Union[str, Sequence[str], None] = 'a2f7c9d4e810'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_EINVOICE_COLUMNS = [
    ('document_type', sa.String(length=2), '01'),
    ('document_version', sa.String(length=5), '1.1'),
    ('currency', sa.String(length=3), 'MYR'),
    ('exchange_rate', sa.Numeric(14, 6), '1'),
    ('supplier_tin', sa.String(length=20), ''),
    ('supplier_reg_no', sa.String(length=30), ''),
    ('supplier_sst', sa.String(length=35), ''),
    ('supplier_msic', sa.String(length=5), ''),
    ('buyer_tin', sa.String(length=20), ''),
    ('buyer_reg_no', sa.String(length=30), ''),
    ('buyer_name', sa.String(length=200), ''),
    ('myinvois_status', sa.String(length=20), 'not_submitted'),
    ('myinvois_uuid', sa.String(length=40), ''),
    ('myinvois_long_id', sa.String(length=80), ''),
    ('submission_uid', sa.String(length=40), ''),
    ('validation_link', sa.String(length=500), ''),
    ('myinvois_error', sa.Text(), ''),
    ('cancel_reason', sa.String(length=300), ''),
]


def upgrade() -> None:
    """Upgrade schema."""
    for name, coltype, default in _EINVOICE_COLUMNS:
        op.add_column('e_invoices', sa.Column(
            name, coltype, nullable=False, server_default=default))
    op.add_column('e_invoices', sa.Column('submitted_at', sa.DateTime(), nullable=True))
    op.add_column('e_invoices', sa.Column('validated_at', sa.DateTime(), nullable=True))
    op.add_column('e_invoices', sa.Column('cancelled_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_e_invoices_myinvois_status'), 'e_invoices',
                    ['myinvois_status'], unique=False)
    op.create_index(op.f('ix_e_invoices_myinvois_uuid'), 'e_invoices',
                    ['myinvois_uuid'], unique=False)

    op.create_table(
        'e_invoice_lines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('e_invoice_id', sa.Integer(), nullable=False),
        sa.Column('line_no', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('classification_code', sa.String(length=5), nullable=False, server_default=''),
        sa.Column('description', sa.String(length=300), nullable=False, server_default=''),
        sa.Column('quantity', sa.Numeric(14, 3), nullable=False, server_default='1'),
        sa.Column('unit_price', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('measurement', sa.String(length=10), nullable=False, server_default=''),
        sa.Column('tax_type', sa.String(length=10), nullable=False, server_default=''),
        sa.Column('tax_rate', sa.Numeric(6, 2), nullable=False, server_default='0'),
        sa.Column('tax_amount', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('discount', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('subtotal', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['e_invoice_id'], ['e_invoices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_e_invoice_lines_tenant_id'), 'e_invoice_lines',
                    ['tenant_id'], unique=False)
    op.create_index(op.f('ix_e_invoice_lines_e_invoice_id'), 'e_invoice_lines',
                    ['e_invoice_id'], unique=False)

    op.create_table(
        'myinvois_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('environment', sa.String(length=12), nullable=False, server_default='sandbox'),
        sa.Column('tin', sa.String(length=20), nullable=False, server_default=''),
        sa.Column('registration_no', sa.String(length=30), nullable=False, server_default=''),
        sa.Column('sst_no', sa.String(length=35), nullable=False, server_default=''),
        sa.Column('msic_code', sa.String(length=5), nullable=False, server_default=''),
        sa.Column('business_activity', sa.String(length=300), nullable=False, server_default=''),
        sa.Column('email', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('address_line', sa.String(length=300), nullable=False, server_default=''),
        sa.Column('city', sa.String(length=100), nullable=False, server_default=''),
        sa.Column('state_code', sa.String(length=3), nullable=False, server_default=''),
        sa.Column('postal_code', sa.String(length=10), nullable=False, server_default=''),
        sa.Column('country_code', sa.String(length=3), nullable=False, server_default='MYS'),
        sa.Column('client_id', sa.String(length=100), nullable=False, server_default=''),
        sa.Column('client_secret_enc', sa.Text(), nullable=False, server_default=''),
        sa.Column('is_intermediary', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('onbehalf_tin', sa.String(length=20), nullable=False, server_default=''),
        sa.Column('cert_ref', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', name='uq_myinvois_config_tenant'),
    )
    op.create_index(op.f('ix_myinvois_config_tenant_id'), 'myinvois_config',
                    ['tenant_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_myinvois_config_tenant_id'), table_name='myinvois_config')
    op.drop_table('myinvois_config')
    op.drop_index(op.f('ix_e_invoice_lines_e_invoice_id'), table_name='e_invoice_lines')
    op.drop_index(op.f('ix_e_invoice_lines_tenant_id'), table_name='e_invoice_lines')
    op.drop_table('e_invoice_lines')
    op.drop_index(op.f('ix_e_invoices_myinvois_uuid'), table_name='e_invoices')
    op.drop_index(op.f('ix_e_invoices_myinvois_status'), table_name='e_invoices')
    for name in ('cancelled_at', 'validated_at', 'submitted_at'):
        op.drop_column('e_invoices', name)
    for name, _type, _default in reversed(_EINVOICE_COLUMNS):
        op.drop_column('e_invoices', name)
