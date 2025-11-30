"""Clear all data from the database - FOR TESTING ONLY.

⚠️  WARNING: This script will DELETE ALL DATA from the database!
Use only for development/testing purposes.

This script:
- Deletes all data from all tables
- Keeps table structure intact
- Requires confirmation before proceeding
- Optionally creates a backup before clearing

Usage:
    python3 tools/clear_database.py
    # or with auto-confirm (dangerous):
    python3 tools/clear_database.py --yes
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import app modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import create_app, db
from models import User, Company, CompanyCompetitor, Industry, CompanyIndustry
from datetime import datetime

app = create_app()


def clear_database(confirm: bool = False):
    """Clear all data from the database.
    
    Args:
        confirm: If True, skip confirmation prompt (dangerous!)
    """
    if not confirm:
        print("=" * 70)
        print("⚠️  WARNING: This will DELETE ALL DATA from the database!")
        print("=" * 70)
        print("\nThis action will:")
        print("  - Delete all users")
        print("  - Delete all companies")
        print("  - Delete all competitors")
        print("  - Delete all industries")
        print("  - Delete all company-industry relationships")
        print("\n⚠️  This action CANNOT be undone!")
        print("\n" + "=" * 70)
        
        response = input("\nType 'DELETE ALL DATA' to confirm: ")
        
        if response != "DELETE ALL DATA":
            print("\n❌ Cancelled. No data was deleted.")
            return False
    
    with app.app_context():
        try:
            print("\n🗑️  Clearing database...")
            
            # Delete in correct order (respecting foreign keys)
            # 1. Delete bridge tables first
            deleted_ci = db.session.query(CompanyIndustry).delete()
            print(f"   ✓ Deleted {deleted_ci} company-industry relationships")
            
            deleted_cc = db.session.query(CompanyCompetitor).delete()
            print(f"   ✓ Deleted {deleted_cc} competitor relationships")
            
            # 2. Delete main tables
            deleted_users = db.session.query(User).delete()
            print(f"   ✓ Deleted {deleted_users} users")
            
            deleted_companies = db.session.query(Company).delete()
            print(f"   ✓ Deleted {deleted_companies} companies")
            
            deleted_industries = db.session.query(Industry).delete()
            print(f"   ✓ Deleted {deleted_industries} industries")
            
            # Commit all deletions
            db.session.commit()
            
            print("\n✅ Database cleared successfully!")
            print("   All data has been removed. Table structures remain intact.")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error clearing database: {e}")
            print("   Transaction rolled back. No data was deleted.")
            return False


def create_backup_before_clear():
    """Optionally create a backup before clearing."""
    try:
        from tools.create_backup import create_backup
        print("\n💾 Creating backup before clearing...")
        create_backup()
        print("   ✓ Backup created\n")
        return True
    except Exception as e:
        print(f"   ⚠️  Could not create backup: {e}")
        print("   Continuing without backup...\n")
        return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Clear all data from the database (FOR TESTING ONLY)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (asks for confirmation)
  python3 tools/clear_database.py
  
  # Auto-confirm (dangerous!)
  python3 tools/clear_database.py --yes
  
  # Create backup first, then clear
  python3 tools/clear_database.py --backup
        """
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt (dangerous!)'
    )
    parser.add_argument(
        '--backup', '-b',
        action='store_true',
        help='Create a backup before clearing database'
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("Database Clear Tool - FOR TESTING ONLY")
    print("=" * 70)
    
    # Create backup if requested
    if args.backup:
        create_backup_before_clear()
    
    # Clear database
    success = clear_database(confirm=args.yes)
    
    if success:
        print("\n" + "=" * 70)
        print("✅ Database is now empty and ready for testing")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("❌ Database clear was cancelled or failed")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()

