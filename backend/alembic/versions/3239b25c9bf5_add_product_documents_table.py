"""add_product_documents_table

Revision ID: 3239b25c9bf5
Revises: 761b5dbff7a8
Create Date: 2025-10-10 22:56:24.112597

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3239b25c9bf5'
down_revision = '761b5dbff7a8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create product_documents table
    op.create_table(
        'product_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_name', sa.String(length=255), nullable=False),
        sa.Column('document_type', sa.Enum('TECHNICAL_DRAWING', 'CATALOG', 'BROCHURE', 'SPEC_SHEET', name='productdocumenttype'), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_product_documents_id'), 'product_documents', ['id'], unique=False)
    op.create_index(op.f('ix_product_documents_product_name'), 'product_documents', ['product_name'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_product_documents_product_name'), table_name='product_documents')
    op.drop_index(op.f('ix_product_documents_id'), table_name='product_documents')
    op.drop_table('product_documents')
    op.execute('DROP TYPE productdocumenttype')
