"""Add statutory notices table for Phase 13 enforcement document drafting.

Revision ID: 20260904_phase13_statutory_notices
Revises: 20260902_phase5_capture_fields
Create Date: 2026-09-04 18:50:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260904_phase13_statutory_notices'
down_revision = '20260902_phase5_capture_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'notices',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('inspection_id', sa.String(length=36), sa.ForeignKey('inspections.id'), nullable=False),
        sa.Column('notice_reference', sa.String(length=64), unique=True, nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='DRAFT'),
        sa.Column('recipient_role', sa.String(length=64), nullable=False, server_default='unknown_pending_verification'),
        sa.Column('recipient_name', sa.String(length=255), nullable=False),
        sa.Column('recipient_address', sa.Text(), nullable=False),
        sa.Column('establishment_name', sa.String(length=255), nullable=True),
        sa.Column('inspection_venue', sa.String(length=255), nullable=True),
        sa.Column('statutory_charges', sa.JSON(), nullable=False),
        sa.Column('legal_version_context', sa.JSON(), nullable=False),
        sa.Column('evidence_references', sa.JSON(), nullable=False),
        sa.Column('inspection_snapshot', sa.JSON(), nullable=False),
        sa.Column('response_period_days', sa.Integer(), nullable=True, server_default='15'),
        sa.Column('response_period_basis', sa.String(length=255), nullable=True),
        sa.Column('compounding_eligible', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('compounding_clause_included', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('officer_name', sa.String(length=128), nullable=True),
        sa.Column('officer_designation', sa.String(length=128), nullable=True),
        sa.Column('officer_office', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_immutable', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    with op.batch_alter_table('notices') as batch_op:
        batch_op.create_index(batch_op.f('ix_notices_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_notices_inspection_id'), ['inspection_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_notices_notice_reference'), ['notice_reference'], unique=True)
        batch_op.create_index(batch_op.f('ix_notices_status'), ['status'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('notices') as batch_op:
        batch_op.drop_index(batch_op.f('ix_notices_status'))
        batch_op.drop_index(batch_op.f('ix_notices_notice_reference'))
        batch_op.drop_index(batch_op.f('ix_notices_inspection_id'))
        batch_op.drop_index(batch_op.f('ix_notices_id'))
    op.drop_table('notices')
