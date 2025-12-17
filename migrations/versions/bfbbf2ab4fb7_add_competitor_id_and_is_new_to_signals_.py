"""Add competitor_id and is_new to signals and snapshots

Revision ID: bfbbf2ab4fb7
Revises: 6f3c2e280fce
Create Date: 2025-12-02 18:57:00.688104

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bfbbf2ab4fb7'
down_revision = '6f3c2e280fce'
branch_labels = None
depends_on = None


def upgrade():
    # Add competitor_id to company_signal (nullable)
    with op.batch_alter_table('company_signal', schema=None) as batch_op:
        batch_op.add_column(sa.Column('competitor_id', sa.UUID(), nullable=True))
        batch_op.create_foreign_key(None, 'company', ['competitor_id'], ['id'], ondelete='CASCADE')
    
    # Add is_new with default True (first nullable, then set default, then make not null)
    op.add_column('company_signal', sa.Column('is_new', sa.Boolean(), nullable=True))
    op.execute("UPDATE company_signal SET is_new = false WHERE is_new IS NULL")
    op.alter_column('company_signal', 'is_new', nullable=False, server_default=sa.text('true'))

    # Add competitor_id to company_snapshot (nullable)
    with op.batch_alter_table('company_snapshot', schema=None) as batch_op:
        batch_op.add_column(sa.Column('competitor_id', sa.UUID(), nullable=True))
        batch_op.create_foreign_key(None, 'company', ['competitor_id'], ['id'], ondelete='CASCADE')


def downgrade():
    with op.batch_alter_table('company_snapshot', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('competitor_id')

    with op.batch_alter_table('company_signal', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('is_new')
        batch_op.drop_column('competitor_id')
