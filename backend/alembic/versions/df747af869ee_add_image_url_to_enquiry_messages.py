"""add_image_url_to_enquiry_messages

Revision ID: df747af869ee
Revises: e572803515db
Create Date: 2025-10-08 10:22:05.829202

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'df747af869ee'
down_revision = 'e572803515db'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add image_url column to enquiry_messages table (if not exists)
    from sqlalchemy import inspect
    from alembic import context
    
    conn = context.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('enquiry_messages')]
    
    if 'image_url' not in columns:
        op.add_column('enquiry_messages', sa.Column('image_url', sa.String(500), nullable=True))


def downgrade() -> None:
    # Remove image_url column from enquiry_messages table
    op.drop_column('enquiry_messages', 'image_url')
