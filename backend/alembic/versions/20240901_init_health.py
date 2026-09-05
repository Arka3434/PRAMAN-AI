"""Initial health check table

Revision ID: 20240901_init_health
Revises: 
Create Date: 2024-09-01 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20240901_init_health"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "health_checks",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_health_checks_id"), "health_checks", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_health_checks_id"), table_name="health_checks")
    op.drop_table("health_checks")
