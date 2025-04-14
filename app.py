from flask import Flask, render_template, request, jsonify
import base64
import boto3
import json
import os
from io import StringIO
import pandas as pd
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)

# Rate limiting configuration
RATE_LIMIT_PERIOD = 60  # 1 minute in seconds
MAX_REQUESTS = 10  # Maximum requests per minute
request_timestamps = []

def check_rate_limit():
    """Check if we're within rate limits"""
    global request_timestamps
    current_time = datetime.now()
    
    # Remove timestamps older than our period
    request_timestamps = [ts for ts in request_timestamps 
                        if current_time - ts < timedelta(seconds=RATE_LIMIT_PERIOD)]
    
    # Check if we're at the limit
    if len(request_timestamps) >= MAX_REQUESTS:
        return False
    
    # Add current timestamp and return True
    request_timestamps.append(current_time)
    return True

# Configure AWS credentials
try:
    bedrock = boto3.client(
        service_name='bedrock-agent-runtime',
        region_name='us-east-2',  # Changed back to us-east-2 to match the agent's ARN
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )
    
    print("AWS Configuration:")
    print(f"Region: us-east-2")
    print(f"Agent ID: {os.getenv('BEDROCK_AGENT_ID')}")
    print(f"Agent Alias ID: {os.getenv('BEDROCK_AGENT_ALIAS_ID')}")
    
    # Verify the agent exists
    def verify_agent():
        try:
            agent_id = os.getenv('BEDROCK_AGENT_ID')
            agent_alias_id = os.getenv('BEDROCK_AGENT_ALIAS_ID')
            
            if not agent_id or not agent_alias_id:
                print("Missing Agent ID or Alias ID")
                return False
            
            print(f"\nAttempting to verify agent:")
            print(f"Agent ID: {agent_id}")
            print(f"Agent Alias ID: {agent_alias_id}")
            
            # Try to invoke agent with a simple test
            response = bedrock.invoke_agent(
                agentId=agent_id,
                agentAliasId=agent_alias_id,
                sessionId='test-session',
                inputText='test'
            )
            
            print("Successfully connected to Bedrock agent")
            return True
            
        except Exception as e:
            error_message = str(e)
            print("\nAgent Verification Error:")
            print(f"Error Type: {type(e).__name__}")
            print(f"Error Message: {error_message}")
            
            if 'ResourceNotFoundException' in error_message:
                print("\nPossible issues:")
                print("1. Agent ID or Alias ID might be incorrect")
                print("2. Agent might not be deployed in us-east-2")
                print("3. Agent might not be in PREPARED state")
            elif 'AccessDeniedException' in error_message:
                print("\nPossible issues:")
                print("1. AWS credentials might not have proper permissions")
                print("2. IAM role might need bedrock:InvokeAgent permission")
            
            return False

except Exception as e:
    print(f"Error configuring Bedrock client: {str(e)}")
    bedrock = None

def determine_status(row):
    # Auto-close logic for options and stocks: 
    # 1. Mark expired, assigned, and dividend transactions as Close
    # 2. Check if option has expired based on expiry date
    # 3. The FIFO matching function below will auto-close stock buys/sells
    action = str(row['Action']).strip()
    type_val = str(row['Type']).strip()
    
    # Mark expired, assigned, and dividend transactions as Close
    if type_val in ['Expired', 'Assigned', 'Dividend']:
        return 'Close'
    
    # Check if option has expired
    if pd.notna(row['Expiry']) and pd.to_datetime(row['Expiry']) < pd.Timestamp.now():
        return 'Close'
        
    return 'Open'

