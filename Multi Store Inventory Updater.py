"""
Multi-Store Inventory Updater
Reads from StoreDB inventory Update.xlsx and updates inventory on Reverb for multiple stores.
"""

import pandas as pd
import requests
import logging
import sys
import time
import os
from typing import Optional, Dict, Any
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
EXCEL_FILE_PATH = r'C:\Users\Navroz\OneDrive\Desktop\Reverb Work\StoreDB inventory Update.xlsx'
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
        headers: API headers with authorization
        
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
            logging.error(f"Authentication failed for SKU {sku}. Please check your API token.")
            return None
        else:
            logging.warning(f"API returned status {response.status_code} for SKU {sku}")
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
        headers: API headers with authorization
        
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
    Use stock value directly as inventory.
    
    Args:
        stock: Stock quantity from Excel
        
    Returns:
        Stock value as integer for Reverb inventory
    """
    if pd.isna(stock):
        return 0
    return int(stock)


def normalize_store_name(store_name: str) -> Optional[str]:
    """
    Normalize store name to match STORES dictionary keys.
    
    Args:
        store_name: Store name from Excel
        
    Returns:
        Normalized store name or None if not found
    """
    if pd.isna(store_name):
        return None
    
    # Convert to string and strip whitespace
    name = str(store_name).strip().upper()
    
    # Direct match
    if name in STORES:
        return name
    
    # Try partial matches
    for store_key in STORES.keys():
        if store_key in name or name in store_key:
            return store_key
    
    return None


def main():
    """Main execution function."""
    # Setup logging
    log_filename = f'multi_store_updater_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logging.info("=" * 80)
    logging.info("Multi-Store Inventory Updater Started")
    logging.info("=" * 80)
    
    # Read Excel file
    try:
        logging.info(f"Reading Excel file: {EXCEL_FILE_PATH}")
        df = pd.read_excel(EXCEL_FILE_PATH, engine='openpyxl')
        logging.info(f"Successfully loaded {len(df)} rows from Excel file")
    except FileNotFoundError:
        logging.error(f"Excel file not found: {EXCEL_FILE_PATH}")
        print(f"\n❌ ERROR: Excel file not found!")
        print(f"Expected file: {EXCEL_FILE_PATH}")
        print(f"Please ensure the file exists at this location.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading Excel file: {str(e)}")
        print(f"\n❌ ERROR: Could not read Excel file: {str(e)}")
        sys.exit(1)
    
    # Validate required columns
    required_columns = ['STORES NAME', 'SKU', 'STOCK']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        # Try case-insensitive match
        df.columns = [col.strip() for col in df.columns]
        column_map = {col.upper(): col for col in df.columns}
        
        # Rename columns to standard format
        rename_dict = {}
        for req_col in required_columns:
            if req_col.upper() in column_map:
                rename_dict[column_map[req_col.upper()]] = req_col
        
        if rename_dict:
            df.rename(columns=rename_dict, inplace=True)
            logging.info(f"Renamed columns: {rename_dict}")
        
        # Check again
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logging.error(f"Required columns not found: {missing_columns}")
            logging.info(f"Available columns: {list(df.columns)}")
            print(f"\n❌ ERROR: Required columns missing: {missing_columns}")
            print(f"Available columns: {list(df.columns)}")
            sys.exit(1)
    
    logging.info(f"Columns found: {list(df.columns)}")
    
    # Group data by store
    print("\n" + "=" * 80)
    print("📊 PROCESSING DATA BY STORE")
    print("=" * 80)
    
    # Normalize store names and group
    df['NORMALIZED_STORE'] = df['STORES NAME'].apply(normalize_store_name)
    
    # Remove rows with unknown stores
    unknown_stores = df[df['NORMALIZED_STORE'].isna()]
    if len(unknown_stores) > 0:
        logging.warning(f"Found {len(unknown_stores)} rows with unknown store names:")
        for idx, row in unknown_stores.iterrows():
            logging.warning(f"  Row {idx + 1}: '{row['STORES NAME']}'")
    
    df = df[df['NORMALIZED_STORE'].notna()]
    
    if len(df) == 0:
        logging.error("No valid store names found in the data")
        print("\n❌ ERROR: No valid store names found!")
        print(f"Valid stores are: {', '.join(STORES.keys())}")
        sys.exit(1)
    
    # Group by normalized store name
    grouped = df.groupby('NORMALIZED_STORE')
    
    # Overall statistics
    overall_stats = {
        'total_rows': 0,
        'total_updated': 0,
        'total_skipped': 0,
        'total_not_found': 0,
        'total_errors': 0,
        'total_validated': 0,
        'total_validation_failed': 0
    }
    
    store_results = {}
    total_stores = len(grouped)
    current_store_number = 0
    
    # Process each store
    for store_name, store_data in grouped:
        current_store_number += 1
        
        print(f"\n{'='*80}")
        print(f"🏪 STARTING STORE {current_store_number}/{total_stores}: {store_name}")
        print(f"{'='*80}")
        print(f"   Items to process: {len(store_data)}")
        print(f"   Rate limit: {PRODUCTS_PER_BATCH} products per {BATCH_DURATION_SECONDS} seconds")
        print(f"   Delay per product: {DELAY_PER_PRODUCT:.2f} seconds")
        
        logging.info(f"\n{'='*80}")
        logging.info(f"STARTING Store {current_store_number}/{total_stores}: {store_name}")
        logging.info(f"{'='*80}")
        logging.info(f"Items to process: {len(store_data)}")
        logging.info(f"Rate limit: {PRODUCTS_PER_BATCH} products per {BATCH_DURATION_SECONDS} seconds")
        
        # Get API token for this store
        api_token = STORES.get(store_name)
        if not api_token:
            logging.error(f"No API token found for store: {store_name}")
            print(f"   ❌ ERROR: No API token configured for {store_name}")
            continue
        
        headers = get_headers(api_token)
        
        # Store statistics
        stats = {
            'total': 0,
            'updated': 0,
            'skipped': 0,
            'not_found': 0,
            'errors': 0,
            'validated': 0,
            'validation_failed': 0
        }
        
        # Track time for rate limiting
        store_start_time = time.time()
        
        # Process each row for this store
        for index, row in store_data.iterrows():
            stats['total'] += 1
            overall_stats['total_rows'] += 1
            
            sku = str(row['SKU']).strip() if pd.notna(row['SKU']) else None
            
            if not sku or sku == 'nan':
                logging.warning(f"Row {index + 1}: Skipping row with invalid SKU")
                stats['errors'] += 1
                overall_stats['total_errors'] += 1
                continue
            
            # Get stock value
            try:
                stock = float(row['STOCK']) if pd.notna(row['STOCK']) else 0
            except (ValueError, TypeError):
                logging.warning(f"SKU {sku}: Invalid stock value, defaulting to 0")
                stock = 0
            
            # Show progress
            progress = f"[{stats['total']}/{len(store_data)}]"
            print(f"   {progress} Processing SKU: {sku} (Stock: {stock})...", end=' ')
            
            # Get current listing from Reverb
            listing = get_listing_by_sku(sku, headers)
            
            if not listing:
                logging.warning(f"SKU {sku}: Listing not found on Reverb")
                stats['not_found'] += 1
                overall_stats['total_not_found'] += 1
                print("NOT FOUND")
                continue
            
            listing_id = listing.get('id')
            
            # Calculate target inventory
            target_inventory = calculate_inventory(stock)
            
            # Get current inventory
            inventory = listing.get('inventory', 0)
            if isinstance(inventory, dict):
                current_inventory = inventory.get('quantity', 0)
            else:
                current_inventory = int(inventory) if inventory else 0
            
            # Update if different
            if current_inventory != target_inventory:
                inventory_data = {'inventory': target_inventory}
                if update_listing(listing_id, inventory_data, headers):
                    logging.info(f"SKU {sku}: Updated inventory from {current_inventory} to {target_inventory} (Stock: {stock})")
                    print(f"✅ UPDATED: {current_inventory}→{target_inventory}", end=' ')
                    
                    # Validate the update
                    print("| Validating...", end=' ')
                    if validate_inventory_update(sku, target_inventory, headers):
                        stats['validated'] += 1
                        overall_stats['total_validated'] += 1
                        print("✓ VERIFIED")
                    else:
                        stats['validation_failed'] += 1
                        overall_stats['total_validation_failed'] += 1
                        print("⚠️  VALIDATION FAILED")
                        logging.error(f"SKU {sku}: Validation failed - inventory may not be {target_inventory}")
                    
                    stats['updated'] += 1
                    overall_stats['total_updated'] += 1
                else:
                    logging.error(f"SKU {sku}: Failed to update inventory")
                    stats['errors'] += 1
                    overall_stats['total_errors'] += 1
                    print("❌ FAILED")
            else:
                logging.info(f"SKU {sku}: Inventory already correct ({target_inventory})")
                stats['skipped'] += 1
                overall_stats['total_skipped'] += 1
                print(f"⏭️  SKIPPED (already {target_inventory})")
            
            # Rate limiting: Wait before next product
            time.sleep(DELAY_PER_PRODUCT)
        
        # Store completion
        store_end_time = time.time()
        store_duration = store_end_time - store_start_time
        
        store_results[store_name] = stats
        
        print(f"\n{'='*80}")
        print(f"✅ STORE COMPLETED: {store_name}")
        print(f"{'='*80}")
        print(f"   📊 Summary:")
        print(f"      Total processed: {stats['total']}")
        print(f"      Updated: {stats['updated']}")
        print(f"      Validated: {stats['validated']}")
        print(f"      Validation failed: {stats['validation_failed']}")
        print(f"      Skipped (no change): {stats['skipped']}")
        print(f"      Not found: {stats['not_found']}")
        print(f"      Errors: {stats['errors']}")
        print(f"      Time taken: {store_duration:.2f} seconds ({store_duration/60:.2f} minutes)")
        
        # Show accuracy percentage
        if stats['updated'] > 0:
            accuracy = (stats['validated'] / stats['updated']) * 100
            print(f"      ✓ Validation accuracy: {accuracy:.1f}%")
        
        print(f"{'='*80}")
        
        # Show next store message if not the last one
        if current_store_number < total_stores:
            next_store = list(grouped.groups.keys())[current_store_number]
            print(f"\n⏭️  Moving to next store: {next_store}")
            print(f"   Progress: {current_store_number}/{total_stores} stores completed\n")
        
        logging.info(f"\n{'='*80}")
        logging.info(f"STORE COMPLETED: {store_name}")
        logging.info(f"{'='*80}")
        logging.info(f"Total processed: {stats['total']}")
        logging.info(f"Updated: {stats['updated']}")
        logging.info(f"Validated: {stats['validated']}")
        logging.info(f"Validation failed: {stats['validation_failed']}")
        logging.info(f"Skipped: {stats['skipped']}")
        logging.info(f"Not found: {stats['not_found']}")
        logging.info(f"Errors: {stats['errors']}")
        logging.info(f"Time taken: {store_duration:.2f} seconds")
        if stats['updated'] > 0:
            accuracy = (stats['validated'] / stats['updated']) * 100
            logging.info(f"Validation accuracy: {accuracy:.1f}%")
    
    # Print overall summary
    print(f"\n{'='*80}")
    print("🎉 ALL STORES COMPLETED - FINAL SUMMARY")
    print(f"{'='*80}")
    print(f"Total rows processed: {overall_stats['total_rows']}")
    print(f"Total updates: {overall_stats['total_updated']}")
    print(f"Total validated: {overall_stats['total_validated']}")
    print(f"Total validation failed: {overall_stats['total_validation_failed']}")
    print(f"Total skipped: {overall_stats['total_skipped']}")
    print(f"Total not found: {overall_stats['total_not_found']}")
    print(f"Total errors: {overall_stats['total_errors']}")
    
    # Overall accuracy
    if overall_stats['total_updated'] > 0:
        overall_accuracy = (overall_stats['total_validated'] / overall_stats['total_updated']) * 100
        print(f"\n✓ Overall validation accuracy: {overall_accuracy:.1f}%")
        if overall_accuracy == 100.0:
            print("  🎯 PERFECT ACCURACY! All updates verified successfully!")
        elif overall_accuracy >= 95.0:
            print("  ✅ Excellent accuracy!")
        elif overall_accuracy >= 90.0:
            print("  ⚠️  Good accuracy, but some validations failed")
        else:
            print("  ⚠️  WARNING: Low validation accuracy - please review logs")
    
    print(f"\n📊 Stores processed: {len(store_results)}")
    
    for store_name, stats in store_results.items():
        accuracy = (stats['validated'] / stats['updated'] * 100) if stats['updated'] > 0 else 0
        print(f"\n  🏪 {store_name}:")
        print(f"     Processed: {stats['total']}")
        print(f"     Updated: {stats['updated']}")
        print(f"     Validated: {stats['validated']}")
        print(f"     Skipped: {stats['skipped']}")
        print(f"     Accuracy: {accuracy:.1f}%")
    
    print(f"\n📄 Log file saved to: {log_filename}")
    print(f"{'='*80}")
    
    logging.info(f"\n{'='*80}")
    logging.info("ALL STORES COMPLETED - FINAL SUMMARY")
    logging.info(f"{'='*80}")
    logging.info(f"Total rows processed: {overall_stats['total_rows']}")
    logging.info(f"Total updates: {overall_stats['total_updated']}")
    logging.info(f"Total validated: {overall_stats['total_validated']}")
    logging.info(f"Total validation failed: {overall_stats['total_validation_failed']}")
    logging.info(f"Total skipped: {overall_stats['total_skipped']}")
    logging.info(f"Total not found: {overall_stats['total_not_found']}")
    logging.info(f"Total errors: {overall_stats['total_errors']}")
    if overall_stats['total_updated'] > 0:
        overall_accuracy = (overall_stats['total_validated'] / overall_stats['total_updated']) * 100
        logging.info(f"Overall validation accuracy: {overall_accuracy:.1f}%")
    logging.info(f"Stores processed: {len(store_results)}")
    logging.info(f"Log file saved to: {log_filename}")
    logging.info(f"{'='*80}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("\nScript interrupted by user")
        print("\n\n⚠️  Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}", exc_info=True)
        print(f"\n\n❌ Unexpected error: {str(e)}")
        sys.exit(1)

