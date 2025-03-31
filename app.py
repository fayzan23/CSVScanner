from flask import Flask, render_template, request, jsonify
import base64
import boto3
import json
import os
from io import StringIO
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configure AWS credentials
bedrock = boto3.client(
    service_name='bedrock-agent-runtime',
    region_name='us-east-1',  # Replace with your region
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

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
            'Fees & Comm': 0  # Note the spelling with two 'm's
        })
        
        # Standardize column names - handle variations in fees column name
        if 'Fees & Comm' in processed_df.columns:
            processed_df = processed_df.rename(columns={'Fees & Comm': 'Fees & Com'})
        
        # Convert numeric columns first - before any other processing
        numeric_columns = ['Quantity', 'Price', 'Amount', 'Fees & Com']
        for col in numeric_columns:
            if col in processed_df.columns:
                # Remove any currency symbols and convert to numeric
                processed_df[col] = processed_df[col].astype(str).str.replace('$', '').str.replace(',', '').str.strip()
                # Handle parentheses for negative numbers
                processed_df[col] = processed_df[col].apply(lambda x: str(x).replace('(', '-').replace(')', '') if isinstance(x, str) else x)
                processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce').fillna(0)

        # Handle "as of" dates and standardize date format
        def standardize_date(date_str):
            if pd.isna(date_str) or date_str == '':
                return None
            # Remove any "as of" and get the first date
            date_str = str(date_str).split('as of')[0].strip()
            try:
                # Parse and standardize date format
                return pd.to_datetime(date_str).strftime('%m/%d/%Y')
            except:
                return date_str

        processed_df['Posted_Date'] = processed_df['Date'].apply(standardize_date)
        
        # Handle transaction date (date after "as of" if exists)
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
        
        # Extract option details from Symbol column
        def extract_option_details(symbol):
            if pd.isna(symbol) or symbol == '':
                return pd.Series({'Ticker': '', 'Expiry': None, 'Strike': None, 'Option_Type': None})
            
            # Try to extract option details
            match = pd.Series(symbol).str.extract(
                r'(\w+)\s*(?:(\d{2}/\d{2}/\d{4})\s*[$]?(\d+(?:\.\d+)?)\s*([PC]|PUT|CALL))?'
            ).iloc[0]
            
            return pd.Series({
                'Ticker': match[0] if pd.notna(match[0]) else '',
                'Expiry': match[1] if pd.notna(match[1]) else None,
                'Strike': pd.to_numeric(match[2], errors='coerce'),
                'Option_Type': match[3] if pd.notna(match[3]) else None
            })

        # Apply the extraction to each row
        option_details = processed_df['Symbol'].apply(extract_option_details)
        processed_df[['Ticker', 'Expiry', 'Strike', 'Option_Type']] = option_details
        
        # Map different option type formats to Put/Call
        option_type_map = {'P': 'Put', 'C': 'Call', 'PUT': 'Put', 'CALL': 'Call'}
        processed_df['Option_Type'] = processed_df['Option_Type'].map(option_type_map)
        
        # Create the Type column based on Action and Option_Type
        def determine_type(row):
            action = str(row['Action']).strip()
            option_type = str(row['Option_Type']).strip() if pd.notna(row['Option_Type']) else ''
            
            # Handle special actions first
            if action in ['Expired', 'Assigned', 'Journal', 'Exchange or Exercise']:
                return f"{option_type} {action}" if option_type else action
            
            # Handle dividend and interest actions
            if action in ['Qualified Dividend', 'Cash Dividend']:
                return 'Dividend'
            if action in ['Credit Interest', 'Margin Interest']:
                return 'Interest'
            
            # Handle Buy/Sell actions
            if 'Sell' in action:
                if option_type == 'Put':
                    return 'Put Sell'
                elif option_type == 'Call':
                    return 'Call Sell'
                return 'Stock Sell'  # No option type means stock transaction
            
            if 'Buy' in action:
                if option_type == 'Put':
                    return 'Put Buy'
                elif option_type == 'Call':
                    return 'Call Buy'
                return 'Stock Buy'  # No option type means stock transaction
            
            return action  # Default to original action if no match
        
        processed_df['Type'] = processed_df.apply(determine_type, axis=1)
        
        # Create Status column based on expiry date
        def determine_status(row):
            if pd.isna(row['Expiry']):
                if 'Buy' in str(row['Action']) or 'Sell' in str(row['Action']):
                    return 'Stock Trade'
                return row['Action']  # Use Action for non-trade rows
            try:
                expiry_date = pd.to_datetime(row['Expiry'])
                current_date = pd.Timestamp.now()
                return 'Closed' if expiry_date < current_date else 'Open'
            except:
                return 'Unknown'
        
        processed_df['Status'] = processed_df.apply(determine_status, axis=1)
        
        # Calculate total amount including fees
        processed_df['Total_Amount'] = processed_df['Amount'] - processed_df['Fees & Com']
        
        # Fill NaN values in the processed columns
        processed_df = processed_df.fillna({
            'Posted_Date': '',
            'Transaction_Date': '',
            'Ticker': '',
            'Expiry': '',
            'Option_Type': '',
            'Strike': 0,
            'Type': '',
            'Status': ''
        })
        
        # Organize columns in the specified order
        columns = [
            'Posted_Date', 'Transaction_Date',  # Date columns
            'Action',                           # Action column
            'Ticker', 'Expiry', 'Option_Type', 'Strike',  # Summary columns
            'Type', 'Status',                   # New columns
            'Quantity', 'Price', 'Amount', 'Fees & Com', 'Total_Amount'  # Additional info
        ]
        
        # Remove Description column if it exists
        if 'Description' in processed_df.columns:
            processed_df = processed_df.drop('Description', axis=1)
        
        # Format numeric columns to 2 decimal places
        numeric_columns = ['Strike', 'Price', 'Amount', 'Fees & Com', 'Total_Amount']
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
        
        # Calculate total amount properly
        total_amount = processed_df['Total_Amount'].sum()
        
        # Prepare summary data with proper date formatting
        summary_data = {
            'total_trades': len(processed_df),
            'symbols_traded': processed_df['Ticker'].unique().tolist(),
            'date_range': f"{processed_df['Posted_Date'].min()} to {processed_df['Posted_Date'].max()}",
            'total_amount': f"${total_amount:,.2f}",
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
        query = data.get('query', '')
        csv_data = data.get('data', {}).get('processed_csv', '')
        
        if not query or not csv_data:
            return jsonify({'error': 'Missing query or data'}), 400
        
        # Convert CSV back to DataFrame
        df = pd.read_csv(StringIO(csv_data))
        
        # Process the query using Bedrock agent
        try:
            response = bedrock.invoke_agent(
                agentId=os.getenv('BEDROCK_AGENT_ID'),
                agentAliasId=os.getenv('BEDROCK_AGENT_ALIAS_ID'),
                sessionId='query-session',
                inputText=json.dumps({
                    'query': query,
                    'trading_data': csv_data
                })
            )
            
            # Process agent response
            if isinstance(response, dict):
                response_text = response.get('completion', '')
            else:
                response_text = str(response)
            
            return jsonify({'response': response_text})
            
        except Exception as e:
            print("Query Error:", str(e))
            return jsonify({'error': f'Error processing query: {str(e)}'}), 500
            
    except Exception as e:
        print("Server Error:", str(e))
        return jsonify({'error': f'Server error: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)