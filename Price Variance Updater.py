"""
Price Variance Updater (OPTIMIZED)
Reads from StoreDB inventory and Price Update.xlsx and updates inventory AND price on Reverb for multiple stores.

Price Update Logic:
- If Posted Price is 0 or empty, skip price update (don't change Reverb price)
- If price difference (in either direction) is $50 OR MORE, update the price on Reverb AND add to review Excel file
- If price difference is LESS than $50, update the price on Reverb normally

SPEED OPTIMIZATIONS:
- Combined inventory + price updates in single API call
- FAST_MODE option to skip validation (much faster)
- Reduced delays between products
- Trust API response (200 = success) instead of re-validating each update

DATA SAFETY:
- Price Variance Review Excel file is saved after EACH STORE completes
- Data is preserved even if script crashes or is interrupted
"""

import pandas as pd
import requests
import logging
import sys
import time
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from collections import defaultdict

# Configuration
EXCEL_FILE_PATH = r'C:\Users\Navroz\OneDrive\Desktop\Reverb Work\StoreDB inventory and Price Update.xlsx'
REVERB_API_BASE_URL = 'https://api.reverb.com/api'

# Output directory for price variance review file
PRICE_VARIANCE_OUTPUT_DIR = r'C:\Users\Navroz\OneDrive\Desktop\Reverb Work\Price vary Sku update Folder'

# Price variance threshold (in dollars)
PRICE_VARIANCE_THRESHOLD = 50.0

# ============================================================================
# SPEED SETTINGS - Adjust these to control speed vs accuracy tradeoff
# ============================================================================

# FAST_MODE: Set to True for faster processing (skips validation)
# - True: ~3-4x faster, trusts API responses, no validation
# - False: Slower but validates each inventory update
FAST_MODE = True

# Delay between products (in seconds)
# - Reverb allows ~50 requests per 2 minutes
# - 1.5 seconds is safe and fast
# - Increase to 2.4 if you get rate limited
DELAY_PER_PRODUCT = 1.5

# Sample validation: Only validate every Nth update (only used if FAST_MODE = False)
# - Set to 1 to validate every update (slowest)
# - Set to 5 to validate every 5th update
# - Set to 10 to validate every 10th update (faster)
VALIDATE_EVERY_N = 5

# ============================================================================

