"""Add core inspection domain models.

Revision ID: 20260902_phase2_core_domain_models
Revises: 20240901_init_health
Create Date: 2026-09-02 15:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260902_phase2_core_domain_models'
down_revision = '20240901_init_health'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('full_name', sa.String(length=150), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='inspector'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)

    op.create_table(
        'products',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('brand', sa.String(length=150), nullable=True),
        sa.Column('manufacturer', sa.String(length=150), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_products_id'), 'products', ['id'], unique=False)
    op.create_index(op.f('ix_products_name'), 'products', ['name'], unique=False)

    op.create_table(
        'inspections',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('inspection_number', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='draft'),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('notes', sa.String(length=2000), nullable=True),
        sa.Column('product_id', sa.String(length=36), nullable=True),
        sa.Column('inspector_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['inspector_id'], ['users.id']),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_inspections_id'), 'inspections', ['id'], unique=False)
    op.create_index(op.f('ix_inspections_inspection_number'), 'inspections', ['inspection_number'], unique=True)
    op.create_index(op.f('ix_inspections_product_id'), 'inspections', ['product_id'], unique=False)
    op.create_index(op.f('ix_inspections_inspector_id'), 'inspections', ['inspector_id'], unique=False)
    op.create_index(op.f('ix_inspections_status'), 'inspections', ['status'], unique=False)

    op.create_table(
        'inspection_images',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('inspection_id', sa.String(length=36), nullable=False),
        sa.Column('image_type', sa.String(length=32), nullable=False, server_default='primary'),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('storage_path', sa.String(length=500), nullable=True),
        sa.Column('mime_type', sa.String(length=80), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['inspection_id'], ['inspections.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_inspection_images_id'), 'inspection_images', ['id'], unique=False)
    op.create_index(op.f('ix_inspection_images_inspection_id'), 'inspection_images', ['inspection_id'], unique=False)
    op.create_index(op.f('ix_inspection_images_image_type'), 'inspection_images', ['image_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_inspection_images_image_type'), table_name='inspection_images')
    op.drop_index(op.f('ix_inspection_images_inspection_id'), table_name='inspection_images')
    op.drop_index(op.f('ix_inspection_images_id'), table_name='inspection_images')
    op.drop_table('inspection_images')

    op.drop_index(op.f('ix_inspections_status'), table_name='inspections')
    op.drop_index(op.f('ix_inspections_inspector_id'), table_name='inspections')
    op.drop_index(op.f('ix_inspections_product_id'), table_name='inspections')
    op.drop_index(op.f('ix_inspections_inspection_number'), table_name='inspections')
    op.drop_index(op.f('ix_inspections_id'), table_name='inspections')
    op.drop_table('inspections')

    op.drop_index(op.f('ix_products_name'), table_name='products')
    op.drop_index(op.f('ix_products_id'), table_name='products')
    op.drop_table('products')

    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
