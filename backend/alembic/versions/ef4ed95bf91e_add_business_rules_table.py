"""add_business_rules_table

Revision ID: ef4ed95bf91e
Revises: df747af869ee
Create Date: 2025-10-10 04:16:32.757570

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = 'ef4ed95bf91e'
down_revision = 'e572803515db'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'business_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rule_name', sa.String(255), nullable=False),
        sa.Column('service_type', sa.String(255), nullable=True, index=True),
        sa.Column('region', sa.String(50), nullable=True),
        sa.Column('rule_config', JSON, nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('priority', sa.Integer(), default=100, nullable=False),
        sa.Column('source_reference', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_business_rules_rule_name', 'business_rules', ['rule_name'])
    op.create_index('ix_business_rules_is_active', 'business_rules', ['is_active'])


def downgrade() -> None:
    op.drop_index('ix_business_rules_is_active', table_name='business_rules')
    op.drop_index('ix_business_rules_rule_name', table_name='business_rules')
    op.drop_table('business_rules')
