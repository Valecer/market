import gspread
from pathlib import Path
from typing import List, Optional
from src.config import settings


async def create_test_sheet(
    title: str,
    row_count: int,
    invalid_rows: Optional[List[int]] = None,
) -> str:
    """Create a test Google Sheet with sample data.
    
    Args:
        title: Sheet title
        row_count: Number of data rows
        invalid_rows: List of row numbers (1-indexed) that should have missing price
    
    Returns:
        Google Sheets URL
    """
    gc = gspread.service_account(filename=settings.google_credentials_path)
    
    # Create new spreadsheet
    spreadsheet = gc.create(title)
    
    # Get the first worksheet
    worksheet = spreadsheet.sheet1
    
    # Set headers
    worksheet.update("A1:D1", [["Product Code", "Description", "Unit Price", "Color"]])
    
    # Add data rows
    data = []
    for i in range(1, row_count + 1):
        if invalid_rows and i in invalid_rows:
            # Invalid row: missing price
            data.append([f"SKU-{i:03d}", f"Product {i}", "", "red"])
        else:
            # Valid row
            price = 10.00 + (i * 0.50)
            data.append([f"SKU-{i:03d}", f"Product {i}", str(price), "blue"])
    
    # Batch update
    if data:
        worksheet.update(f"A2:D{row_count + 1}", data)
    
    # Make sheet publicly readable (for testing)
    spreadsheet.share("", perm_type="anyone", role="reader")
    
    return spreadsheet.url