# Store configurations: {Store Name: API Token}
STORES = {
    'TSS': 'e8a002618b3025827e25510da202fb6567ca86dad1b2221ba42596460418e9f9',
    'GGL': '7bddeec2d92f81371d5842f044fd520d8a0d091b1edc19174d0463693dec90e9',
    'MMS': 'f6fc5ff306fe6440b71d9f0336cbb1dd3a964b330e0569f9699adbec2262711c',
    'MZM': 'e51c6294ec9f81ee489adfe473a5a89f5e02051d3e997dff632f75e8694e5ebb',
    'GG': 'bc5ea36c7a5638a41b84c69f3055ad210f84f41b8116b6498b568f9676d9ead7',
    'AMH': '09b64f54b4e9eb8235b276900eddc24b657b2a235c661d2110b785caaabb6b88'
}


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
    """
    try:
        url = f"{REVERB_API_BASE_URL}/my/listings"
        params = {'sku': sku, 'state': 'all', 'per_page': 1}
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
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
    Update a Reverb listing with combined data (inventory + price in one call).
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


def validate_inventory_update(sku: str, expected_inventory: int, headers: Dict[str, str]) -> bool:
    """
    Validate that inventory was updated correctly (simplified - single check).
    """
    # Short delay before validation
    time.sleep(0.5)
    
    listing = get_listing_by_sku(sku, headers)
    if not listing:
        logging.warning(f"Validation: Could not fetch listing for SKU {sku}")
        return False
    
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
        logging.warning(f"Validation mismatch for SKU {sku}: Expected {expected_inventory}, Got {current_inventory}")
        return False


def calculate_inventory(stock: float) -> int:
    """Use stock value directly as inventory."""
    if pd.isna(stock):
        return 0
    return int(stock)


def normalize_store_name(store_name: str) -> Optional[str]:
    """Normalize store name to match STORES dictionary keys."""
    if pd.isna(store_name):
        return None
    
    name = str(store_name).strip().upper()
    
    if name in STORES:
        return name
    
    for store_key in STORES.keys():
        if store_key in name or name in store_key:
            return store_key
    
    return None


def save_price_variance_review(variance_data: List[Dict], output_dir: str) -> str:
    """Save SKUs with price variance >= $50 to an Excel file for manual review."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logging.info(f"Created output directory: {output_dir}")
    
    today = datetime.now().strftime("%Y-%m-%d")
    output_filename = f"Price Variance Review {today}.xlsx"
    output_path = os.path.join(output_dir, output_filename)
    
    if variance_data:
        df = pd.DataFrame(variance_data)
        column_order = ['STORE NAME', 'SKU', 'REVERB PRICE', 'POSTED PRICE', 'DIFFERENCE', 'DIRECTION']
        df = df[column_order]
        
        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Price Variance Review', index=False)
            
            workbook = writer.book
            worksheet = writer.sheets['Price Variance Review']
            
            money_format = workbook.add_format({'num_format': '$#,##0.00'})
            worksheet.set_column(0, 0, 12)
            worksheet.set_column(1, 1, 30)
            worksheet.set_column(2, 2, 15, money_format)
            worksheet.set_column(3, 3, 15, money_format)
            worksheet.set_column(4, 4, 15, money_format)
            worksheet.set_column(5, 5, 20)
        
        logging.info(f"Saved price variance review file: {output_path}")
    else:
        df = pd.DataFrame(columns=['STORE NAME', 'SKU', 'REVERB PRICE', 'POSTED PRICE', 'DIFFERENCE', 'DIRECTION'])
        df.to_excel(output_path, index=False)
        logging.info(f"No price variances found. Created empty review file: {output_path}")
    
    return output_path


