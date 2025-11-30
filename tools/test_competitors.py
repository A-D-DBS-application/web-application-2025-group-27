#!/usr/bin/env python3
"""Test script to fetch competitors for Apple and Microsoft."""

import os
import sys
from pathlib import Path

# Add parent directory to path to import services
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from services.company_api import fetch_similar_companies

# Load environment variables
load_dotenv()

def test_competitors(domain: str, company_name: str):
    """Test fetching competitors for a given domain."""
    print(f"\n{'='*60}")
    print(f"Testing competitors for: {company_name} ({domain})")
    print(f"{'='*60}\n")
    
    try:
        competitors = fetch_similar_companies(domain=domain, limit=10)
        
        if not competitors:
            print("❌ No competitors found or API call failed")
            print("   (This could be due to API limits, filtering, or API errors)")
            return
        
        print(f"✅ Found {len(competitors)} competitors:\n")
        
        for i, competitor in enumerate(competitors, 1):
            print(f"{i}. {competitor.get('name', 'Unknown')}")
            print(f"   Domain: {competitor.get('domain', 'N/A')}")
            print(f"   Industry: {competitor.get('industry', 'N/A')}")
            if competitor.get('description'):
                desc = competitor.get('description', '')[:100]
                print(f"   Description: {desc}...")
            print()
        
        print(f"\nTotal: {len(competitors)} competitors")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Test Apple
    test_competitors("apple.com", "Apple")
    
    # Test Microsoft
    test_competitors("microsoft.com", "Microsoft")
    
    # Test other companies
    test_competitors("google.com", "Google")
    test_competitors("amazon.com", "Amazon")
    test_competitors("tesla.com", "Tesla")
    
    print(f"\n{'='*60}")
    print("Testing complete!")
    print(f"{'='*60}\n")

