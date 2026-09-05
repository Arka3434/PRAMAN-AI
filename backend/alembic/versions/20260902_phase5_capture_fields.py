"""Add capture metadata fields to inspections.

Revision ID: 20260902_phase5_capture_fields
Revises: 20260902_phase5_ocr_columns
Create Date: 2026-09-02 18:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260902_phase5_capture_fields'
down_revision = '20260902_phase5_ocr_columns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('inspections') as batch_op:
        batch_op.add_column(sa.Column('barcode_or_qr', sa.String(length=200), nullable=True))
        batch_op.create_index(batch_op.f('ix_inspections_barcode_or_qr'), ['barcode_or_qr'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('inspections') as batch_op:
        batch_op.drop_index(batch_op.f('ix_inspections_barcode_or_qr'))
        batch_op.drop_column('barcode_or_qr')
