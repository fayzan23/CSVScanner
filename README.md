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
- AWS account with Bedrock access
- AWS credentials configured

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd trading-data-analyzer
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your AWS credentials:

```
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
BEDROCK_AGENT_ID=your_agent_id
BEDROCK_AGENT_ALIAS_ID=your_agent_alias_id
```

## Usage

1. Start the Flask application:

```bash
python app.py
```

2. Open your web browser and navigate to `http://localhost:5000`

3. Upload your CSV file with the following required columns:

   - Date
   - Action
   - Symbol
   - Quantity
   - Price
   - Amount

4. View the processed data and use the query interface to analyze your trading data

## CSV Format Requirements

The application expects CSV files with the following columns:

- Date: Transaction date (supports "as of" format)
- Action: Type of transaction
- Symbol: Trading symbol (supports both stock and option symbols)
- Quantity: Number of shares/contracts
- Price: Transaction price
- Amount: Transaction amount
- Fees & Comm: Transaction fees (optional)

## License

MIT License