def process_csv(df):
    """Process and organize the CSV data"""
    try:
        # Create a copy to avoid modifying the original
        processed_df = df.copy()

        # Fill NaN values appropriately
        processed_df = processed_df.fillna({
            'Date': '',
            'Action': '',
            'Symbol': '',
            'Description': '',
            'Quantity': 0,
            'Price': 0,
            'Amount': 0,
            'Fees & Com': 0
        })

        # Standardize column names
        if 'Fees & Comm' in processed_df.columns:
            processed_df = processed_df.rename(columns={'Fees & Comm': 'Fees & Com'})

        # Convert numeric columns
        numeric_columns = ['Quantity', 'Price', 'Amount', 'Fees & Com']
        for col in numeric_columns:
            if col in processed_df.columns:
                processed_df[col] = processed_df[col].astype(str).str.replace('$', '').str.replace(',', '').str.strip()
                processed_df[col] = processed_df[col].apply(lambda x: str(x).replace('(', '-').replace(')', '') if isinstance(x, str) else x)
                processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce').fillna(0)

        # Handle dates
        def standardize_date(date_str):
            if pd.isna(date_str) or date_str == '':
                return None
            date_str = str(date_str).split('as of')[0].strip()
            try:
                return pd.to_datetime(date_str).strftime('%m/%d/%Y')
            except:
                return date_str

        processed_df['Posted_Date'] = processed_df['Date'].apply(standardize_date)

        def get_transaction_date(date_str):
            if pd.isna(date_str) or date_str == '':
                return None
            parts = str(date_str).split('as of')
            if len(parts) > 1:
                try:
                    return pd.to_datetime(parts[1].strip()).strftime('%m/%d/%Y')
                except:
                    return parts[1].strip()
            return standardize_date(parts[0])

        processed_df['Transaction_Date'] = processed_df['Date'].apply(get_transaction_date)

        # Extract option details
        def extract_option_details(symbol):
            if pd.isna(symbol) or symbol == '':
                return pd.Series({'Ticker': '', 'Expiry': None, 'Strike': None, 'Option_Type': None})

            match = pd.Series(symbol).str.extract(
                r'(\w+)\s*(?:(\d{2}/\d{2}/\d{4})\s*[$]?(\d+(?:\.\d+)?)\s*([PC]|PUT|CALL))?'
            ).iloc[0]

            return pd.Series({
                'Ticker': match[0] if pd.notna(match[0]) else '',
                'Expiry': match[1] if pd.notna(match[1]) else None,
                'Strike': pd.to_numeric(match[2], errors='coerce'),
                'Option_Type': match[3] if pd.notna(match[3]) else None
            })

        option_details = processed_df['Symbol'].apply(extract_option_details)
        processed_df[['Ticker', 'Expiry', 'Strike', 'Option_Type']] = option_details

        # Map option types
        option_type_map = {'P': 'Put', 'C': 'Call', 'PUT': 'Put', 'CALL': 'Call'}
        processed_df['Option_Type'] = processed_df['Option_Type'].map(option_type_map)

        # Create Type column
        def determine_type(row):
            action = str(row['Action']).strip()
            option_type = str(row['Option_Type']).strip() if pd.notna(row['Option_Type']) else ''

            # Handle expired and assigned cases
            if action in ['Expired', 'Assigned']:
                return 'Expired' if action == 'Expired' else 'Assigned'

            # Handle dividend cases
            if action in ['Qualified Dividend', 'Cash Dividend', 'Reinvest Dividend']:
                return 'Dividend'

            if action in ['Credit Interest', 'Margin Interest']:
                return 'Interest'

            if 'Sell' in action:
                if option_type == 'Put':
                    return 'Put Sell'
                elif option_type == 'Call':
                    return 'Call Sell'
                return 'Stock Sell'

            if 'Buy' in action:
                if option_type == 'Put':
                    return 'Put Buy'
                elif option_type == 'Call':
                    return 'Call Buy'
                return 'Stock Buy'

            return action

        processed_df['Type'] = processed_df.apply(determine_type, axis=1)

        # Create Status column with new rules
        def determine_status(row):
            # Auto-close logic for options and stocks: 
            # 1. Mark expired, assigned, and dividend transactions as Close
            # 2. Check if option has expired based on expiry date
            # 3. The FIFO matching function below will auto-close stock buys/sells
            action = str(row['Action']).strip()
            type_val = str(row['Type']).strip()
            
            # Mark expired, assigned, and dividend transactions as Close
            if type_val in ['Expired', 'Assigned', 'Dividend']:
                return 'Close'
            
            # Check if option has expired
            if pd.notna(row['Expiry']) and pd.to_datetime(row['Expiry']) < pd.Timestamp.now():
                return 'Close'
                
            return 'Open'

        processed_df['Status'] = processed_df.apply(determine_status, axis=1)

        # Implement FIFO matching for Stock Buy/Sell pairs
        def match_stock_transactions(df):
            # Make a copy to avoid modifying the original during iteration
            df_copy = df.copy()
            
            # Convert Posted_Date to datetime for proper comparison
            if 'Posted_Date' in df_copy.columns:
                try:
                    df_copy['Posted_Date'] = pd.to_datetime(df_copy['Posted_Date'], errors='coerce')
                    print(f"Converted Posted_Date to datetime. Sample: {df_copy['Posted_Date'].head(3)}")
                except Exception as e:
                    print(f"Error converting Posted_Date: {e}")
                    # If conversion fails, use index order as proxy for time
                    df_copy['Posted_Date'] = df_copy.index
            
            # Debug information
            print(f"Starting FIFO matching. Total rows: {len(df_copy)}")
            
            # Filter only stock transactions - use case-insensitive comparison to catch all variations
            stock_buys = df_copy[df_copy['Type'].str.contains('Stock Buy', case=False, na=False)].copy()
            stock_sells = df_copy[df_copy['Type'].str.contains('Stock Sell', case=False, na=False)].copy()
            
            print(f"Found {len(stock_buys)} stock buys and {len(stock_sells)} stock sells")
            
            # Track which rows should be marked as closed
            rows_to_close = []
            
            # Process each ticker separately
            for ticker in df_copy['Ticker'].unique():
                if pd.isna(ticker) or ticker == '':
                    continue
                    
                # Get buys and sells for this ticker
                ticker_buys = stock_buys[stock_buys['Ticker'] == ticker].copy().sort_values('Posted_Date')
                ticker_sells = stock_sells[stock_sells['Ticker'] == ticker].copy().sort_values('Posted_Date')
                
                print(f"Processing ticker {ticker}: {len(ticker_buys)} buys, {len(ticker_sells)} sells")
                
                # Skip if no pairs to match
                if ticker_buys.empty or ticker_sells.empty:
                    continue
                
                # Track remaining quantities for each buy
                ticker_buys['Remaining_Qty'] = ticker_buys['Quantity'].abs()
                
                # Process each sell using FIFO
                for sell_idx, sell_row in ticker_sells.iterrows():
                    sell_qty = abs(sell_row['Quantity'])
                    sell_date = sell_row['Posted_Date']
                    
                    print(f"Processing sell {sell_idx}: qty={sell_qty}, date={sell_date}")
                    
                    # Find buys that happened before this sell
                    # If dates are not valid, treat all buys as eligible
                    if pd.isna(sell_date) or not isinstance(sell_date, pd.Timestamp):
                        eligible_buys = ticker_buys[ticker_buys['Remaining_Qty'] > 0]
                        print(f"Using all buys as eligible due to invalid sell date")
                    else:
                        eligible_buys = ticker_buys[
                            (ticker_buys['Posted_Date'] <= sell_date) & 
                            (ticker_buys['Remaining_Qty'] > 0)
                        ]
                        print(f"Found {len(eligible_buys)} eligible buys before {sell_date}")
                    
                    if eligible_buys.empty:
                        print(f"No eligible buys found for sell {sell_idx}")
                        continue
                    
                    # Always mark the sell as closed if we found any eligible buys
                    rows_to_close.append(sell_idx)
                    print(f"Marking sell {sell_idx} as closed")
                    
                    # Match with buys using FIFO
                    remaining_sell_qty = sell_qty
                    
                    for buy_idx, buy_row in eligible_buys.iterrows():
                        if remaining_sell_qty <= 0:
                            break
                            
                        buy_remaining_qty = buy_row['Remaining_Qty']
                        matched_qty = min(remaining_sell_qty, buy_remaining_qty)
                        
                        print(f"Matching buy {buy_idx}: qty={buy_remaining_qty}, matched={matched_qty}")
                        
                        # Update the remaining quantity
                        ticker_buys.loc[buy_idx, 'Remaining_Qty'] -= matched_qty
                        remaining_sell_qty -= matched_qty
                        
                        # If buy is fully matched, mark it as closed
                        if ticker_buys.loc[buy_idx, 'Remaining_Qty'] <= 0:
                            rows_to_close.append(buy_idx)
                            print(f"Marking buy {buy_idx} as closed (fully matched)")
            
            # Update the original dataframe with the closed status
            print(f"Total rows to close: {len(rows_to_close)}")
            for idx in rows_to_close:
                if idx in df.index:
                    df.loc[idx, 'Status'] = 'Close'
                
            return df
        
        # Apply FIFO matching to update Status
        processed_df = match_stock_transactions(processed_df)

        # Fill NaN values in processed columns
        processed_df = processed_df.fillna({
            'Posted_Date': '',
            'Transaction_Date': '',
            'Ticker': '',
            'Expiry': '',
            'Option_Type': '',
            'Strike': 0,
            'Type': '',
            'Status': 'Open'  # Default status is Open
        })

        # Organize columns with Status at the end
        columns = [
            'Posted_Date', 'Transaction_Date',
            'Action',
            'Ticker', 'Expiry', 'Strike', 'Option_Type',
            'Type',
            'Quantity', 'Price', 'Fees & Com', 'Amount',
            'Status'  # Moved to the end
        ]

        # Remove Description column if it exists
        if 'Description' in processed_df.columns:
            processed_df = processed_df.drop('Description', axis=1)

        # Format numeric columns
        numeric_columns = ['Strike', 'Price', 'Amount', 'Fees & Com']
        for col in numeric_columns:
            if col in processed_df.columns:
                processed_df[col] = processed_df[col].round(2)

        return processed_df[columns]

    except Exception as e:
        print(f"Error in process_csv: {str(e)}")
        print(f"DataFrame columns: {df.columns.tolist()}")
        print(f"First row: {df.iloc[0].to_dict()}")
        raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'Please upload a CSV file'}), 400

        # Read and validate CSV content
        try:
            df = pd.read_csv(file)
            required_columns = ['Date', 'Action', 'Symbol', 'Quantity', 'Price', 'Amount']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return jsonify({'error': f'Missing required columns: {", ".join(missing_columns)}'}), 400

        except Exception as e:
            return jsonify({'error': f'Invalid CSV format: {str(e)}'}), 400

        # Process the CSV data
        processed_df = process_csv(df)

        # Convert processed DataFrame back to CSV
        processed_csv = processed_df.to_csv(index=False)

        # Calculate summary data
        summary_data = {
            'total_trades': len(processed_df),
            'total_amount': f"${processed_df['Amount'].sum():,.2f}",
            'symbols_traded': processed_df['Ticker'].unique().tolist(),
            'date_range': f"{processed_df['Posted_Date'].min()} to {processed_df['Posted_Date'].max()}",
            'option_types': processed_df['Option_Type'].value_counts().to_dict()
        }

        return jsonify({
            'success': True,
            'processed_csv': processed_csv,
            'summary': summary_data
        })

    except Exception as e:
        print("Server Error:", str(e))
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/query', methods=['POST'])
def query_data():
    try:
        data = request.json
        query = data.get('query')
        csv_data = data.get('csvData')
        
        if not query or not csv_data:
            return jsonify({'error': 'Missing query or CSV data'}), 400
        
        # Decode base64 CSV data
        csv_content = base64.b64decode(csv_data).decode('utf-8')
        df = pd.read_csv(StringIO(csv_content))
        
        # Initialize Bedrock client
        bedrock = boto3.client(
            service_name='bedrock-agent-runtime',
            region_name='us-east-2'
        )
        
        # Prepare the query for Bedrock
        response = bedrock.invoke_agent(
            agentId=os.getenv('BEDROCK_AGENT_ID'),
            agentAliasId=os.getenv('BEDROCK_AGENT_ALIAS_ID'),
            sessionId=str(int(time.time())),
            inputText=query,
            enableTrace=True
        )
        
        # Parse the response
        response_body = json.loads(response['completion'])
        
        return jsonify({
            'response': response_body['text'],
            'data': response_body.get('data', [])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)