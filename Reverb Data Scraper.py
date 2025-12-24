"""
Reverb Data Scraper
Processes input files from multiple stores and generates a combined output file
with SKU, ASIN, and link information.
"""

import os
import pandas as pd
from datetime import datetime
import re


# Configuration
INPUT_DIR = r"C:\Users\Navroz\OneDrive\Desktop\Reverb Work\Input Files"
OUTPUT_DIR = r"C:\Users\Navroz\OneDrive\Desktop\Reverb Work\Output File"

# Files to process (in order)
STORE_FILES = ["MMS", "MZM", "TSS", "GG", "GGL", "AMH"]


def find_input_file(store_name):
    """
    Find the input file for a given store name.
    Checks for both CSV and Excel file extensions.
    """
    extensions = ['.csv', '.xlsx', '.xls']
    
    for ext in extensions:
        file_path = os.path.join(INPUT_DIR, f"{store_name}{ext}")
        if os.path.exists(file_path):
            return file_path
    
    return None


def read_input_file(file_path):
    """
    Read input file (CSV or Excel) and return a DataFrame.
    Read all columns as strings to preserve ASIN formatting.
    Uses converters to ensure exact string representation.
    """
    if file_path.endswith('.csv'):
        return pd.read_csv(file_path, dtype=str, keep_default_na=False)
    elif file_path.endswith(('.xlsx', '.xls')):
        # Read Excel file - use dtype=str and na_filter=False to preserve exact values
        # This prevents pandas from converting numbers and losing precision
        df = pd.read_excel(file_path, dtype=str, na_filter=False, keep_default_na=False)
        # Replace any 'nan' strings (from pandas conversion) with empty strings
        df = df.replace('nan', '')
        df = df.replace('NaN', '')
        return df
    else:
        raise ValueError(f"Unsupported file format: {file_path}")


def convert_to_string(value):
    """
    Convert a value to string properly, handling:
    - NaN/None
    - Float numbers (avoid scientific notation and decimals)
    - Integer numbers
    - Already strings
    - Scientific notation strings
    - Preserve exact string representation when possible
    """
    if pd.isna(value):
        return ""
    
    # If it's already a string, check if it needs processing
    if isinstance(value, str):
        value_str = value.strip()
        
        # Handle scientific notation strings (e.g., "4.01642E+11")
        if 'e+' in value_str.lower() or 'e-' in value_str.lower():
            try:
                # Convert from scientific notation to regular number
                num = float(value_str)
                # Convert to int to avoid decimals and preserve precision
                return f"{int(num)}"
            except (ValueError, OverflowError):
                return value_str
        
        # If it's already a clean string (no scientific notation), return as-is
        return value_str
    
    # If it's a float, convert carefully to preserve precision
    if isinstance(value, float):
        # Check if it's a whole number
        if value == int(value):
            # Use format to avoid scientific notation for large numbers
            return f"{int(value)}"
        else:
            # Even if it has decimals, convert to int for ASINs
            return f"{int(value)}"
    
    # If it's an int, convert directly
    if isinstance(value, (int,)):
        return str(value)
    
    # For any other type, convert to string
    return str(value).strip()


def is_valid_asin(asin):
    """
    Validate ASIN format:
    - Length 10: Must contain at least one alphabet letter (alphanumeric)
    - Length 12: Must contain only numbers
    
    Returns: (is_valid, reason)
    """
    if pd.isna(asin) or not isinstance(asin, str) or asin.strip() == "":
        return False, "Empty or missing ASIN"
    
    asin = asin.strip()
    asin_len = len(asin)
    
    if asin_len == 10:
        # Must contain at least one alphabet letter
        has_letter = any(c.isalpha() for c in asin)
        if has_letter:
            return True, "Valid Amazon ASIN"
        else:
            return False, "Length 10 but no alphabets (should contain letters)"
    
    elif asin_len == 12:
        # Must contain only numbers
        if asin.isdigit():
            return True, "Valid eBay ASIN"
        else:
            return False, "Length 12 but contains non-numeric characters"
    
    else:
        return False, f"Invalid length: {asin_len} (must be 10 or 12)"


