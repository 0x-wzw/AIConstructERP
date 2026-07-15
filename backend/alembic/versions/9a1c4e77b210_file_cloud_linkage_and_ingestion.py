"""strengthen file storage cloud linkage + ingestion fields

Adds to file_uploads: storage_bucket, checksum_sha256, and the ingestion
columns (ingest_status, extracted_data, ingested_entity_type/id, ingested_at)
that link a stored file to the structured domain record produced from it.

Revision ID: 9a1c4e77b210
Revises: 758b615dcf53
Create Date: 2026-07-16 06:40:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9a1c4e77b210'
down_revision: Union[str, Sequence[str], None] = '758b615dcf53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('file_uploads') as batch:
        batch.add_column(sa.Column('storage_bucket', sa.String(length=200),
                                   nullable=False, server_default=''))
        batch.add_column(sa.Column('checksum_sha256', sa.String(length=64),
                                   nullable=False, server_default=''))
        batch.add_column(sa.Column('ingest_status', sa.String(length=20),
                                   nullable=False, server_default='pending'))
        batch.add_column(sa.Column('extracted_data', sa.Text(),
                                   nullable=False, server_default=''))
        batch.add_column(sa.Column('ingested_entity_type', sa.String(length=50),
                                   nullable=False, server_default=''))
        batch.add_column(sa.Column('ingested_entity_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('ingested_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_file_uploads_checksum_sha256'), 'file_uploads',
                    ['checksum_sha256'], unique=False)
    op.create_index(op.f('ix_file_uploads_ingest_status'), 'file_uploads',
                    ['ingest_status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_file_uploads_ingest_status'), table_name='file_uploads')
    op.drop_index(op.f('ix_file_uploads_checksum_sha256'), table_name='file_uploads')
    with op.batch_alter_table('file_uploads') as batch:
        batch.drop_column('ingested_at')
        batch.drop_column('ingested_entity_id')
        batch.drop_column('ingested_entity_type')
        batch.drop_column('extracted_data')
        batch.drop_column('ingest_status')
        batch.drop_column('checksum_sha256')
        batch.drop_column('storage_bucket')
