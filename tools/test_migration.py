"""Test script to verify migration was successful.

Run this after executing the migration to verify everything worked correctly.

Usage:
    python3 tools/test_migration.py
    # or from project root:
    python3 -m tools.test_migration
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import app modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import create_app, db
from models import User, Company, CompanyCompetitor, Industry, CompanyIndustry

app = create_app()

with app.app_context():
    print("=" * 60)
    print("Migration Verification Script")
    print("=" * 60)
    
    # Check if user table exists and has data
    try:
        user_count = db.session.query(User).count()
        print(f"✅ User table exists with {user_count} users")
        
        if user_count > 0:
            sample_user = db.session.query(User).first()
            print(f"   Sample user: {sample_user.email} ({sample_user.first_name} {sample_user.last_name})")
            if sample_user.company:
                print(f"   Company: {sample_user.company.name}")
    except Exception as e:
        print(f"❌ Error checking user table: {e}")
    
    # Check if old tables are gone
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        old_tables = ['account', 'profile', 'product']
        for table in old_tables:
            if table in tables:
                print(f"⚠️  Warning: Old table '{table}' still exists")
            else:
                print(f"✅ Old table '{table}' correctly removed")
        
        # Check if industries tables exist (should exist)
        if 'industries' in tables:
            print(f"✅ Industries table exists")
        else:
            print(f"⚠️  Warning: Industries table missing")
        
        if 'company_industry' in tables:
            print(f"✅ CompanyIndustry bridge table exists")
        else:
            print(f"⚠️  Warning: CompanyIndustry bridge table missing")
    except Exception as e:
        print(f"❌ Error checking tables: {e}")
    
    # Check company table structure
    try:
        company_count = db.session.query(Company).count()
        print(f"✅ Company table exists with {company_count} companies")
        
        if company_count > 0:
            sample_company = db.session.query(Company).first()
            print(f"   Sample company: {sample_company.name}")
            
            # Check if metadata columns are removed
            columns = [col.name for col in Company.__table__.columns]
            metadata_cols = ['created_at', 'last_updated', 'source', 'andere_criteria', 'external_reference']
            for col in metadata_cols:
                if col in columns:
                    print(f"⚠️  Warning: Metadata column '{col}' still exists")
                else:
                    print(f"✅ Metadata column '{col}' correctly removed")
    except Exception as e:
        print(f"❌ Error checking company table: {e}")
    
    # Check company_competitor structure
    try:
        competitor_count = db.session.query(CompanyCompetitor).count()
        print(f"✅ CompanyCompetitor table exists with {competitor_count} relationships")
        
        # Check if relationship_type column is removed
        columns = [col.name for col in CompanyCompetitor.__table__.columns]
        if 'relationship_type' in columns:
            print(f"⚠️  Warning: 'relationship_type' column still exists")
        else:
            print(f"✅ 'relationship_type' column correctly removed")
    except Exception as e:
        print(f"❌ Error checking company_competitor table: {e}")
    
    # Check industries
    try:
        industry_count = db.session.query(Industry).count()
        print(f"✅ Industry table exists with {industry_count} industries")
        
        company_industry_count = db.session.query(CompanyIndustry).count()
        print(f"✅ CompanyIndustry bridge table has {company_industry_count} relationships")
    except Exception as e:
        print(f"❌ Error checking industries: {e}")
    
    print("=" * 60)
    print("Verification complete!")
    print("=" * 60)

