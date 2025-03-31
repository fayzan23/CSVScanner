# Trading Data Analyzer

A Flask web application that processes and analyzes trading data from CSV files. The application handles various types of trading data including stocks and options, with support for different transaction types and status tracking.

## Features

- CSV file upload and processing
- Support for various trading actions:
  - Buy/Sell to Open/Close
  - Assigned
  - Journal
  - Exchange or Exercise
  - Dividends
  - Interest
- Automatic option type detection (Put/Call)
- Status tracking (Open/Closed) based on expiry dates
- Data summary generation
- Query interface for data analysis

## Prerequisites

- Python 3.9 or higher
- pip (Python package installer)

## Quick Start

1. Clone the repository:

```bash
git clone https://github.com/fayzan23/CSVScanner.git
cd CSVScanner
```

2. (Recommended) Create and activate a virtual environment:

```bash
# Create virtual environment (recommended for clean installation)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate
```

Note: Using a virtual environment is recommended but optional. It helps avoid package conflicts and keeps your system Python clean.

3. Install dependencies:

```bash
# If using virtual environment (recommended):
pip install -r requirements.txt

# If installing globally (alternative):
pip install flask pandas python-dotenv
```

4. Run the application:

```bash
python app.py
```

5. Open your web browser and navigate to `http://localhost:5000`

## CSV Format Requirements

The application expects CSV files with the following columns:

- Date: Transaction date (supports "as of" format)
- Action: Type of transaction (e.g., Buy to Open, Sell to Close)
- Symbol: Trading symbol (supports both stock and option symbols)
- Quantity: Number of shares/contracts
- Price: Transaction price
- Amount: Transaction amount
- Fees & Comm: Transaction fees (optional)

### Example CSV Format:

```csv
Date,Action,Symbol,Quantity,Price,Amount,Fees & Comm
03/15/2024,Buy to Open,QQQ 03/22/2024 $400 PUT,1,2.50,250.00,1.50
03/18/2024,Sell to Close,QQQ 03/22/2024 $400 PUT,1,3.75,375.00,1.50
03/20/2024 as of 03/19/2024,Cash Dividend,AAPL,100,,75.00,0.00
```

### Supported Actions

- Buy to Open
- Buy to Close
- Sell to Open
- Sell to Close
- Assigned
- Journal
- Exchange or Exercise
- Qualified Dividend (processed as "Dividend")
- Cash Dividend (processed as "Dividend")
- Credit Interest (processed as "Interest")
- Margin Interest (processed as "Interest")

## Features

### Data Processing

- Automatic detection of option types (Put/Call)
- Status tracking for options (Open/Closed based on expiry)
- Stock vs. Option trade identification
- Dividend and Interest categorization
- Fee calculation and total amount computation

### Data Organization

The processed CSV will include:

- Posted Date and Transaction Date (split from "as of" format)
- Organized action types
- Option details (Ticker, Expiry, Strike, Option Type)
- Trade type classification
- Status tracking
- Financial calculations including fees

## Troubleshooting

1. If you get module import errors:

   - If using venv: Make sure you've activated it and installed requirements
   - If not using venv: Make sure you've installed all required packages globally
   - Verify installations with: `pip list`

2. If the application won't start:

   - Check if port 5000 is available
   - Verify Python version (3.9 or higher)

3. If CSV processing fails:
   - Verify your CSV format matches the required structure
   - Check for special characters or encoding issues in your CSV
   - Ensure dates are in MM/DD/YYYY format

## License

MIT License