def main():
    """Main execution function."""
    # Setup logging
    log_filename = f'price_variance_updater_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logging.info("=" * 80)
    logging.info("Price Variance Updater (OPTIMIZED) Started")
    logging.info(f"FAST_MODE: {FAST_MODE}")
    logging.info(f"Delay per product: {DELAY_PER_PRODUCT}s")
    if not FAST_MODE:
        logging.info(f"Validate every: {VALIDATE_EVERY_N} updates")
    logging.info(f"Price variance threshold: ${PRICE_VARIANCE_THRESHOLD:.2f}")
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
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading Excel file: {str(e)}")
        print(f"\n❌ ERROR: Could not read Excel file: {str(e)}")
        sys.exit(1)
    
    # Validate required columns
    required_columns = ['STORES NAME', 'SKU', 'STOCK']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        df.columns = [col.strip() for col in df.columns]
        column_map = {col.upper(): col for col in df.columns}
        
        rename_dict = {}
        for req_col in required_columns:
            if req_col.upper() in column_map:
                rename_dict[column_map[req_col.upper()]] = req_col
        
        if rename_dict:
            df.rename(columns=rename_dict, inplace=True)
            logging.info(f"Renamed columns: {rename_dict}")
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logging.error(f"Required columns not found: {missing_columns}")
            print(f"\n❌ ERROR: Required columns missing: {missing_columns}")
            print(f"Available columns: {list(df.columns)}")
            sys.exit(1)
    
    # Find POSTED PRICE column
    price_column = None
    price_keywords = ['POSTED PRICE', 'Posted Price', 'posted price', 'POSTED_PRICE', 
                      'Posted_Price', 'posted_price', 'PRICE', 'Price', 'price']
    
    for col in df.columns:
        col_str = str(col).strip()
        for keyword in price_keywords:
            if keyword.upper() in col_str.upper():
                price_column = col
                logging.info(f"Found POSTED PRICE column: {price_column}")
                break
        if price_column:
            break
    
    if not price_column:
        logging.warning("No POSTED PRICE column found. Only inventory will be updated.")
        print("\n⚠️  WARNING: No POSTED PRICE column found. Only inventory will be updated.")
    
    # Group data by store
    print("\n" + "=" * 80)
    print("📊 PROCESSING DATA BY STORE (OPTIMIZED)")
    print(f"⚡ FAST_MODE: {'ON - Skipping validation for speed' if FAST_MODE else 'OFF - Validating updates'}")
    print(f"⏱️  Delay per product: {DELAY_PER_PRODUCT}s")
    print(f"💰 Price variance threshold: ${PRICE_VARIANCE_THRESHOLD:.2f}")
    print("=" * 80)
    
    df['NORMALIZED_STORE'] = df['STORES NAME'].apply(normalize_store_name)
    
    unknown_stores = df[df['NORMALIZED_STORE'].isna()]
    if len(unknown_stores) > 0:
        logging.warning(f"Found {len(unknown_stores)} rows with unknown store names")
    
    df = df[df['NORMALIZED_STORE'].notna()]
    
    if len(df) == 0:
        logging.error("No valid store names found in the data")
        print("\n❌ ERROR: No valid store names found!")
        sys.exit(1)
    
    grouped = df.groupby('NORMALIZED_STORE')
    
    price_variance_data = []
    
    overall_stats = {
        'total_rows': 0,
        'inventory_updated': 0,
        'inventory_skipped': 0,
        'inventory_validated': 0,
        'inventory_validation_failed': 0,
        'price_updated': 0,
        'price_added_to_review': 0,  # Prices updated with difference >= $50
        'price_skipped_no_change': 0,
        'total_not_found': 0,
        'total_errors': 0,
        'combined_updates': 0  # Track combined inventory+price updates
    }
    
    store_results = {}
    total_stores = len(grouped)
    current_store_number = 0
    overall_start_time = time.time()
    
    # Process each store
    for store_name, store_data in grouped:
        current_store_number += 1
        
        print(f"\n{'='*80}")
        print(f"🏪 STARTING STORE {current_store_number}/{total_stores}: {store_name}")
        print(f"{'='*80}")
        print(f"   Items to process: {len(store_data)}")
        print(f"   Estimated time: ~{len(store_data) * DELAY_PER_PRODUCT / 60:.1f} minutes")
        
        logging.info(f"\nSTARTING Store {current_store_number}/{total_stores}: {store_name}")
        logging.info(f"Items to process: {len(store_data)}")
        
        api_token = STORES.get(store_name)
        if not api_token:
            logging.error(f"No API token found for store: {store_name}")
            print(f"   ❌ ERROR: No API token configured for {store_name}")
            continue
        
        headers = get_headers(api_token)
        
        stats = {
            'total': 0,
            'inventory_updated': 0,
            'inventory_skipped': 0,
            'inventory_validated': 0,
            'inventory_validation_failed': 0,
            'price_updated': 0,
            'price_added_to_review': 0,  # Prices updated with difference >= $50
            'price_skipped_no_change': 0,
            'not_found': 0,
            'errors': 0,
            'combined_updates': 0
        }
        
        store_start_time = time.time()
        update_count = 0  # For sample validation
        
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
            
            # Get POSTED PRICE value
            posted_price = None
            if price_column:
                try:
                    posted_price = float(row[price_column]) if pd.notna(row[price_column]) else None
                except (ValueError, TypeError):
                    posted_price = None
            
            # Show progress
            progress = f"[{stats['total']}/{len(store_data)}]"
            print(f"   {progress} {sku}...", end=' ')
            
            # Get current listing from Reverb
            listing = get_listing_by_sku(sku, headers)
            
            if not listing:
                logging.warning(f"SKU {sku}: Listing not found on Reverb")
                stats['not_found'] += 1
                overall_stats['total_not_found'] += 1
                print("NOT FOUND")
                continue
            
            listing_id = listing.get('id')
            output_parts = []
            
            # Get current inventory
            target_inventory = calculate_inventory(stock)
            inventory = listing.get('inventory', 0)
            if isinstance(inventory, dict):
                current_inventory = inventory.get('quantity', 0)
            else:
                current_inventory = int(inventory) if inventory else 0
            
            # Get current price info
            reverb_price = 0.0
            currency = 'USD'
            price_difference = 0.0
            should_update_price = False
            add_to_review = False  # Flag to track if price update should be added to review file
            
            # Skip price update if posted_price is None, empty, or 0
            if posted_price is not None and posted_price > 0:
                current_price_data = listing.get('price', {})
                if isinstance(current_price_data, dict):
                    reverb_price = float(current_price_data.get('amount', 0))
                    currency = current_price_data.get('currency', 'USD')
                else:
                    reverb_price = float(current_price_data) if current_price_data else 0.0
                
                price_difference = abs(posted_price - reverb_price)
                
                if price_difference >= PRICE_VARIANCE_THRESHOLD:
                    # Update price AND add to review file (50% = $50 difference)
                    should_update_price = True
                    add_to_review = True
                    direction = "INCREASE" if posted_price > reverb_price else "DECREASE"
                    price_variance_data.append({
                        'STORE NAME': store_name,
                        'SKU': sku,
                        'REVERB PRICE': reverb_price,
                        'POSTED PRICE': posted_price,
                        'DIFFERENCE': price_difference,
                        'DIRECTION': direction
                    })
                elif price_difference > 0:
                    # Normal update (difference < $50)
                    should_update_price = True
                else:
                    stats['price_skipped_no_change'] += 1
                    overall_stats['price_skipped_no_change'] += 1
            
            # Determine what to update
            need_inventory_update = current_inventory != target_inventory
            need_price_update = should_update_price
            
            # COMBINED UPDATE - Single API call for both inventory and price
            if need_inventory_update or need_price_update:
                update_data = {}
                
                if need_inventory_update:
                    update_data['inventory'] = target_inventory
                
                if need_price_update:
                    update_data['price'] = {
                        'amount': str(posted_price),
                        'currency': currency
                    }
                
                # Make single API call
                if update_listing(listing_id, update_data, headers):
                    if need_inventory_update:
                        output_parts.append(f"INV:{current_inventory}→{target_inventory}")
                        stats['inventory_updated'] += 1
                        overall_stats['inventory_updated'] += 1
                        update_count += 1
                        
                        # Sample validation (only if not in FAST_MODE)
                        if not FAST_MODE and update_count % VALIDATE_EVERY_N == 0:
                            if validate_inventory_update(sku, target_inventory, headers):
                                stats['inventory_validated'] += 1
                                overall_stats['inventory_validated'] += 1
                                output_parts.append("✓")
                            else:
                                stats['inventory_validation_failed'] += 1
                                overall_stats['inventory_validation_failed'] += 1
                                output_parts.append("⚠️")
                    
                    if need_price_update:
                        if add_to_review:
                            output_parts.append(f"PRICE:${reverb_price:.0f}→${posted_price:.0f}✅ (Added to review)")
                            stats['price_added_to_review'] += 1
                            overall_stats['price_added_to_review'] += 1
                        else:
                            output_parts.append(f"PRICE:${reverb_price:.0f}→${posted_price:.0f}✅")
                        stats['price_updated'] += 1
                        overall_stats['price_updated'] += 1
                    
                    if need_inventory_update and need_price_update:
                        stats['combined_updates'] += 1
                        overall_stats['combined_updates'] += 1
                else:
                    if need_inventory_update:
                        output_parts.append("INV:FAILED")
                    if need_price_update:
                        output_parts.append("PRICE:FAILED")
                    stats['errors'] += 1
                    overall_stats['total_errors'] += 1
            else:
                # No updates needed
                if not need_inventory_update:
                    stats['inventory_skipped'] += 1
                    overall_stats['inventory_skipped'] += 1
                output_parts.append("OK")
            
            # Print output
            print(" | ".join(output_parts) if output_parts else "OK")
            
            # Rate limiting
            time.sleep(DELAY_PER_PRODUCT)
        
        # Store completion
        store_end_time = time.time()
        store_duration = store_end_time - store_start_time
        
        store_results[store_name] = stats
        
        print(f"\n{'='*80}")
        print(f"✅ STORE COMPLETED: {store_name}")
        print(f"{'='*80}")
        print(f"   Total: {stats['total']} | INV Updated: {stats['inventory_updated']} | Price Updated: {stats['price_updated']}")
        print(f"   Combined updates: {stats['combined_updates']} | Not found: {stats['not_found']} | Errors: {stats['errors']}")
        print(f"   Time: {store_duration:.1f}s ({store_duration/60:.1f} min)")
        
        # SAVE VARIANCE FILE AFTER EACH STORE (so data is preserved if script is interrupted)
        if price_variance_data:
            variance_file_path = save_price_variance_review(price_variance_data, PRICE_VARIANCE_OUTPUT_DIR)
            print(f"   💾 Saved {len(price_variance_data)} variance SKUs to file")
        
        if current_store_number < total_stores:
            print(f"\n⏭️  Progress: {current_store_number}/{total_stores} stores completed")
    
    # Final save of price variance review file (in case no variances were found during processing)
    variance_file_path = save_price_variance_review(price_variance_data, PRICE_VARIANCE_OUTPUT_DIR)
    
    # Overall summary
    overall_end_time = time.time()
    total_duration = overall_end_time - overall_start_time
    
    print(f"\n{'='*80}")
    print("🎉 ALL STORES COMPLETED - FINAL SUMMARY")
    print(f"{'='*80}")
    print(f"⚡ Mode: {'FAST (no validation)' if FAST_MODE else 'STANDARD (with validation)'}")
    print(f"⏱️  Total time: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")
    print(f"📊 Products processed: {overall_stats['total_rows']}")
    print(f"   Inventory updated: {overall_stats['inventory_updated']}")
    print(f"   Inventory skipped (no change): {overall_stats['inventory_skipped']}")
    if not FAST_MODE:
        print(f"   Inventory validated: {overall_stats['inventory_validated']}")
        print(f"   Validation failed: {overall_stats['inventory_validation_failed']}")
    print(f"   Price updated: {overall_stats['price_updated']}")
    print(f"   Price updated & added to review (diff >= $50): {overall_stats['price_added_to_review']}")
    print(f"   Price skipped (no change): {overall_stats['price_skipped_no_change']}")
    print(f"   Combined updates (single API call): {overall_stats['combined_updates']}")
    print(f"   Not found: {overall_stats['total_not_found']}")
    print(f"   Errors: {overall_stats['total_errors']}")
    
    if overall_stats['total_rows'] > 0:
        avg_time = total_duration / overall_stats['total_rows']
        print(f"\n⚡ Average time per product: {avg_time:.2f} seconds")
    
    print(f"\n{'='*80}")
    print("💰 PRICE VARIANCE REVIEW")
    print(f"{'='*80}")
    print(f"SKUs with variance > ${PRICE_VARIANCE_THRESHOLD:.2f}: {len(price_variance_data)}")
    print(f"Review file: {variance_file_path}")
    
    print(f"\n📄 Log file: {log_filename}")
    print(f"{'='*80}")
    
    logging.info(f"\nFINAL SUMMARY")
    logging.info(f"Total time: {total_duration:.1f} seconds")
    logging.info(f"Products processed: {overall_stats['total_rows']}")
    logging.info(f"Inventory updated: {overall_stats['inventory_updated']}")
    logging.info(f"Price updated: {overall_stats['price_updated']}")
    logging.info(f"Combined updates: {overall_stats['combined_updates']}")
    logging.info(f"Price variance SKUs: {len(price_variance_data)}")


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
