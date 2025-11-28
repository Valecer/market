#!/usr/bin/env python3
"""Helper script to create a test Google Sheet with sample data.

This script creates a test Google Sheet with:
- 100 rows of product data
- 95 valid rows (with all required fields)
- 5 rows with missing price (for error testing)

Usage:
    python scripts/create_test_sheet.py --title "Test Price List" --credentials-path /path/to/credentials.json
    python scripts/create_test_sheet.py --title "Test Price List"
"""
import argparse
import sys
import random
from pathlib import Path
from datetime import datetime

# Add src to path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

# Load .env file if it exists
env_file = project_root / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        pass

import gspread
from gspread.exceptions import APIError
from src.config import settings


# Sample product data for generating test rows
PRODUCT_NAMES = [
    "Cotton T-Shirt",
    "Denim Jeans",
    "Wool Sweater",
    "Leather Jacket",
    "Silk Scarf",
    "Cotton Shorts",
    "Canvas Sneakers",
    "Leather Boots",
    "Baseball Cap",
    "Wool Socks",
    "Cotton Pants",
    "Denim Shorts",
    "Fleece Hoodie",
    "Nylon Backpack",
    "Canvas Tote Bag",
    "Leather Belt",
    "Cotton Polo",
    "Denim Vest",
    "Wool Beanie",
    "Cotton Tank Top",
]

COLORS = ["Red", "Blue", "Green", "Black", "White", "Gray", "Navy", "Brown", "Beige", "Pink"]
SIZES = ["XS", "S", "M", "L", "XL", "XXL"]
MATERIALS = ["100% Cotton", "100% Wool", "100% Leather", "100% Polyester", "Cotton Blend", "Wool Blend"]


def generate_test_data(num_valid: int = 95, num_invalid: int = 5) -> list[list[str]]:
    """Generate test data rows for Google Sheet.
    
    Args:
        num_valid: Number of valid rows (with all fields)
        num_invalid: Number of invalid rows (missing price)
    
    Returns:
        List of lists representing sheet rows (headers + data rows)
    """
    # Header row
    headers = [
        "Product Code",  # Maps to 'sku'
        "Product Name",  # Maps to 'name'
        "Unit Price",    # Maps to 'price'
        "Color",         # Characteristic column
        "Size",          # Characteristic column
        "Material",      # Characteristic column
        "Weight (kg)",   # Characteristic column (numeric)
    ]
    
    rows = [headers]
    
    # Generate valid rows
    for i in range(1, num_valid + 1):
        sku = f"TEST-{i:04d}"
        name = random.choice(PRODUCT_NAMES)
        price = round(random.uniform(10.0, 200.0), 2)
        color = random.choice(COLORS)
        size = random.choice(SIZES)
        material = random.choice(MATERIALS)
        weight = round(random.uniform(0.1, 5.0), 2)
        
        row = [sku, name, str(price), color, size, material, str(weight)]
        rows.append(row)
    
    # Generate invalid rows (missing price)
    for i in range(num_valid + 1, num_valid + num_invalid + 1):
        sku = f"TEST-{i:04d}"
        name = random.choice(PRODUCT_NAMES)
        # Missing price - leave empty
        price = ""
        color = random.choice(COLORS)
        size = random.choice(SIZES)
        material = random.choice(MATERIALS)
        weight = round(random.uniform(0.1, 5.0), 2)
        
        row = [sku, name, price, color, size, material, str(weight)]
        rows.append(row)
    
    return rows


