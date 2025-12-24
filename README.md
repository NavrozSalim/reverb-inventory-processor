# Reverb Data Scraper

A Python script that processes inventory data from multiple stores, extracts ASINs from SKUs, and generates formatted output files with product links.

## Features

- **Multi-Store Processing**: Processes data from multiple stores (MMS, MZM, TSS, GG, GGL, AMH)
- **ASIN Extraction**: Automatically extracts ASINs from SKUs using strict pattern matching
- **Dual Platform Support**: Handles both Amazon (10-character) and eBay (12-digit) ASINs
- **Link Generation**: Automatically generates product links based on ASIN type
- **Manual Review**: Sends SKUs that don't match patterns to a separate sheet for manual review
- **Data Validation**: Validates ASIN format and ensures accuracy

## ASIN Extraction Logic

The script extracts ASINs from SKUs using strict pattern matching:

### Amazon ASIN (10 characters)
- **Pattern**: `STOREPREFIX-<10CHARCODE>-New` or `STOREPREFIX-<10CHARCODE>-N`
- **Requirements**: 
  - Exactly 10 alphanumeric characters
  - Must contain at least one letter
- **Extraction**: Split into two 5-character halves and swap positions

**Examples:**
- `MZM-4KTCXB0CYZ-New` → `B0CYZ4KTCX`
- `MZM-7TBHSB0DJ8-N` → `B0DJ87TBHS`
- `MZM-9866NB098S-New` → `B098S9866N`

### eBay ASIN (12 digits)
- **Pattern**: `STOREPREFIX-<12DIGITS>-New` or `STOREPREFIX-<12DIGITS>-N`
- **Requirements**: 
  - Exactly 12 numeric digits
- **Extraction**: Split into two 6-digit halves and swap positions

**Examples:**
- `MZM-853596316522-New` → `316522853596`
- `MMS-197190135509-New` → `135509197190`

### Manual Review
SKUs that don't match the strict patterns are sent to the "Manual Review" sheet for manual ASIN entry.

## Installation

### Prerequisites
- Python 3.7 or higher
- pip (Python package manager)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd "Reverb Work"
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

## Configuration

Edit the configuration section in `Reverb Data Scraper.py`:

```python
# Input directory containing store files
INPUT_DIR = r"C:\Users\Navroz\OneDrive\Desktop\Reverb Work\Input Files"

# Output directory for generated files
OUTPUT_DIR = r"C:\Users\Navroz\OneDrive\Desktop\Reverb Work\Output File"

# Stores to process (in order)
STORE_FILES = ["MMS", "MZM", "TSS", "GG", "GGL", "AMH"]
```

## Input File Format

Place your store data files in the `Input Files` directory with the following naming:
- `MMS.csv` or `MMS.xlsx`
- `MZM.csv` or `MZM.xlsx`
- `TSS.csv` or `TSS.xlsx`
- etc.

### Required Columns
- **SKU**: Product SKU identifier
- **ASIN**: (Optional) Existing ASIN value (will be extracted from SKU if not provided)

### Supported Formats
- CSV (`.csv`)
- Excel (`.xlsx`, `.xls`)

## Usage

Run the script:

```bash
python "Reverb Data Scraper.py"
```

### Output

The script generates an Excel file with today's date:
- **Filename**: `Reverb Data Scrape YYYY-MM-DD.xlsx`
- **Location**: `Output File` directory

### Output Sheets

#### 1. Data Sheet
Contains successfully processed SKUs with:
- **STORE NAME**: Store identifier
- **SKU**: Original SKU
- **ASIN**: Extracted ASIN
- **LEN**: ASIN length (10 or 12)
- **LINKS**: Generated product link (Amazon or eBay)
- **STOCK**: (Empty - for manual entry)
- **POSTED PRICE**: (Empty - for manual entry)

#### 2. Manual Review Sheet
Contains SKUs that couldn't be automatically processed:
- **STORE NAME**: Store identifier
- **SKU**: Original SKU
- **MANUAL ASIN**: (Empty - for manual entry)

## Output Example

```
Processing MZM...
  Valid: 2311 rows, Needs Manual Review: 9 rows
  Verification:
    ✓ Extracted from SKU: 2311
    ✗ Sent to Manual Review: 9
```

## Link Generation

The script automatically generates product links based on ASIN type:

- **Amazon ASIN (10 chars)**: `https://www.amazon.com/dp/{ASIN}`
- **eBay ASIN (12 digits)**: `https://www.ebay.com/itm/{ASIN}`

## Validation Rules

### Amazon ASIN Validation
- Must be exactly 10 characters
- Must contain at least one alphabet letter
- Can contain numbers and letters

### eBay ASIN Validation
- Must be exactly 12 characters
- Must contain only numeric digits

## Error Handling

- **Missing Files**: Script skips stores if input files are not found
- **Invalid SKUs**: SKUs that don't match patterns are sent to manual review
- **Invalid ASINs**: Extracted ASINs that don't pass validation are sent to manual review
- **Data Preservation**: All columns are read as strings to preserve formatting

## Troubleshooting

### Issue: ASINs showing as scientific notation
**Solution**: The script reads all data as strings to prevent this. Ensure input files are properly formatted.

### Issue: SKUs not being extracted
**Solution**: Verify SKU format matches the strict patterns:
- Must end with `-New` or `-N`
- Must have exactly 10 or 12 characters in the middle code
- For Amazon: code must contain at least one letter

### Issue: File not found errors
**Solution**: 
- Ensure input files are in the `Input Files` directory
- Check file naming matches store names exactly (case-sensitive)
- Verify file extensions are `.csv`, `.xlsx`, or `.xls`

## Project Structure

```
Reverb Work/
├── Reverb Data Scraper.py    # Main script
├── requirements.txt            # Python dependencies
├── README.md                  # This file
├── Input Files/               # Input data files
│   ├── MMS.csv
│   ├── MZM.csv
│   └── ...
└── Output File/               # Generated output files
    └── Reverb Data Scrape YYYY-MM-DD.xlsx
```

## Dependencies

- **pandas**: Data manipulation and Excel file handling
- **openpyxl**: Excel file reading/writing
- **xlsxwriter**: Excel formatting and styling

See `requirements.txt` for specific versions.

## License

This project is proprietary software. All rights reserved.

## Author

Developed for Reverb Work inventory management.

## Version History

- **v1.0.0** (2025-12-23)
  - Initial release
  - Support for Amazon and eBay ASIN extraction
  - Multi-store processing
  - Manual review functionality