def verify_asin_from_sku(asin, sku):
    """
    Verify that an ASIN can be correctly extracted from the given SKU.
    This is a reverse verification to ensure accuracy.
    
    Returns: (is_verified, extracted_asin)
    """
    if not asin or not sku:
        return False, ""
    
    # Extract ASIN from SKU
    extracted_asin, success = extract_asin_from_sku(sku)
    
    if not success:
        return False, ""
    
    # Verify the extracted ASIN matches the provided ASIN
    return (extracted_asin == asin), extracted_asin


def extract_asin_from_sku(sku):
    """
    Extract ASIN from SKU using ONLY the specific patterns.
    
    STRICT PATTERNS:
    1. STOREPREFIX-<10CHARCODE>-New or STOREPREFIX-<10CHARCODE>-N (Amazon ASIN)
    2. STOREPREFIX-<12DIGITS>-New or STOREPREFIX-<12DIGITS>-N (eBay ASIN)
    
    Type 1 (10 chars - Amazon):
    - 10-character code (alphanumeric, must contain letters)
    - Split into two parts of 5 characters each
    - Swap their positions
    
    Type 2 (12 digits - eBay):
    - 12-digit code (all numbers)
    - Split into two parts of 6 digits each
    - Swap their positions
    
    Examples:
    - MZM-4KTCXB0CYZ-New -> 4KTCXB0CYZ -> B0CYZ + 4KTCX -> B0CYZ4KTCX (Amazon)
    - MZM-7TBHSB0DJ8-N -> 7TBHSB0DJ8 -> B0DJ8 + 7TBHS -> B0DJ87TBHS (Amazon)
    - MZM-9866NB098S-New -> 9866NB098S -> B098S + 9866N -> B098S9866N (Amazon)
    - MZM-853596316522-New -> 853596316522 -> 316522 + 853596 -> 316522853596 (eBay)
    
    Returns: (asin, success)
        - asin: The extracted ASIN or empty string
        - success: True if valid ASIN was extracted, False otherwise
    """
    if pd.isna(sku) or not isinstance(sku, str):
        return "", False
    
    sku = str(sku).strip()
    
    # STRICT PATTERN 1: PREFIX-<10CHARCODE>-New or PREFIX-<10CHARCODE>-N (Amazon)
    pattern1_10 = r'^[A-Za-z]+-([A-Za-z0-9]{10})-[Nn]ew$'
    pattern2_10 = r'^[A-Za-z]+-([A-Za-z0-9]{10})-[Nn]$'
    
    # STRICT PATTERN 2: PREFIX-<12DIGITS>-New or PREFIX-<12DIGITS>-N (eBay)
    pattern1_12 = r'^[A-Za-z]+-(\d{12})-[Nn]ew$'
    pattern2_12 = r'^[A-Za-z]+-(\d{12})-[Nn]$'
    
    # Try Amazon pattern (10 chars)
    match1_10 = re.match(pattern1_10, sku)
    match2_10 = re.match(pattern2_10, sku)
    match_10 = match1_10 or match2_10
    
    if match_10:
        code = match_10.group(1)
        # Verify it contains at least one letter (required for Amazon ASIN)
        if any(c.isalpha() for c in code):
            # Extract ASIN: Split into two halves and swap
            first_half = code[:5]
            second_half = code[5:]
            asin = second_half + first_half
            return asin, True
    
    # Try eBay pattern (12 digits)
    match1_12 = re.match(pattern1_12, sku)
    match2_12 = re.match(pattern2_12, sku)
    match_12 = match1_12 or match2_12
    
    if match_12:
        code = match_12.group(1)
        # Verify it's all digits
        if code.isdigit():
            # Extract ASIN: Split into two halves and swap
            first_half = code[:6]
            second_half = code[6:]
            asin = second_half + first_half
            return asin, True
    
    # Pattern doesn't match - return failure (will go to manual review)
    return "", False


