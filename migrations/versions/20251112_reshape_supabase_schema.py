"""Reshape schema to match Supabase UUID-based design.

This migration drops the old demo `people` table and creates the production
tables used by the startup intelligence platform.  All primary keys are UUIDs
with `gen_random_uuid()` defaults, and bridge tables capture many-to-many
relationships for competitors and industries.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20251112_supabase_schema"
down_revision = "b7d5cb14029f"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=True)
now_utc = sa.text("timezone('utc', now())")


def upgrade() -> None:
    # Ensure the uuid-ossp extension is available (Supabase enables pgcrypto already,
    # but this call is idempotent and safe).
    op.execute("CREATE EXTENSION IF NOT EXISTS \"pgcrypto\"")

    # Drop legacy table from the tutorial app if it still exists.
    op.execute("DROP TABLE IF EXISTS people CASCADE")

    op.create_table(
        "account",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_account_email", "account", ["email"], unique=True)

    op.create_table(
        "company",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now_utc, nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=now_utc, nullable=False),
        sa.Column("source", sa.String(length=255), server_default=sa.text("'Clay'"), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("headline", sa.Text(), nullable=True),
        sa.Column("number_of_employees", sa.BigInteger(), nullable=True),
        sa.Column("funding", sa.BigInteger(), nullable=True),
        sa.Column("andere_criteria", sa.Text(), nullable=True),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_company_domain", "company", ["domain"], unique=False)

    op.create_table(
        "industries",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now_utc, nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=now_utc, nullable=False),
        sa.Column("source", sa.String(length=255), server_default=sa.text("'Clay'"), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("value", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

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

    op.create_table(
        "company_industry",
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("industry_id", UUID, nullable=False),
        sa.PrimaryKeyConstraint("company_id", "industry_id", name="company_industry_pk"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["industry_id"],
            ["industries.id"],
            ondelete="CASCADE",
        ),
    )

    op.create_table(
        "company_competitor",
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("competitor_id", UUID, nullable=False),
        sa.Column("relationship_type", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("company_id", "competitor_id", name="company_competitor_pk"),
        sa.CheckConstraint("company_id <> competitor_id", name="ck_company_not_self"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["competitor_id"],
            ["company.id"],
            ondelete="CASCADE",
        ),
    )

    op.create_table(
        "product",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now_utc, nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=now_utc, nullable=False),
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
        sa.ForeignKeyConstraint(
            ["industry_id"],
            ["industries.id"],
            ondelete="SET NULL",
        ),
    )


def downgrade() -> None:
    op.drop_table("product")
    op.drop_table("company_competitor")
    op.drop_table("company_industry")
    op.drop_index("ix_profile_email", table_name="profile")
    op.drop_table("profile")
    op.drop_table("industries")
    op.drop_index("ix_company_domain", table_name="company")
    op.drop_table("company")
    op.drop_index("ix_account_email", table_name="account")
    op.drop_table("account")
    # Recreate the legacy people table for symmetry (optional).
    op.create_table(
        "people",
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("job", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("pid"),
    )

