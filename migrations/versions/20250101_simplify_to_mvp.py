"""Simplify schema to MVP structure.

This migration:
1. Creates the new simplified 'user' table
2. Migrates data from account + profile to user
3. Simplifies company table (removes metadata fields)
4. Simplifies company_competitor (removes relationship_type)
5. Drops unused tables (product, industries, company_industry)
6. Drops old tables (account, profile)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20250101_simplify_mvp"
down_revision = "7e443e3897bc"  # Latest migration: add_industry_and_country_to_company
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    # Step 1: Create the new simplified 'user' table
    op.create_table(
        "user",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column("company_id", UUID, nullable=True),
        sa.Column("role", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)
    op.create_index("ix_user_company_id", "user", ["company_id"], unique=False)

    # Step 2: Migrate data from account + profile to user
    # This SQL joins account and profile tables and inserts into user
    op.execute("""
        INSERT INTO "user" (id, email, first_name, last_name, company_id, role, is_active)
        SELECT 
            p.id,
            COALESCE(a.email, p.email) as email,
            p.first_name,
            p.last_name,
            p.company_id,
            p.role,
            COALESCE(a.is_active, true) as is_active
        FROM profile p
        LEFT JOIN account a ON p.account_id = a.id
        WHERE p.id IS NOT NULL
    """)

    # Step 3: Simplify company table - remove metadata columns
    # First, drop the columns (PostgreSQL doesn't support IF EXISTS for columns in older versions)
    op.execute("ALTER TABLE company DROP COLUMN IF EXISTS created_at")
    op.execute("ALTER TABLE company DROP COLUMN IF EXISTS last_updated")
    op.execute("ALTER TABLE company DROP COLUMN IF EXISTS source")
    op.execute("ALTER TABLE company DROP COLUMN IF EXISTS andere_criteria")
    op.execute("ALTER TABLE company DROP COLUMN IF EXISTS external_reference")
    
    # Add simplified industry and country columns if they don't exist
    # (They might already exist from previous migration)
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='company' AND column_name='industry') THEN
                ALTER TABLE company ADD COLUMN industry VARCHAR(255);
            END IF;
        END $$;
    """)
    
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='company' AND column_name='country') THEN
                ALTER TABLE company ADD COLUMN country VARCHAR(255);
            END IF;
        END $$;
    """)

    # Step 4: Simplify company_competitor - remove relationship_type
    op.execute("ALTER TABLE company_competitor DROP COLUMN IF EXISTS relationship_type")

    # Step 5: Drop unused tables (in correct order due to foreign keys)
    # NOTE: industries and company_industry are kept for many-to-many relationship
    # They will be simplified in a later migration
    op.execute("DROP TABLE IF EXISTS product CASCADE")
    # Keep industries and company_industry - they will be simplified but not removed

    # Step 6: Drop old account and profile tables
    # First drop profile (it has foreign key to account)
    op.execute("DROP TABLE IF EXISTS profile CASCADE")
    op.execute("DROP TABLE IF EXISTS account CASCADE")


def downgrade() -> None:
    # Recreate account table
    op.create_table(
        "account",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_account_email", "account", ["email"], unique=True)

    # Recreate profile table
    op.create_table(
        "profile",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("account_id", UUID, nullable=False),
        sa.Column("company_id", UUID, nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=255), nullable=True),
        sa.Column("phone_number", sa.String(length=32), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_profile_email", "profile", ["email"], unique=False)

    # Migrate data back from user to account + profile
    # Note: This is a simplified migration - some data might be lost
    op.execute("""
        INSERT INTO account (id, email, is_active)
        SELECT id, email, is_active
        FROM "user"
    """)

    op.execute("""
        INSERT INTO profile (id, account_id, company_id, email, first_name, last_name, role)
        SELECT id, id as account_id, company_id, email, first_name, last_name, role
        FROM "user"
    """)

    # Recreate metadata columns in company
    op.execute("""
        ALTER TABLE company 
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now()),
        ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now()),
        ADD COLUMN IF NOT EXISTS source VARCHAR(255) DEFAULT 'Clay',
        ADD COLUMN IF NOT EXISTS andere_criteria TEXT,
        ADD COLUMN IF NOT EXISTS external_reference VARCHAR(255)
    """)

    # Recreate relationship_type in company_competitor
    op.execute("""
        ALTER TABLE company_competitor 
        ADD COLUMN IF NOT EXISTS relationship_type VARCHAR(255)
    """)

    # Industries and company_industry are kept (not dropped in upgrade)
    # They will be restored/simplified by the restore_industries migration

    op.create_table(
        "product",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("source", sa.String(length=255), server_default=sa.text("'Clay'"), nullable=True),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("industry_id", UUID, nullable=True),
        sa.Column("funding", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.id"],
            ondelete="CASCADE",
        ),
    )

    # Drop the user table
    op.drop_index("ix_user_company_id", table_name="user")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_table("user")