def create_test_sheet(
    title: str,
    credentials_path: str | None = None,
    sheet_name: str = "Sheet1",
    existing_spreadsheet_url: str | None = None
) -> dict:
    """Create a test Google Sheet with sample data.
    
    Args:
        title: Title of the spreadsheet (used only if creating new spreadsheet)
        credentials_path: Path to service account credentials JSON file
                        If None, checks local project credentials, then settings
        sheet_name: Name of the worksheet tab (default: "Sheet1")
        existing_spreadsheet_url: Optional URL to existing spreadsheet to populate.
                                 If provided, uses this instead of creating new.
    
    Returns:
        Dictionary with:
            - spreadsheet_id: ID of created spreadsheet
            - sheet_url: URL to the spreadsheet
            - worksheet_name: Name of the worksheet
            - total_rows: Total number of data rows created
    
    Raises:
        FileNotFoundError: If credentials file not found
        APIError: If Google Sheets API error occurs
        Exception: For other errors
    """
    # Determine credentials path: explicit > local project > settings
    if credentials_path:
        creds_path = credentials_path
        print(f"📁 Using provided credentials path: {creds_path}")
    else:
        # Check for local project credentials (two levels up from scripts/ to project root)
        # scripts/ -> services/python-ingestion -> marketbel/
        repo_root = project_root.parent.parent
        local_creds = repo_root / "credentials" / "google-credentials.json"
        
        print(f"🔍 Checking for local credentials...")
        print(f"   project_root: {project_root}")
        print(f"   repo_root: {repo_root}")
        print(f"   local_creds: {local_creds}")
        print(f"   exists: {local_creds.exists()}")
        
        if local_creds.exists():
            creds_path = str(local_creds)
            print(f"📁 Found local credentials at: {creds_path}")
        else:
            # Fall back to settings (Docker path)
            creds_path = settings.google_credentials_path
            print(f"⚠️  Local credentials not found, using settings path: {creds_path}")
    
    # Authenticate with service account
    try:
        # Verify file exists before attempting authentication
        creds_path_obj = Path(creds_path)
        if not creds_path_obj.exists():
            # Try one more time to find local credentials
            repo_root = project_root.parent.parent
            alt_local_creds = repo_root / "credentials" / "google-credentials.json"
            if alt_local_creds.exists():
                creds_path = str(alt_local_creds)
                print(f"📁 Found local credentials at: {creds_path}")
            else:
                raise FileNotFoundError(
                    f"Credentials file not found: {creds_path}\n"
                    f"Checked paths:\n"
                    f"  - {creds_path}\n"
                    f"  - {alt_local_creds}\n"
                    f"Please provide credentials path with --credentials-path or set GOOGLE_CREDENTIALS_PATH environment variable."
                )
        
        gc = gspread.service_account(filename=creds_path)
        print(f"✅ Authenticated with Google Sheets API")
    except FileNotFoundError as e:
        raise FileNotFoundError(str(e)) from e
    except Exception as e:
        raise Exception(f"Failed to authenticate with Google Sheets API: {e}") from e
    
    # Generate test data
    print(f"📊 Generating test data...")
    data_rows = generate_test_data(num_valid=95, num_invalid=5)
    total_rows = len(data_rows) - 1  # Exclude header row
    
    # Open existing spreadsheet or create new one
    if existing_spreadsheet_url:
        try:
            print(f"📂 Opening existing spreadsheet from URL...")
            spreadsheet = gc.open_by_url(existing_spreadsheet_url)
            print(f"✅ Opened existing spreadsheet: {spreadsheet.id} ({spreadsheet.title})")
        except Exception as e:
            raise Exception(
                f"Failed to open existing spreadsheet: {e}\n"
                f"Make sure the spreadsheet is shared with the service account:\n"
                f"  {creds_path_obj.parent.parent / 'README.md'}"
            ) from e
    else:
        # Create new spreadsheet
        try:
            print(f"📝 Creating spreadsheet '{title}'...")
            spreadsheet = gc.create(title)
            print(f"✅ Spreadsheet created: {spreadsheet.id}")
        except APIError as e:
            # Extract error message from APIError
            error_msg = str(e)
            error_code = ""
            if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                error_code = f"HTTP {e.response.status_code}"
            elif "403" in error_msg:
                error_code = "HTTP 403"
            
            if "403" in error_msg or "quota" in error_msg.lower():
                # Note: "storage quota" error can also mean API quota, not actual storage
                raise Exception(
                    f"❌ Google Drive API Error ({error_code}): {error_msg}\n\n"
                    f"   NOTE: This might be API quota, not storage quota!\n"
                    f"   Even if your personal Drive has space, the service account\n"
                    f"   might have hit API rate limits or quota restrictions.\n\n"
                    f"   WORKAROUND: Create a spreadsheet manually and use --use-existing flag:\n"
                    f"   python scripts/create_test_sheet.py --use-existing <URL>\n\n"
                    f"   Or fix the API issue:\n"
                    f"   1. Enable APIs (required):\n"
                    f"      - https://console.cloud.google.com/apis/library/sheets.googleapis.com?project=testsheetpars\n"
                    f"      - https://console.cloud.google.com/apis/library/drive.googleapis.com?project=testsheetpars\n"
                    f"   2. Check API quotas:\n"
                    f"      - https://console.cloud.google.com/apis/api/sheets.googleapis.com/quotas?project=testsheetpars\n"
                    f"      - https://console.cloud.google.com/apis/api/drive.googleapis.com/quotas?project=testsheetpars\n"
                    f"   3. Verify service account has Editor role in IAM & Admin\n"
                ) from e
            else:
                raise Exception(f"Failed to create spreadsheet ({error_code}): {error_msg}") from e
    
    # Get or create worksheet
    try:
        # Get the default first worksheet
        worksheet = spreadsheet.get_worksheet(0)
        # Rename it if needed
        if worksheet.title != sheet_name:
            worksheet.update_title(sheet_name)
        print(f"✅ Using worksheet '{sheet_name}'")
    except Exception as e:
        raise Exception(f"Failed to get/rename worksheet: {e}") from e
    
    # Update worksheet with data (batch update for efficiency)
    try:
        print(f"📥 Writing {total_rows} rows to worksheet...")
        # Use batch update for better performance
        # worksheet.update() handles large data efficiently
        worksheet.update(data_rows, value_input_option='USER_ENTERED')
        print(f"✅ Data written successfully")
    except APIError as e:
        error_msg = str(e)
        raise Exception(f"Failed to write data to worksheet: {error_msg}") from e
    
    # Make spreadsheet shareable (optional - for testing)
    try:
        # Share with anyone with the link (view only)
        spreadsheet.share('', perm_type='anyone', role='reader')
        print(f"✅ Spreadsheet shared (anyone with link can view)")
    except APIError as e:
        error_msg = str(e)
        print(f"⚠️  Warning: Could not share spreadsheet: {error_msg}")
        print(f"   You may need to share it manually if needed for testing")
    except Exception as e:
        print(f"⚠️  Warning: Could not share spreadsheet: {e}")
        print(f"   You may need to share it manually if needed for testing")
    
    # Get spreadsheet URL
    sheet_url = spreadsheet.url
    
    result = {
        'spreadsheet_id': spreadsheet.id,
        'sheet_url': sheet_url,
        'worksheet_name': sheet_name,
        'total_rows': total_rows,
        'valid_rows': 95,
        'invalid_rows': 5,
    }
    
    return result


