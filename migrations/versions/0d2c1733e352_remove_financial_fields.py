"""remove_financial_fields

Revision ID: 0d2c1733e352
Revises: 88caf396b78e
Create Date: 2025-11-30 22:59:15.558359

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0d2c1733e352'
down_revision = '88caf396b78e'
branch_labels = None
depends_on = None


def upgrade():
    # Remove financial fields from company table
    with op.batch_alter_table('company', schema=None) as batch_op:
        batch_op.drop_column('stock_symbol')
        batch_op.drop_column('stock_exchange')
        batch_op.drop_column('funding_stage')
        batch_op.drop_column('revenue')


def downgrade():
    # Restore financial fields to company table
    with op.batch_alter_table('company', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stock_symbol', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('stock_exchange', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('funding_stage', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('revenue', sa.String(length=50), nullable=True))
