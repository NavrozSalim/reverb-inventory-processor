# Reverb Inventory Management Suite

A comprehensive Python toolkit for managing Reverb inventory across multiple stores. Includes ASIN extraction, price variance tracking, and automated inventory/price updates.

## 📦 Project Overview

This repository contains multiple tools for Reverb inventory management:

1. **Reverb Data Scraper** - Extracts ASINs from SKUs and generates product links
2. **Price Variance Updater** - Updates prices with variance tracking ($50+ threshold)
3. **Multi Store Price and Inventory Updater** - Updates both inventory and prices
4. **Multi Store Inventory Updater** - Updates inventory only
5. **Reverb Updater** - Single store updater
6. **Test Reverb API** - API testing utility

## 🚀 Quick Start

### Prerequisites
- Python 3.7 or higher
- pip (Python package manager)
- Reverb API tokens for your stores

### Installation

1. Clone the repository:
```bash
git clone https://github.com/NavrozSalim/reverb-inventory-processor.git
cd reverb-inventory-processor
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure API tokens:
   - Copy `.env.example` to `.env`
   - Add your Reverb API tokens to the `.env` file
   ```bash
   cp .env.example .env
   # Then edit .env and add your actual API tokens
   ```

## 📋 Scripts Overview

### 1. Reverb Data Scraper

**File**: `Reverb Data Scraper.py`

Extracts ASINs from SKUs and generates formatted Excel output with product links.

#### Features
- Multi-store processing (MMS, MZM, TSS, GG, GGL, AMH)
- Automatic ASIN extraction from SKU patterns
- Amazon (10-char) and eBay (12-digit) ASIN support
- Automatic link generation
- Manual review sheet for unmatched SKUs

#### ASIN Extraction Logic

**Amazon ASIN (10 characters):**
- Pattern: `STOREPREFIX-<10CHARCODE>-New` or `STOREPREFIX-<10CHARCODE>-N`
- Example: `MZM-4KTCXB0CYZ-New` → `B0CYZ4KTCX`
- Logic: Split into two 5-char halves, swap positions

**eBay ASIN (12 digits):**
- Pattern: `STOREPREFIX-<12DIGITS>-New` or `STOREPREFIX-<12DIGITS>-N`
- Example: `MZM-853596316522-New` → `316522853596`
- Logic: Split into two 6-digit halves, swap positions

#### Usage
```bash
python "Reverb Data Scraper.py"
```

**Input**: CSV/Excel files in `Input Files/` directory
**Output**: `Output File/Reverb Data Scrape YYYY-MM-DD.xlsx`

---

### 2. Price Variance Updater

**File**: `Price Variance Updater.py`

Updates inventory and prices on Reverb with variance tracking. SKUs with price differences ≥ $50 are updated AND added to a review file.

#### Features
- Combined inventory + price updates (single API call)
- Price variance tracking ($50 threshold)
- FAST_MODE for faster processing
- Real-time data saving (saves after each store)
- Rate limiting protection

#### Price Update Logic
- **Posted Price = 0**: Skip price update
- **Difference ≥ $50**: Update price AND add to review file
- **Difference < $50**: Update price normally

#### Configuration
```python
FAST_MODE = True  # Skip validation for speed
DELAY_PER_PRODUCT = 1.5  # Seconds between API calls
PRICE_VARIANCE_THRESHOLD = 50.0  # Dollar threshold
```

#### Usage
```bash
python "Price Variance Updater.py"
```

**Input**: `StoreDB inventory and Price Update.xlsx`
**Output**: 
- Updates on Reverb
- `Price vary Sku update Folder/Price Variance Review YYYY-MM-DD.xlsx`

---

### 3. Multi Store Price and Inventory Updater

**File**: `Multi Store Price and Inventory Updater.py`

Updates both inventory and prices for multiple stores. Only updates price if Posted Price > Reverb Price.

#### Features
- Multi-store batch processing
- Inventory validation
- Conditional price updates
- Rate limiting
- Detailed logging

#### Usage
```bash
python "Multi Store Price and Inventory Updater.py"
```

**Input**: `StoreDB inventory and Price Update.xlsx`

---

### 4. Multi Store Inventory Updater

**File**: `Multi Store Inventory Updater.py`

Updates inventory only (no price updates) for multiple stores.

#### Usage
```bash
python "Multi Store Inventory Updater.py"
```

**Input**: `StoreDB inventory Update.xlsx`

---

### 5. Reverb Updater

**File**: `Reverb Updater.py`

Single-store updater with interactive store selection.

#### Usage
```bash
python "Reverb Updater.py"
```

---

### 6. Test Reverb API

**File**: `Test Reverb API.py`

Utility script for testing Reverb API connectivity and authentication.

#### Usage
```bash
python "Test Reverb API.py"
```

## ⚙️ Configuration

### Store API Tokens

API tokens are stored in a `.env` file (not committed to git for security).

1. **Copy the example file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and add your API tokens:**
   ```env
   TSS_API_TOKEN=your_actual_token_here
   GGL_API_TOKEN=your_actual_token_here
   MMS_API_TOKEN=your_actual_token_here
   MZM_API_TOKEN=your_actual_token_here
   GG_API_TOKEN=your_actual_token_here
   AMH_API_TOKEN=your_actual_token_here
   ```

3. **All scripts automatically load tokens from `.env` file**

**✅ Security**: 
- `.env` file is in `.gitignore` (never committed to git)
- `.env.example` is a template (safe to commit)
- Tokens are loaded via `python-dotenv` library

## 📁 Project Structure

```
reverb-inventory-processor/
├── Reverb Data Scraper.py              # ASIN extraction tool
├── Price Variance Updater.py           # Price variance tracking
├── Multi Store Price and Inventory Updater.py
├── Multi Store Inventory Updater.py
├── Reverb Updater.py                   # Single store updater
├── Test Reverb API.py                  # API testing
├── requirements.txt                    # Python dependencies
├── .env.example                        # Environment variables template
├── .env                                # Your API tokens (not in git)
├── README.md                           # This file
├── .gitignore                          # Git ignore rules
├── Input Files/                        # Input data (not in git)
└── Output File/                        # Generated files (not in git)
```

## 📊 Input File Formats

### Reverb Data Scraper
- **Required**: `SKU` column
- **Optional**: `ASIN` column
- **Format**: CSV or Excel (.xlsx, .xls)
- **Location**: `Input Files/` directory
- **Naming**: `MMS.csv`, `MZM.csv`, etc.

### Price/Inventory Updaters
- **Required**: `STORES NAME`, `SKU`, `STOCK` columns
- **Optional**: `POSTED PRICE` column
- **Format**: Excel (.xlsx)
- **File**: `StoreDB inventory and Price Update.xlsx`

## 🔒 Security

- ✅ API tokens are stored in `.env` file (not committed to git)
- ✅ `.env` is in `.gitignore` (never committed)
- ✅ `.env.example` is a template (safe to commit)
- ✅ Data files are excluded from git
- ✅ Output files are excluded from git

## 📝 Dependencies

See `requirements.txt` for full list:
- pandas >= 2.0.0
- openpyxl >= 3.1.0
- requests >= 2.31.0
- python-dotenv >= 1.0.0 (for .env file support)
- xlsxwriter (for formatting)

## 🐛 Troubleshooting

### ASIN Extraction Issues
- Verify SKU format matches strict patterns
- Check SKU ends with `-New` or `-N`
- Ensure code is exactly 10 or 12 characters

### API Errors
- Verify API tokens are correct
- Check rate limiting (50 requests per 2 minutes)
- Review log files for detailed errors

### File Not Found
- Ensure input files are in correct directories
- Check file naming matches store names exactly
- Verify file extensions (.csv, .xlsx, .xls)

## 📈 Performance

### Price Variance Updater
- **FAST_MODE ON**: ~1.5 seconds per SKU
- **FAST_MODE OFF**: ~2.5 seconds per SKU
- **Rate Limit**: 50 products per 2 minutes

### Reverb Data Scraper
- Processes all stores sequentially
- No API calls (file processing only)
- Fast execution (< 1 minute for thousands of rows)

## 📄 License

This project is proprietary software. All rights reserved.

## 👤 Author

Developed for Reverb Work inventory management.

## 📅 Version History

- **v1.0.0** (2025-12-23)
  - Initial release
  - Full project suite
  - Multi-store support
  - Price variance tracking
  - ASIN extraction with validation

## 🤝 Contributing

This is a private project. For issues or feature requests, please contact the repository owner.

## 📞 Support

For questions or issues, please open an issue on GitHub or contact the development team.
