"""
Test Script - Single SKU Reverb API Test
Tests if the Reverb API connection and updates work correctly for one SKU.
"""

import requests
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
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


def get_headers(api_token: str) -> dict:
    """Get API headers for a given token."""
    return {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/hal+json',
        'Accept-Version': '3.0',
        'Accept': 'application/hal+json'
    }


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


def get_listing_by_sku(sku: str, headers: dict):
    """Get listing from Reverb by SKU."""
    try:
        url = f"{REVERB_API_BASE_URL}/my/listings"
        params = {'sku': sku, 'state': 'all', 'per_page': 1}
        
        print(f"\n🔍 Searching for SKU: {sku}...")
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        print(f"   API Response Status: {response.status_code}")
        
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
            else:
                print(f"   ❌ No listing found for SKU: {sku}")
                return None
        elif response.status_code == 401:
            print(f"   ❌ Authentication failed! Check your API token.")
            return None
        else:
            print(f"   ❌ API Error: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Network Error: {str(e)}")
        return None


def display_listing_info(listing):
    """Display current listing information."""
    print("\n" + "="*60)
    print("📦 CURRENT LISTING INFORMATION")
    print("="*60)
    
    listing_id = listing.get('id', 'N/A')
    title = listing.get('title', 'N/A')
    sku = listing.get('sku', 'N/A')
    
    # Inventory info - handle both int and dict formats
    inventory = listing.get('inventory', 0)
    if isinstance(inventory, dict):
        current_inventory = inventory.get('quantity', 0)
    else:
        current_inventory = int(inventory) if inventory else 0
    
    # Price info - handle both formats
    price_data = listing.get('price', {})
    if isinstance(price_data, dict):
        current_price = price_data.get('amount', '0')
        currency = price_data.get('currency', 'USD')
    else:
        current_price = str(price_data) if price_data else '0'
        currency = 'USD'
    
    # Status
    state = listing.get('state', 'N/A')
    
    print(f"Listing ID: {listing_id}")
    print(f"Title: {title}")
    print(f"SKU: {sku}")
    print(f"State: {state}")
    print(f"Current Inventory: {current_inventory}")
    print(f"Current Price: {currency} ${current_price}")
    print("="*60)


def test_update_inventory(listing_id: str, new_inventory: int, headers: dict):
    """Test updating inventory."""
    print(f"\n🔄 Testing Inventory Update...")
    print(f"   Attempting to set inventory to: {new_inventory}")
    
    try:
        url = f"{REVERB_API_BASE_URL}/listings/{listing_id}"
        # API expects inventory as integer directly, not nested dict
        update_data = {'inventory': new_inventory}
        
        response = requests.put(url, headers=headers, json=update_data, timeout=30)
        
        print(f"   API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ Inventory update successful!")
            return True
        else:
            print(f"   ❌ Inventory update failed")
            print(f"   Response: {response.text[:300]}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Error: {str(e)}")
        return False


def test_update_price(listing_id: str, new_price: float, headers: dict, currency: str = 'USD'):
    """Test updating price."""
    print(f"\n💰 Testing Price Update...")
    print(f"   Attempting to set price to: {currency} ${new_price:.2f}")
    
    try:
        url = f"{REVERB_API_BASE_URL}/listings/{listing_id}"
        update_data = {
            'price': {
                'amount': str(new_price),
                'currency': currency
            }
        }
        
        response = requests.put(url, headers=headers, json=update_data, timeout=30)
        
        print(f"   API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ Price update successful!")
            return True
        else:
            print(f"   ❌ Price update failed")
            print(f"   Response: {response.text[:300]}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Error: {str(e)}")
        return False


def main():
    """Main test function."""
    print("\n" + "="*60)
    print("🧪 REVERB API TEST - SINGLE SKU")
    print("="*60)
    
    # Select store first
    store_name, api_token = select_store()
    headers = get_headers(api_token)
    
    # Get SKU from command line or prompt
    if len(sys.argv) > 1:
        sku = sys.argv[1]
    else:
        sku = input("\nEnter SKU to test: ").strip()
    
    if not sku:
        print("❌ No SKU provided. Exiting.")
        return
    
    # Step 1: Get listing
    listing = get_listing_by_sku(sku, headers)
    
    if not listing:
        print("\n❌ Cannot proceed - listing not found or API error.")
        return
    
    # Step 2: Display current info
    display_listing_info(listing)
    
    listing_id = listing.get('id')
    
    # Handle inventory - both int and dict formats
    inventory = listing.get('inventory', 0)
    if isinstance(inventory, dict):
        current_inventory = inventory.get('quantity', 0)
    else:
        current_inventory = int(inventory) if inventory else 0
    
    # Handle price - both formats
    current_price_data = listing.get('price', {})
    if isinstance(current_price_data, dict):
        current_price = float(current_price_data.get('amount', 0))
        currency = current_price_data.get('currency', 'USD')
    else:
        current_price = float(current_price_data) if current_price_data else 0.0
        currency = 'USD'
    
    # Step 3: Ask what to test
    print("\n" + "="*60)
    print("🧪 TEST OPTIONS")
    print("="*60)
    print("1. Test Inventory Update")
    print("2. Test Price Update")
    print("3. Test Both")
    print("4. Just view info (no updates)")
    
    choice = input("\nSelect option (1-4): ").strip()
    
    if choice == '1' or choice == '3':
        # Ask user for inventory value
        print(f"\nCurrent Inventory: {current_inventory}")
        inventory_input = input("Enter new inventory value (0-999): ").strip()
        try:
            test_inventory = int(inventory_input)
            if test_inventory < 0:
                print("   ⚠️  Inventory cannot be negative. Using 0.")
                test_inventory = 0
            success = test_update_inventory(listing_id, test_inventory, headers)
            
            if success:
                # Verify by fetching again
                print("\n🔄 Verifying update...")
                updated_listing = get_listing_by_sku(sku, headers)
                if updated_listing:
                    inv = updated_listing.get('inventory', 0)
                    if isinstance(inv, dict):
                        new_inventory = inv.get('quantity', 0)
                    else:
                        new_inventory = int(inv) if inv else 0
                    print(f"   ✅ Verified: Inventory is now {new_inventory}")
        except ValueError:
            print("   ❌ Invalid inventory value. Update skipped.")
    
    if choice == '2' or choice == '3':
        # Ask user for price value
        print(f"\nCurrent Price: {currency} ${current_price:.2f}")
        price_input = input(f"Enter new price ({currency}): ").strip().replace('$', '').replace(',', '')
        try:
            test_price = float(price_input)
            if test_price < 0:
                print("   ⚠️  Price cannot be negative. Update skipped.")
            else:
                success = test_update_price(listing_id, test_price, headers, currency)
                
                if success:
                    # Verify by fetching again
                    print("\n🔄 Verifying update...")
                    updated_listing = get_listing_by_sku(sku, headers)
                    if updated_listing:
                        price_info = updated_listing.get('price', {})
                        if isinstance(price_info, dict):
                            new_price = float(price_info.get('amount', 0))
                        else:
                            new_price = float(price_info) if price_info else 0.0
                        print(f"   ✅ Verified: Price is now {currency} ${new_price:.2f}")
        except ValueError:
            print("   ❌ Invalid price value. Update skipped.")
    
    if choice == '4':
        print("\n✅ Test complete - No updates performed (view only)")
    
    print("\n" + "="*60)
    print("✅ TEST COMPLETE")
    print(f"Store: {store_name}")
    print("="*60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

