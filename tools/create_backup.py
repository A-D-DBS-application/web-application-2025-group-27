"""Create a backup of the current database state.

This script creates a backup by exporting all data to JSON format.
Run this regularly, especially before migrations.

Usage:
    python3 tools/create_backup.py
    # or from project root:
    python3 -m tools.create_backup
"""

import sys
import os
from pathlib import Path

# Add parent directory to path so we can import app modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import create_app, db
from models import User, Company, CompanyCompetitor, Industry, CompanyIndustry
from datetime import datetime
import json

app = create_app()

def create_backup():
    """Create a backup of all data in the database."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Save backup in backups directory
    backups_dir = project_root / "backups"
    backups_dir.mkdir(exist_ok=True)
    backup_file = backups_dir / f"backup_mvp_{timestamp}.json"
    
    with app.app_context():
        backup_data = {
            "timestamp": timestamp,
            "version": "MVP",
            "users": [],
            "companies": [],
            "competitors": [],
            "industries": [],
            "company_industries": []
        }
        
        # Backup users
        users = db.session.query(User).all()
        for user in users:
            backup_data["users"].append({
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "company_id": str(user.company_id) if user.company_id else None,
                "role": user.role,
                "is_active": user.is_active,
            })
        
        # Backup companies
        companies = db.session.query(Company).all()
        for company in companies:
            backup_data["companies"].append({
                "id": str(company.id),
                "name": company.name,
                "domain": company.domain,
                "headline": company.headline,
                "number_of_employees": company.number_of_employees,
                "funding": company.funding,
                "industry": company.industry,
                "country": company.country,
            })
        
        # Backup competitor relationships
        competitors = db.session.query(CompanyCompetitor).all()
        for comp in competitors:
            backup_data["competitors"].append({
                "company_id": str(comp.company_id),
                "competitor_id": str(comp.competitor_id),
                "notes": comp.notes,
            })
        
        # Backup industries
        industries = db.session.query(Industry).all()
        for industry in industries:
            backup_data["industries"].append({
                "id": str(industry.id),
                "name": industry.name,
                "description": industry.description,
            })
        
        # Backup company-industry relationships
        company_industries = db.session.query(CompanyIndustry).all()
        for ci in company_industries:
            backup_data["company_industries"].append({
                "company_id": str(ci.company_id),
                "industry_id": str(ci.industry_id),
            })
        
        # Write to file
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Backup created: {backup_file}")
        print(f"   - {len(backup_data['users'])} users")
        print(f"   - {len(backup_data['companies'])} companies")
        print(f"   - {len(backup_data['competitors'])} competitor relationships")
        print(f"   - {len(backup_data['industries'])} industries")
        print(f"   - {len(backup_data['company_industries'])} company-industry relationships")
        print(f"\n💡 Tip: Store this backup in a safe place!")

if __name__ == "__main__":
    create_backup()

