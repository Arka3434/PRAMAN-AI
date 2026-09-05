"""Add Phase 3/4 MVP models for analysis, findings, and review.

Revision ID: 20260902_phase3_phase4_demo_mvp
Revises: 20260902_phase2_core_domain_models
Create Date: 2026-09-02 16:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260902_phase3_phase4_demo_mvp'
down_revision = '20260902_phase2_core_domain_models'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'analysis_results',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('inspection_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='completed'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('structured_declarations', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['inspection_id'], ['inspections.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_analysis_results_id'), 'analysis_results', ['id'], unique=False)
    op.create_index(op.f('ix_analysis_results_inspection_id'), 'analysis_results', ['inspection_id'], unique=False)
    op.create_index(op.f('ix_analysis_results_status'), 'analysis_results', ['status'], unique=False)

    op.create_table(
        'findings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('inspection_id', sa.String(length=36), nullable=False),
        sa.Column('severity', sa.String(length=32), nullable=False, server_default='warning'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='open'),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('detected_value', sa.String(length=500), nullable=True),
        sa.Column('rule_check_id', sa.String(length=64), nullable=False),
        sa.Column('evidence_reference', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['inspection_id'], ['inspections.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_findings_id'), 'findings', ['id'], unique=False)
    op.create_index(op.f('ix_findings_inspection_id'), 'findings', ['inspection_id'], unique=False)
    op.create_index(op.f('ix_findings_severity'), 'findings', ['severity'], unique=False)
    op.create_index(op.f('ix_findings_status'), 'findings', ['status'], unique=False)
    op.create_index(op.f('ix_findings_rule_check_id'), 'findings', ['rule_check_id'], unique=False)

    op.create_table(
        'review_decisions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('inspection_id', sa.String(length=36), nullable=False),
        sa.Column('decision', sa.String(length=32), nullable=False),
        sa.Column('reviewer_name', sa.String(length=150), nullable=False, server_default='demo-inspector'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['inspection_id'], ['inspections.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_review_decisions_id'), 'review_decisions', ['id'], unique=False)
    op.create_index(op.f('ix_review_decisions_inspection_id'), 'review_decisions', ['inspection_id'], unique=False)
    op.create_index(op.f('ix_review_decisions_decision'), 'review_decisions', ['decision'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_review_decisions_decision'), table_name='review_decisions')
    op.drop_index(op.f('ix_review_decisions_inspection_id'), table_name='review_decisions')
    op.drop_index(op.f('ix_review_decisions_id'), table_name='review_decisions')
    op.drop_table('review_decisions')

    op.drop_index(op.f('ix_findings_rule_check_id'), table_name='findings')
    op.drop_index(op.f('ix_findings_status'), table_name='findings')
    op.drop_index(op.f('ix_findings_severity'), table_name='findings')
    op.drop_index(op.f('ix_findings_inspection_id'), table_name='findings')
    op.drop_index(op.f('ix_findings_id'), table_name='findings')
    op.drop_table('findings')

    op.drop_index(op.f('ix_analysis_results_status'), table_name='analysis_results')
    op.drop_index(op.f('ix_analysis_results_inspection_id'), table_name='analysis_results')
    op.drop_index(op.f('ix_analysis_results_id'), table_name='analysis_results')
    op.drop_table('analysis_results')
