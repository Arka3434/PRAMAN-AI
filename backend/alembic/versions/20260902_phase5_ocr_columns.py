"""Add OCR metadata fields to analysis results.

Revision ID: 20260902_phase5_ocr_columns
Revises: 20260902_phase3_phase4_demo_mvp
Create Date: 2026-09-02 17:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260902_phase5_ocr_columns'
down_revision = '20260902_phase3_phase4_demo_mvp'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('analysis_results') as batch_op:
        batch_op.add_column(sa.Column('ocr_text', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('ocr_confidence', sa.Float(), nullable=True, server_default='0.0'))
        batch_op.add_column(sa.Column('ocr_regions', sa.JSON(), nullable=True, server_default='[]'))
        batch_op.add_column(sa.Column('extraction_metadata', sa.JSON(), nullable=True, server_default='{}'))


def downgrade() -> None:
    with op.batch_alter_table('analysis_results') as batch_op:
        batch_op.drop_column('extraction_metadata')
        batch_op.drop_column('ocr_regions')
        batch_op.drop_column('ocr_confidence')
        batch_op.drop_column('ocr_text')
