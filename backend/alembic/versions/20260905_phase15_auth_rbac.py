"""Add authentication, RBAC, and officer identity for Phase 15.

Revision ID: 20260905_phase15_auth_rbac
Revises: 20260904_phase13_statutory_notices
Create Date: 2026-09-05 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260905_phase15_auth_rbac'
down_revision = '20260904_phase13_statutory_notices'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1. Update users table with authentication & officer identity fields
    user_cols = {col['name'] for col in insp.get_columns('users')}
    with op.batch_alter_table('users') as batch_op:
        if 'hashed_password' not in user_cols:
            batch_op.add_column(
                sa.Column(
                    'hashed_password',
                    sa.String(length=255),
                    nullable=False,
                    server_default='!UNUSABLE_CREDENTIAL_PHASE15_INIT_REQUIRED',
                )
            )
        if 'designation' not in user_cols:
            batch_op.add_column(sa.Column('designation', sa.String(length=128), nullable=True))
        if 'jurisdiction_office' not in user_cols:
            batch_op.add_column(sa.Column('jurisdiction_office', sa.String(length=255), nullable=True))
        if 'badge_number' not in user_cols:
            batch_op.add_column(sa.Column('badge_number', sa.String(length=64), nullable=True))
        if 'last_login_at' not in user_cols:
            batch_op.add_column(sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
        if 'failed_login_attempts' not in user_cols:
            batch_op.add_column(
                sa.Column(
                    'failed_login_attempts',
                    sa.Integer(),
                    nullable=False,
                    server_default='0',
                )
            )
        if 'locked_until' not in user_cols:
            batch_op.add_column(sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))

    # Re-inspect to create indexes safely if missing
    existing_user_indexes = {ix['name'] for ix in insp.get_indexes('users')}
    with op.batch_alter_table('users') as batch_op:
        if 'ix_users_badge_number' not in existing_user_indexes:
            try:
                batch_op.create_index(batch_op.f('ix_users_badge_number'), ['badge_number'], unique=True)
            except Exception:
                pass
        if 'ix_users_role' not in existing_user_indexes:
            try:
                batch_op.create_index(batch_op.f('ix_users_role'), ['role'], unique=False)
            except Exception:
                pass

    # 2. Normalize existing plain-string roles to canonical enum uppercase values
    op.execute("UPDATE users SET role = 'LEGAL_METROLOGY_INSPECTOR' WHERE LOWER(role) = 'inspector'")
    op.execute("UPDATE users SET role = 'SUPERVISING_OFFICER' WHERE LOWER(role) IN ('supervisor', 'supervising_officer')")
    op.execute("UPDATE users SET role = 'ADMIN' WHERE LOWER(role) = 'admin'")
    op.execute("UPDATE users SET role = 'REVIEWER' WHERE LOWER(role) = 'reviewer'")

    # 3. Update notices table with issuing officer reference
    notice_cols = {col['name'] for col in insp.get_columns('notices')}
    if 'issuing_officer_id' not in notice_cols:
        with op.batch_alter_table('notices') as batch_op:
            batch_op.add_column(
                sa.Column(
                    'issuing_officer_id',
                    sa.String(length=36),
                    sa.ForeignKey('users.id', name='fk_notices_issuing_officer_id_users', ondelete='SET NULL'),
                    nullable=True,
                )
            )
            batch_op.create_index(batch_op.f('ix_notices_issuing_officer_id'), ['issuing_officer_id'], unique=False)

    # 4. Update review_decisions table with reviewer reference
    review_cols = {col['name'] for col in insp.get_columns('review_decisions')}
    if 'reviewer_id' not in review_cols:
        with op.batch_alter_table('review_decisions') as batch_op:
            batch_op.add_column(
                sa.Column(
                    'reviewer_id',
                    sa.String(length=36),
                    sa.ForeignKey('users.id', name='fk_review_decisions_reviewer_id_users', ondelete='SET NULL'),
                    nullable=True,
                )
            )
            batch_op.create_index(batch_op.f('ix_review_decisions_reviewer_id'), ['reviewer_id'], unique=False)

    # 5. Create audit_logs table
    tables = set(insp.get_table_names())
    if 'audit_logs' not in tables:
        op.create_table(
            'audit_logs',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
            sa.Column('user_id', sa.String(length=36), nullable=True),
            sa.Column('event_type', sa.String(length=64), nullable=False),
            sa.Column('resource_type', sa.String(length=64), nullable=False),
            sa.Column('resource_id', sa.String(length=64), nullable=True),
            sa.Column('ip_address', sa.String(length=45), nullable=True),
            sa.Column('details', sa.JSON(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        with op.batch_alter_table('audit_logs') as batch_op:
            batch_op.create_index(batch_op.f('ix_audit_logs_id'), ['id'], unique=False)
            batch_op.create_index(batch_op.f('ix_audit_logs_timestamp'), ['timestamp'], unique=False)
            batch_op.create_index(batch_op.f('ix_audit_logs_user_id'), ['user_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_audit_logs_event_type'), ['event_type'], unique=False)
            batch_op.create_index(batch_op.f('ix_audit_logs_resource_id'), ['resource_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    # 1. Drop audit_logs
    if 'audit_logs' in tables:
        with op.batch_alter_table('audit_logs') as batch_op:
            batch_op.drop_index(batch_op.f('ix_audit_logs_resource_id'))
            batch_op.drop_index(batch_op.f('ix_audit_logs_event_type'))
            batch_op.drop_index(batch_op.f('ix_audit_logs_user_id'))
            batch_op.drop_index(batch_op.f('ix_audit_logs_timestamp'))
            batch_op.drop_index(batch_op.f('ix_audit_logs_id'))
        op.drop_table('audit_logs')

    # 2. Revert review_decisions
    if 'review_decisions' in tables:
        review_cols = {col['name'] for col in insp.get_columns('review_decisions')}
        if 'reviewer_id' in review_cols:
            with op.batch_alter_table('review_decisions') as batch_op:
                batch_op.drop_index(batch_op.f('ix_review_decisions_reviewer_id'))
                batch_op.drop_column('reviewer_id')

    # 3. Revert notices
    if 'notices' in tables:
        notice_cols = {col['name'] for col in insp.get_columns('notices')}
        if 'issuing_officer_id' in notice_cols:
            with op.batch_alter_table('notices') as batch_op:
                batch_op.drop_index(batch_op.f('ix_notices_issuing_officer_id'))
                batch_op.drop_column('issuing_officer_id')

    # 4. Revert users
    if 'users' in tables:
        user_cols = {col['name'] for col in insp.get_columns('users')}
        with op.batch_alter_table('users') as batch_op:
            existing_user_indexes = {ix['name'] for ix in insp.get_indexes('users')}
            if 'ix_users_role' in existing_user_indexes:
                batch_op.drop_index(batch_op.f('ix_users_role'))
            if 'ix_users_badge_number' in existing_user_indexes:
                batch_op.drop_index(batch_op.f('ix_users_badge_number'))
            if 'locked_until' in user_cols:
                batch_op.drop_column('locked_until')
            if 'failed_login_attempts' in user_cols:
                batch_op.drop_column('failed_login_attempts')
            if 'last_login_at' in user_cols:
                batch_op.drop_column('last_login_at')
            if 'badge_number' in user_cols:
                batch_op.drop_column('badge_number')
            if 'jurisdiction_office' in user_cols:
                batch_op.drop_column('jurisdiction_office')
            if 'designation' in user_cols:
                batch_op.drop_column('designation')
            if 'hashed_password' in user_cols:
                batch_op.drop_column('hashed_password')
