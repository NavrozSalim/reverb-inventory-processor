"""
Reverb Updater Script
Updates Reverb inventory and prices based on Excel file data.
"""

import pandas as pd
import requests
import logging
import sys
import time
import os
from typing import Optional, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
EXCEL_FILE_PATH = r'C:\Users\Navroz\OneDrive\Desktop\Reverb Work\TSS\StoreDB\StoreDB RAW.xlsx'
REVERB_API_BASE_URL = 'https://api.reverb.com/api'

# Store configurations: {Store Name: API Token}
# Load from environment variables (.env file)
STORES = {
    'TSS': os.getenv('TSS_API_TOKEN', ''),
    'GGL': os.getenv('GGL_API_TOKEN', ''),
    'MMS': os.getenv('MMS_API_TOKEN', ''),
    'MZM': os.getenv('MZM_API_TOKEN', ''),
    'GG': os.getenv('GG_API_TOKEN', ''),
    'AMH': os.getenv('AMH_API_TOKEN', '')
}

# Validate that all tokens are loaded
missing_tokens = [store for store, token in STORES.items() if not token]
if missing_tokens:
    print(f"⚠️  WARNING: Missing API tokens for stores: {', '.join(missing_tokens)}")
    print("   Please ensure .env file exists and contains all required tokens.")
    print("   See .env.example for the required format.")

# Rate Limiting Configuration
# 50 products per 2 minutes = 50 products per 120 seconds
PRODUCTS_PER_BATCH = 50
BATCH_DURATION_SECONDS = 120  # 2 minutes
DELAY_PER_PRODUCT = BATCH_DURATION_SECONDS / PRODUCTS_PER_BATCH  # 2.4 seconds per product


def get_headers(api_token: str) -> Dict[str, str]:
    """Get API headers for a given token."""
    return {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/hal+json',
        'Accept-Version': '3.0',
        'Accept': 'application/hal+json'
    }


