"""add_summary_to_documents

Revision ID: 47d940edfcfe
Revises: 
Create Date: 2025-10-02 04:40:57.808670

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '47d940edfcfe'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add summary column to documents table
    op.add_column('documents', sa.Column('summary', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove summary column from documents table
    op.drop_column('documents', 'summary')
