"""Test CompanyEnrich API key configuration.

This script verifies that the API key is correctly set and can make API calls.
"""

import sys
from pathlib import Path

# Add parent directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os

# Try to load dotenv, but continue if not available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, but that's okay - environment variables might be set directly
    pass

from services.company_api import fetch_company_info

def test_api_key():
    """Test if API key is configured and working."""
    print("=" * 70)
    print("CompanyEnrich API Key Test")
    print("=" * 70)
    print()
    
    # Check if API key is set
    api_key = os.getenv("COMPANY_ENRICH_API_KEY")
    
    if not api_key:
        print("❌ API key not found in environment variables")
        print()
        print("To set the API key:")
        print("1. Open .env file in project root")
        print("2. Add: COMPANY_ENRICH_API_KEY=your-api-key-here")
        print("3. Save the file")
        return False
    
    if api_key == "your-api-key-here":
        print("⚠️  API key is set to placeholder value")
        print("   Please replace 'your-api-key-here' with your actual API key")
        return False
    
    print(f"✅ API key found: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '****'}")
    print()
    
    # Test API call with a known domain
    print("Testing API call with domain 'example.com'...")
    print()
    
    try:
        result = fetch_company_info(domain="example.com")
        
        if result:
            print("✅ API call successful!")
            print()
            print("Response data:")
            print(f"  - Domain: {result.get('domain', 'N/A')}")
            print(f"  - Name: {result.get('name', 'N/A')}")
            print(f"  - Description: {result.get('description', 'N/A')[:50]}..." if result.get('description') else "  - Description: N/A")
            print(f"  - Employees: {result.get('employees', 'N/A')}")
            print(f"  - Industry: {result.get('industry', 'N/A')}")
            print(f"  - Country: {result.get('country', 'N/A')}")
            print()
            print("✅ API key is working correctly!")
            return True
        else:
            print("⚠️  API call returned no data")
            print("   This might be normal if the domain doesn't exist in the database")
            print("   But the API key appears to be configured correctly")
            return True
            
    except Exception as e:
        print(f"❌ Error testing API: {e}")
        print()
        print("Possible issues:")
        print("  - API key might be invalid")
        print("  - Network connection problem")
        print("  - API service might be down")
        return False

if __name__ == "__main__":
    success = test_api_key()
    print("=" * 70)
    if success:
        print("✅ API key test completed")
    else:
        print("❌ API key test failed - check configuration")
    print("=" * 70)
    sys.exit(0 if success else 1)