def get_listing_by_sku(sku: str, headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """
    Retrieve a listing from Reverb by SKU.
    
    Args:
        sku: The SKU to search for
        
    Returns:
        Listing dictionary if found, None otherwise
    """
    try:
        url = f"{REVERB_API_BASE_URL}/my/listings"
        params = {'sku': sku, 'state': 'all', 'per_page': 1}
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            # Handle different API response formats
            listings = None
            if '_embedded' in data and 'listings' in data['_embedded']:
                listings = data['_embedded']['listings']
            elif 'listings' in data:
                listings = data['listings']
            
            if listings and len(listings) > 0:
                return listings[0]
            return None
        elif response.status_code == 401:
            logging.error(f"Authentication failed. Please check your API token.")
            return None
        else:
            logging.warning(f"API returned status {response.status_code} for SKU {sku}: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching listing for SKU {sku}: {str(e)}")
        return None


def update_listing(listing_id: str, update_data: Dict[str, Any], headers: Dict[str, str]) -> bool:
    """
    Update a Reverb listing.
    
    Args:
        listing_id: The ID of the listing to update
        update_data: Dictionary containing fields to update
        
    Returns:
        True if update was successful, False otherwise
    """
    try:
        url = f"{REVERB_API_BASE_URL}/listings/{listing_id}"
        response = requests.put(url, headers=headers, json=update_data, timeout=30)
        
        if response.status_code == 200:
            return True
        else:
            logging.error(f"Failed to update listing {listing_id}: Status {response.status_code}, Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Error updating listing {listing_id}: {str(e)}")
        return False


def validate_inventory_update(sku: str, expected_inventory: int, headers: Dict[str, str], max_retries: int = 3) -> bool:
    """
    Validate that inventory was updated correctly by fetching the listing again.
    
    Args:
        sku: The SKU to validate
        expected_inventory: The expected inventory value
        headers: API headers with authorization
        max_retries: Maximum number of validation attempts
        
    Returns:
        True if validation successful, False otherwise
    """
    for attempt in range(max_retries):
        # Wait a bit before validating to ensure API has processed the update
        time.sleep(1)
        
        listing = get_listing_by_sku(sku, headers)
        if not listing:
            logging.warning(f"Validation failed for SKU {sku}: Could not fetch listing (attempt {attempt + 1}/{max_retries})")
            continue
        
        # Get current inventory
        inventory = listing.get('inventory', 0)
        if isinstance(inventory, dict):
            current_inventory = inventory.get('quantity', 0)
        else:
            current_inventory = int(inventory) if inventory else 0
        
        if current_inventory == expected_inventory:
            logging.info(f"✓ Validation successful for SKU {sku}: Inventory is {current_inventory}")
            return True
        else:
            logging.warning(f"Validation mismatch for SKU {sku}: Expected {expected_inventory}, Got {current_inventory} (attempt {attempt + 1}/{max_retries})")
    
    return False


def calculate_inventory(stock: float) -> int:
    """
    Calculate Reverb inventory based on stock level.
    
    Args:
        stock: Stock quantity from Excel
        
    Returns:
        Inventory level for Reverb (0, 1, or 2)
    """
    if pd.isna(stock) or stock < 7:
        return 0  # Out of Stock
    elif 7 <= stock <= 10:
        return 1
    else:  # stock > 10
        return 2


def find_price_column(df: pd.DataFrame) -> Optional[str]:
    """
    Find the price column in the DataFrame.
    Looks for common price column names.
    
    Args:
        df: DataFrame to search
        
    Returns:
        Column name if found, None otherwise
    """
    price_keywords = ['price', 'Price', 'PRICE', 'cost', 'Cost', 'COST', 
                      'amount', 'Amount', 'AMOUNT', 'value', 'Value', 'VALUE']
    
    for col in df.columns:
        if any(keyword in str(col) for keyword in price_keywords):
            return col
    
    return None


def select_store():
    """Prompt user to select a store."""
    print("\n" + "=" * 60)
    print("🏪 AVAILABLE STORES")
    print("=" * 60)
    store_list = list(STORES.keys())
    for i, store in enumerate(store_list, 1):
        print(f"{i}. {store}")
    
    while True:
        try:
            choice = input(f"\nSelect store (1-{len(store_list)}) or store name: ").strip()
            # Try as number first
            if choice.isdigit() and 1 <= int(choice) <= len(store_list):
                selected_store = store_list[int(choice) - 1]
                break
            # Try as store name
            elif choice.upper() in STORES:
                selected_store = choice.upper()
                break
            else:
                print(f"❌ Invalid selection. Please enter 1-{len(store_list)} or store name.")
        except (ValueError, KeyboardInterrupt):
            print("\n❌ Invalid input. Exiting.")
            sys.exit(1)
    
    api_token = STORES[selected_store]
    print(f"✅ Selected store: {selected_store}")
    return selected_store, api_token


def main():
    """Main execution function."""
    # Select store first
    store_name, api_token = select_store()
    headers = get_headers(api_token)
    
    # Setup logging with store name in filename
    log_filename = f'reverb_updater_{store_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logging.info("=" * 60)
    logging.info("Reverb Updater Script Started")
    logging.info(f"Store: {store_name}")
    logging.info(f"Rate limit: {PRODUCTS_PER_BATCH} products per {BATCH_DURATION_SECONDS} seconds")
    logging.info(f"Delay per product: {DELAY_PER_PRODUCT:.2f} seconds")
    logging.info("=" * 60)
    
    print("\n" + "=" * 60)
    print(f"⚙️  Rate Limiting Configuration:")
    print(f"   {PRODUCTS_PER_BATCH} products per {BATCH_DURATION_SECONDS} seconds")
    print(f"   {DELAY_PER_PRODUCT:.2f} seconds delay per product")
    print("=" * 60)
    
    # Read Excel file - try to read the sheet matching store name
    try:
        logging.info(f"Reading Excel file: {EXCEL_FILE_PATH}")
        logging.info(f"Looking for sheet: {store_name}")
        
        # Try to read the specific sheet first
        try:
            df = pd.read_excel(EXCEL_FILE_PATH, sheet_name=store_name, engine='openpyxl')
            logging.info(f"Successfully loaded sheet '{store_name}' with {len(df)} rows")
        except ValueError:
            # If sheet doesn't exist, try reading first sheet
            logging.warning(f"Sheet '{store_name}' not found. Reading first available sheet...")
            df = pd.read_excel(EXCEL_FILE_PATH, engine='openpyxl')
            logging.info(f"Successfully loaded {len(df)} rows from Excel file")
    except FileNotFoundError:
        logging.error(f"Excel file not found: {EXCEL_FILE_PATH}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading Excel file: {str(e)}")
        sys.exit(1)
    
    # Validate required columns
    if 'SKU' not in df.columns:
        logging.error("Required column 'SKU' not found in Excel file")
        logging.info(f"Available columns: {list(df.columns)}")
        sys.exit(1)
    
    if 'Stock' not in df.columns:
        logging.error("Required column 'Stock' not found in Excel file")
        logging.info(f"Available columns: {list(df.columns)}")
        sys.exit(1)
    
    # Find price column
    price_column = find_price_column(df)
    if not price_column:
        logging.error("Price column not found. Please ensure a column with 'price' in the name exists.")
        logging.info(f"Available columns: {list(df.columns)}")
        sys.exit(1)
    
    logging.info(f"Using price column: {price_column}")
    logging.info(f"Using API token for store: {store_name}")
    
    # Statistics tracking
    stats = {
        'total': 0,
        'inventory_updated': 0,
        'inventory_skipped': 0,
        'inventory_validated': 0,
        'inventory_validation_failed': 0,
        'price_updated': 0,
        'price_skipped': 0,
        'not_found': 0,
        'errors': 0
    }
    
    # Track processing time
    start_time = time.time()
    
    # Process each row
    total_rows = len(df)
    logging.info(f"\nProcessing {total_rows} products...")
    print(f"\nProcessing {total_rows} products...\n")
    
    for index, row in df.iterrows():
        stats['total'] += 1
        sku = str(row['SKU']).strip() if pd.notna(row['SKU']) else None
        
        if not sku or sku == 'nan':
            logging.warning(f"Row {index + 1}: Skipping row with invalid SKU")
            stats['errors'] += 1
            continue
        
        # Get stock value
        try:
            stock = float(row['Stock']) if pd.notna(row['Stock']) else 0
        except (ValueError, TypeError):
            logging.warning(f"SKU {sku}: Invalid stock value, defaulting to 0")
            stock = 0
        
        # Get price value
        try:
            excel_price = float(row[price_column]) if pd.notna(row[price_column]) else None
        except (ValueError, TypeError):
            logging.warning(f"SKU {sku}: Invalid price value, skipping price update")
            excel_price = None
        
        # Show progress
        progress = f"[{stats['total']}/{total_rows}]"
        print(f"{progress} Processing SKU: {sku}...", end=' ')
        
        # Get current listing from Reverb
        listing = get_listing_by_sku(sku, headers)
        
        if not listing:
            logging.warning(f"SKU {sku}: Listing not found on Reverb")
            stats['not_found'] += 1
            print("NOT FOUND")
            continue
        
        listing_id = listing.get('id')
        listing_title = listing.get('title', 'Unknown')
        
        # TASK 1: Update Inventory
        target_inventory = calculate_inventory(stock)
        # Handle inventory - both int and dict formats
        inventory = listing.get('inventory', 0)
        if isinstance(inventory, dict):
            current_inventory = inventory.get('quantity', 0)
        else:
            current_inventory = int(inventory) if inventory else 0
        
        if current_inventory != target_inventory:
            # API expects inventory as integer directly, not nested dict
            inventory_data = {'inventory': target_inventory}
            if update_listing(listing_id, inventory_data, headers):
                logging.info(f"SKU {sku}: Updated inventory from {current_inventory} to {target_inventory} (Stock: {stock})")
                print(f"INVENTORY: {current_inventory}→{target_inventory}", end=' ')
                
                # Validate the update
                print("| Validating...", end=' ')
                if validate_inventory_update(sku, target_inventory, headers):
                    stats['inventory_validated'] += 1
                    print("✓", end=' ')
                else:
                    stats['inventory_validation_failed'] += 1
                    print("⚠️ VAL-FAILED", end=' ')
                    logging.error(f"SKU {sku}: Inventory validation failed")
                
                stats['inventory_updated'] += 1
            else:
                logging.error(f"SKU {sku}: Failed to update inventory")
                stats['errors'] += 1
                print("INVENTORY UPDATE FAILED", end=' ')
        else:
            logging.info(f"SKU {sku}: Inventory already correct ({target_inventory})")
            stats['inventory_skipped'] += 1
            print(f"INVENTORY: {target_inventory} (no change)", end=' ')
        
        # TASK 2: Update Price
        if excel_price is not None:
            try:
                # Extract current price from Reverb listing - handle both formats
                current_price_data = listing.get('price', {})
                if isinstance(current_price_data, dict):
                    current_reverb_price = float(current_price_data.get('amount', 0))
                    currency = current_price_data.get('currency', 'USD')
                else:
                    current_reverb_price = float(current_price_data) if current_price_data else 0.0
                    currency = 'USD'
                
                # Only update if current Reverb price < Excel price
                if current_reverb_price < excel_price:
                    price_data = {
                        'price': {
                            'amount': str(excel_price),
                            'currency': currency
                        }
                    }
                    if update_listing(listing_id, price_data, headers):
                        logging.info(f"SKU {sku}: Updated price from ${current_reverb_price:.2f} to ${excel_price:.2f}")
                        stats['price_updated'] += 1
                        print(f"PRICE: ${current_reverb_price:.2f}→${excel_price:.2f}")
                    else:
                        logging.error(f"SKU {sku}: Failed to update price")
                        stats['errors'] += 1
                        print("PRICE UPDATE FAILED")
                else:
                    logging.info(f"SKU {sku}: Price update skipped (Reverb: ${current_reverb_price:.2f} >= Excel: ${excel_price:.2f})")
                    stats['price_skipped'] += 1
                    print(f"PRICE: ${current_reverb_price:.2f} (no change)")
            except (ValueError, TypeError, KeyError) as e:
                logging.warning(f"SKU {sku}: Error processing price - {str(e)}")
                stats['errors'] += 1
                print("PRICE ERROR")
        else:
            logging.info(f"SKU {sku}: Skipping price update (no valid price in Excel)")
            print("PRICE: SKIPPED")
        
        print()  # New line after each product
        
        # Rate limiting: Wait before next product
        time.sleep(DELAY_PER_PRODUCT)
    
    # Calculate processing time
    end_time = time.time()
    duration = end_time - start_time
    
    # Calculate accuracy
    inventory_accuracy = 0
    if stats['inventory_updated'] > 0:
        inventory_accuracy = (stats['inventory_validated'] / stats['inventory_updated']) * 100
    
    # Print summary
    logging.info("\n" + "=" * 60)
    logging.info("UPDATE SUMMARY")
    logging.info("=" * 60)
    logging.info(f"Total products processed: {stats['total']}")
    logging.info(f"Inventory updates: {stats['inventory_updated']}")
    logging.info(f"Inventory validated: {stats['inventory_validated']}")
    logging.info(f"Inventory validation failed: {stats['inventory_validation_failed']}")
    logging.info(f"Inventory skipped (no change): {stats['inventory_skipped']}")
    logging.info(f"Price updates: {stats['price_updated']}")
    logging.info(f"Price skipped (no change needed): {stats['price_skipped']}")
    logging.info(f"Listings not found: {stats['not_found']}")
    logging.info(f"Errors encountered: {stats['errors']}")
    if stats['inventory_updated'] > 0:
        logging.info(f"Validation accuracy: {inventory_accuracy:.1f}%")
    logging.info(f"Time taken: {duration:.2f} seconds ({duration/60:.2f} minutes)")
    logging.info(f"Store: {store_name}")
    logging.info(f"Log file saved to: {log_filename}")
    logging.info("=" * 60)
    
    print("\n" + "=" * 60)
    print("✅ UPDATE COMPLETE - SUMMARY")
    print("=" * 60)
    print(f"Store: {store_name}")
    print(f"Total products processed: {stats['total']}")
    print(f"Inventory updates: {stats['inventory_updated']}")
    print(f"Inventory validated: {stats['inventory_validated']}")
    print(f"Inventory validation failed: {stats['inventory_validation_failed']}")
    print(f"Inventory skipped (no change): {stats['inventory_skipped']}")
    print(f"Price updates: {stats['price_updated']}")
    print(f"Price skipped (no change needed): {stats['price_skipped']}")
    print(f"Listings not found: {stats['not_found']}")
    print(f"Errors encountered: {stats['errors']}")
    
    if stats['inventory_updated'] > 0:
        print(f"\n✓ Validation accuracy: {inventory_accuracy:.1f}%")
        if inventory_accuracy == 100.0:
            print("  🎯 PERFECT ACCURACY! All updates verified successfully!")
        elif inventory_accuracy >= 95.0:
            print("  ✅ Excellent accuracy!")
        elif inventory_accuracy >= 90.0:
            print("  ⚠️  Good accuracy, but some validations failed")
        else:
            print("  ⚠️  WARNING: Low validation accuracy - please review logs")
    
    print(f"\n⏱️  Time taken: {duration:.2f} seconds ({duration/60:.2f} minutes)")
    print(f"📄 Log file saved to: {log_filename}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("\nScript interrupted by user")
        print("\n\nScript interrupted by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}", exc_info=True)
        print(f"\n\nUnexpected error: {str(e)}")
        sys.exit(1)

