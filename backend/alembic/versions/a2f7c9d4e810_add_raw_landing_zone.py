"""add raw landing zone (raw_documents staging table)

Introduces the bronze tier: unstructured documents land here immutably before
ETL promotes them into the curated FileUpload + structured domain records.

Revision ID: a2f7c9d4e810
Revises: 9a1c4e77b210
Create Date: 2026-07-22 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a2f7c9d4e810'
down_revision: Union[str, Sequence[str], None] = '9a1c4e77b210'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'raw_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='upload'),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=False, server_default=''),
        sa.Column('size_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('storage_backend', sa.String(length=20), nullable=False, server_default='local'),
        sa.Column('storage_bucket', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('storage_path', sa.String(length=500), nullable=False),
        sa.Column('checksum_sha256', sa.String(length=64), nullable=False, server_default=''),
        sa.Column('category', sa.String(length=50), nullable=False, server_default=''),
        sa.Column('etl_status', sa.String(length=20), nullable=False, server_default='landed'),
        sa.Column('etl_error', sa.Text(), nullable=False, server_default=''),
        sa.Column('raw_text', sa.Text(), nullable=False, server_default=''),
        sa.Column('file_upload_id', sa.Integer(), nullable=True),
        sa.Column('received_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['file_upload_id'], ['file_uploads.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_raw_documents_tenant_id'), 'raw_documents',
                    ['tenant_id'], unique=False)
    op.create_index(op.f('ix_raw_documents_checksum_sha256'), 'raw_documents',
                    ['checksum_sha256'], unique=False)
    op.create_index(op.f('ix_raw_documents_etl_status'), 'raw_documents',
                    ['etl_status'], unique=False)
    op.create_index(op.f('ix_raw_documents_file_upload_id'), 'raw_documents',
                    ['file_upload_id'], unique=False)
    op.create_index(op.f('ix_raw_documents_is_archived'), 'raw_documents',
                    ['is_archived'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_raw_documents_is_archived'), table_name='raw_documents')
    op.drop_index(op.f('ix_raw_documents_file_upload_id'), table_name='raw_documents')
    op.drop_index(op.f('ix_raw_documents_etl_status'), table_name='raw_documents')
    op.drop_index(op.f('ix_raw_documents_checksum_sha256'), table_name='raw_documents')
    op.drop_index(op.f('ix_raw_documents_tenant_id'), table_name='raw_documents')
    op.drop_table('raw_documents')