def main():
    """Main entry point for script."""
    parser = argparse.ArgumentParser(
        description="Create a test Google Sheet with sample product data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create test sheet with default settings
  python scripts/create_test_sheet.py --title "Test Price List"
  
  # Create test sheet with custom credentials
  python scripts/create_test_sheet.py --title "Test Price List" \\
      --credentials-path /path/to/credentials.json
  
  # Create test sheet with custom worksheet name
  python scripts/create_test_sheet.py --title "Test Price List" \\
      --sheet-name "November 2025"
  
  # Use existing spreadsheet (workaround for quota/permission issues)
  python scripts/create_test_sheet.py \\
      --use-existing "https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit" \\
      --sheet-name "Sheet1"
        """
    )
    
    parser.add_argument(
        '--title',
        type=str,
        default=f"Test Price List - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        help='Title for the spreadsheet (default: auto-generated with timestamp)'
    )
    
    parser.add_argument(
        '--credentials-path',
        type=str,
        default=None,
        help='Path to Google service account credentials JSON file (default: from settings)'
    )
    
    parser.add_argument(
        '--sheet-name',
        type=str,
        default='Sheet1',
        help='Name of the worksheet tab (default: Sheet1)'
    )
    
    parser.add_argument(
        '--use-existing',
        type=str,
        default=None,
        metavar='URL',
        help='URL of existing spreadsheet to populate (bypasses creation)'
    )
    
    args = parser.parse_args()
    
    try:
        result = create_test_sheet(
            title=args.title,
            credentials_path=args.credentials_path,
            sheet_name=args.sheet_name,
            existing_spreadsheet_url=args.use_existing
        )
        
        print("\n" + "=" * 70)
        print("✅ Test Sheet Created Successfully!")
        print("=" * 70)
        print(f"\n📋 Spreadsheet Details:")
        print(f"   Title: {args.title}")
        print(f"   ID: {result['spreadsheet_id']}")
        print(f"   URL: {result['sheet_url']}")
        print(f"   Worksheet: {result['worksheet_name']}")
        print(f"\n📊 Data Summary:")
        print(f"   Total rows: {result['total_rows']}")
        print(f"   Valid rows: {result['valid_rows']} (with all fields)")
        print(f"   Invalid rows: {result['invalid_rows']} (missing price)")
        print(f"\n🔗 Next Steps:")
        print(f"   1. Verify the sheet at: {result['sheet_url']}")
        print(f"   2. Test parser with:")
        print(f"      python scripts/enqueue_task.py \\")
        print(f"          --task-id test-001 \\")
        print(f"          --parser-type google_sheets \\")
        print(f"          --supplier-name 'Test Supplier' \\")
        print(f"          --sheet-url '{result['sheet_url']}'")
        print("=" * 70)
        
        return 0
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        return 1
    except APIError as e:
        error_msg = str(e)
        print(f"\n❌ Google Sheets API Error: {error_msg}", file=sys.stderr)
        if "quota" in error_msg.lower() or "storage" in error_msg.lower():
            print(f"\n💡 Tip: Free up space in your Google Drive or upgrade your storage plan.", file=sys.stderr)
        return 1
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ Error: {error_msg}", file=sys.stderr)
        # Only print full traceback for unexpected errors (not user-friendly errors)
        if "quota" not in error_msg.lower() and "storage" not in error_msg.lower():
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