def generate_link(asin):
    """
    Generate a link based on ASIN length.
    - LEN = 10 (with letters): Amazon link
    - LEN = 12 (all digits): eBay link
    - Otherwise: blank
    """
    if pd.isna(asin) or not isinstance(asin, str) or asin == "":
        return ""
    
    asin = asin.strip()
    asin_len = len(asin)
    
    # Length 10 with at least one letter = Amazon
    if asin_len == 10 and any(c.isalpha() for c in asin):
        return f"https://www.amazon.com/dp/{asin}"
    # Length 12 with all digits = eBay
    elif asin_len == 12 and asin.isdigit():
        return f"https://www.ebay.com/itm/{asin}"
    else:
        return ""


def process_store_file(store_name, file_path):
    """
    Process a single store file and return processed DataFrames.
    Returns: (valid_df, invalid_df)
    """
    print(f"Processing {store_name}...")
    
    # Read the file
    df = read_input_file(file_path)
    
    # Normalize column names (case-insensitive matching)
    df.columns = df.columns.str.lower().str.strip()
    
    # Check for required column 'sku'
    if 'sku' not in df.columns:
        print(f"  Warning: 'sku' column not found in {store_name}. Skipping.")
        return None, None
    
    # Create output data lists
    valid_data = []
    invalid_data = []
    
    # Verification statistics
    verification_stats = {
        'extracted_from_sku': 0,
        'no_asin': 0
    }
    
    # Track failed SKU extractions for analysis (limit to first 20 examples)
    failed_sku_examples = []
    
    for idx, row in df.iterrows():
        # Get SKU - convert properly to avoid scientific notation
        sku_raw = row.get('sku', '')
        sku = convert_to_string(sku_raw)
        
        # SIMPLE LOGIC: Extract ASIN from SKU only, or send to manual review
        final_asin = ""
        
        # Try to extract ASIN from SKU
        extracted_asin, extraction_success = extract_asin_from_sku(sku)
        
        if extraction_success:
            # Verify the extracted ASIN is valid
            is_valid, reason = is_valid_asin(extracted_asin)
            if is_valid:
                final_asin = extracted_asin
                verification_stats['extracted_from_sku'] += 1
            else:
                # Extraction succeeded but ASIN is invalid - send to manual review
                verification_stats['no_asin'] += 1
        else:
            # Extraction failed - send to manual review
            verification_stats['no_asin'] += 1
            # Track failed extractions for analysis
            if len(failed_sku_examples) < 20:
                failed_sku_examples.append({
                    'sku': sku,
                    'parts': sku.split('-') if sku else []
                })
        
        # Now decide if valid or needs manual review
        if final_asin != '':
            # Calculate length
            asin_len = len(final_asin)
            
            # Generate link
            link = generate_link(final_asin)
            
            valid_data.append({
                'STORE NAME': store_name,
                'SKU': sku,
                'ASIN': final_asin,
                'LEN': asin_len,
                'LINKS': link,
                'STOCK': '',
                'POSTED PRICE': ''
            })
        else:
            # Add to invalid/manual review list - only if we truly can't get an ASIN
            invalid_data.append({
                'STORE NAME': store_name,
                'SKU': sku,
                'MANUAL ASIN': ''  # User fills this in
            })
    
    valid_count = len(valid_data)
    invalid_count = len(invalid_data)
    print(f"  Valid: {valid_count} rows, Needs Manual Review: {invalid_count} rows")
    print(f"  Verification:")
    print(f"    ✓ Extracted from SKU: {verification_stats['extracted_from_sku']}")
    print(f"    ✗ Sent to Manual Review: {verification_stats['no_asin']}")
    
    # Show examples of failed SKU extractions for analysis
    if failed_sku_examples:
        print(f"\n  📋 Sample SKUs sent to manual review (showing first {min(len(failed_sku_examples), 10)}):")
        for i, example in enumerate(failed_sku_examples[:10], 1):  # Show first 10
            print(f"    {i}. SKU: {example['sku']}")
            print(f"       Parts: {example['parts']}")
    
    valid_df = pd.DataFrame(valid_data) if valid_data else None
    invalid_df = pd.DataFrame(invalid_data) if invalid_data else None
    
    return valid_df, invalid_df, verification_stats


