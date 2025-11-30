"""Restore Industry and CompanyIndustry tables for many-to-many relationship.

This migration restores the industries and company_industry tables that were
removed in the MVP simplification, as they are needed for the many-to-many
relationship between companies and industries.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20250101_restore_industries"
down_revision = "20250101_simplify_mvp"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    # Check if industries table already exists (might have been kept)
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables 
                          WHERE table_name='industries') THEN
                -- Create industries table (simplified, no metadata)
                CREATE TABLE industries (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL UNIQUE,
                    description TEXT
                );
            END IF;
        END $$;
    """)
    
    # Check if company_industry table already exists
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables 
                          WHERE table_name='company_industry') THEN
                -- Create company_industry bridge table
                CREATE TABLE company_industry (
                    company_id UUID NOT NULL,
                    industry_id UUID NOT NULL,
                    PRIMARY KEY (company_id, industry_id),
                    FOREIGN KEY (company_id) REFERENCES company(id) ON DELETE CASCADE,
                    FOREIGN KEY (industry_id) REFERENCES industries(id) ON DELETE CASCADE
                );
            END IF;
        END $$;
    """)
    
    # If industries table exists but has metadata columns, remove them (simplify)
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name='industries' AND column_name='created_at') THEN
                ALTER TABLE industries DROP COLUMN IF EXISTS created_at;
                ALTER TABLE industries DROP COLUMN IF EXISTS last_updated;
                ALTER TABLE industries DROP COLUMN IF EXISTS source;
                ALTER TABLE industries DROP COLUMN IF EXISTS value;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Drop the bridge table first (due to foreign keys)
    op.execute("DROP TABLE IF EXISTS company_industry CASCADE")
    # Then drop industries table
    op.execute("DROP TABLE IF EXISTS industries CASCADE")