def main():
    """
    Main function to process all store files and generate combined output.
    """
    print("=" * 60)
    print("Reverb Data Scraper")
    print("=" * 60)
    print(f"Input Directory: {INPUT_DIR}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print()
    
    # Check if input directory exists
    if not os.path.exists(INPUT_DIR):
        print(f"Error: Input directory does not exist: {INPUT_DIR}")
        return
    
    # Create output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created output directory: {OUTPUT_DIR}")
    
    # Process each store file
    all_valid_data = []
    all_invalid_data = []
    files_processed = 0
    
    for store_name in STORE_FILES:
        file_path = find_input_file(store_name)
        
        if file_path:
            print(f"Found: {file_path}")
            valid_df, invalid_df, verification_stats = process_store_file(store_name, file_path)
            
            if valid_df is not None and not valid_df.empty:
                all_valid_data.append(valid_df)
            
            if invalid_df is not None and not invalid_df.empty:
                all_invalid_data.append(invalid_df)
            
            files_processed += 1
        else:
            print(f"Not found: {store_name} (skipping)")
    
    print()
    
    # Combine all data
    if all_valid_data or all_invalid_data:
        # Generate output filename with today's date
        today = datetime.now().strftime("%Y-%m-%d")
        output_filename = f"Reverb Data Scrape {today}.xlsx"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        # Create Excel writer with xlsxwriter engine to format ASIN as text
        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            workbook = writer.book
            
            # Text format to prevent number conversion
            text_format = workbook.add_format({'num_format': '@'})
            
            # Write valid data to main sheet
            if all_valid_data:
                combined_valid = pd.concat(all_valid_data, ignore_index=True)
                combined_valid.to_excel(writer, sheet_name='Data', index=False)
                
                # Get the worksheet and format ASIN column as text
                worksheet = writer.sheets['Data']
                
                # Find ASIN column index (0-based, +0 because no index column)
                asin_col = combined_valid.columns.get_loc('ASIN')
                
                # Set column format for ASIN
                worksheet.set_column(asin_col, asin_col, 15, text_format)
                
                # Also format the LEN column
                len_col = combined_valid.columns.get_loc('LEN')
                worksheet.set_column(len_col, len_col, 8)
                
                # Widen other columns for readability
                worksheet.set_column(0, 0, 12)  # STORE NAME
                worksheet.set_column(1, 1, 30)  # SKU
                worksheet.set_column(4, 4, 45)  # LINKS
                
                valid_count = len(combined_valid)
            else:
                valid_count = 0
            
            # Write invalid data to separate sheet for manual review
            if all_invalid_data:
                combined_invalid = pd.concat(all_invalid_data, ignore_index=True)
                combined_invalid.to_excel(writer, sheet_name='Manual Review', index=False)
                
                # Format the manual review sheet
                worksheet_invalid = writer.sheets['Manual Review']
                worksheet_invalid.set_column(0, 0, 12)   # STORE NAME
                worksheet_invalid.set_column(1, 1, 35)   # SKU
                worksheet_invalid.set_column(2, 2, 15, text_format)  # MANUAL ASIN
                
                invalid_count = len(combined_invalid)
            else:
                invalid_count = 0
        
        print("=" * 60)
        print("Processing Complete!")
        print("=" * 60)
        print(f"Files processed: {files_processed}")
        print(f"Valid rows (Data sheet): {valid_count}")
        print(f"Needs review (Manual Review sheet): {invalid_count}")
        print(f"Output file: {output_path}")
        
        if invalid_count > 0:
            print()
            print("NOTE: Please review the 'Manual Review' sheet for SKUs")
            print("that need manual ASIN extraction.")
    else:
        print("No data to process. No output file generated.")
        print("Please ensure input files exist in the Input Files directory.")


if __name__ == "__main__":
    main()
