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
            
            if action in ['Expired', 'Assigned', 'Journal', 'Exchange or Exercise']:
                return f"{option_type} {action}" if option_type else action
            
            if action in ['Qualified Dividend', 'Cash Dividend']:
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
        processed_df['Status'] = processed_df.apply(determine_status, axis=1)
        
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
        
        # Organize columns
        columns = [
            'Posted_Date', 'Transaction_Date',
            'Action',
            'Ticker', 'Expiry', 'Option_Type', 'Strike',
            'Type', 'Status',
            'Quantity', 'Price', 'Fees & Com', 'Amount'
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

def determine_status(row):
    return 'Closed' if pd.notna(row['Expiry']) and pd.to_datetime(row['Expiry']) < pd.Timestamp.now() else 'Open'

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
        
        # Calculate summary using the original Amount column
        total_amount = processed_df['Amount'].sum()
        
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
        if not bedrock:
            return jsonify({'error': 'Bedrock client not configured properly'}), 500

        # Check rate limit
        if not check_rate_limit():
            wait_time = RATE_LIMIT_PERIOD - (datetime.now() - request_timestamps[0]).total_seconds()
            return jsonify({
                'error': f'Rate limit exceeded. Please wait {int(wait_time)} seconds before trying again.',
                'retry_after': int(wait_time)
            }), 429

        data = request.json
        query = data.get('query', '')
        csv_data = data.get('data', {}).get('processed_csv', '')
        
        if not query or not csv_data:
            return jsonify({'error': 'Missing query or data'}), 400

        try:
            agent_id = os.getenv('BEDROCK_AGENT_ID')
            agent_alias_id = os.getenv('BEDROCK_AGENT_ALIAS_ID')

            if not agent_id or not agent_alias_id:
                return jsonify({'error': 'Missing Bedrock agent configuration'}), 500

            print(f"\nProcessing query request:")
            print(f"Query: {query}")
            print(f"Agent ID: {agent_id}")
            print(f"Agent Alias ID: {agent_alias_id}")
            print(f"CSV Data Available: {'Yes' if csv_data else 'No'}")

            # Add exponential backoff retry logic
            max_retries = 3
            retry_count = 0
            while retry_count < max_retries:
                try:
                    input_text = {
                        "query": query,
                        "trading_data": csv_data
                    }
                    input_json = json.dumps(input_text)
                    
                    print(f"Sending request to Bedrock agent (attempt {retry_count + 1})")
                    
                    response = bedrock.invoke_agent(
                        agentId=agent_id,
                        agentAliasId=agent_alias_id,
                        sessionId=f'trading-session-{int(time.time())}',  # Unique session ID
                        inputText=input_json,
                        enableTrace=True
                    )
                    
                    break  # If successful, exit retry loop
                    
                except Exception as e:
                    if 'ThrottlingException' in str(e) and retry_count < max_retries - 1:
                        retry_count += 1
                        wait_time = (2 ** retry_count)  # Exponential backoff
                        print(f"Rate limited, waiting {wait_time} seconds before retry...")
                        time.sleep(wait_time)
                    else:
                        raise  # Re-raise the exception if we're out of retries
            
            print("\nReceived response from Bedrock agent")
            
            # Process the EventStream response
            full_response = ""
            for event in response['completion']:
                if 'chunk' in event:
                    chunk_obj = event['chunk']
                    if 'bytes' in chunk_obj:
                        chunk_text = chunk_obj['bytes'].decode('utf-8')
                        print(f"Received chunk: {chunk_text}")
                        try:
                            chunk_data = json.loads(chunk_text)
                            if 'content' in chunk_data:
                                full_response += chunk_data['content']
                        except json.JSONDecodeError:
                            full_response += chunk_text

            if not full_response:
                full_response = "I apologize, but I couldn't process that query. Please try rephrasing your question."

            print(f"\nFinal response: {full_response}")
            
            return jsonify({
                'success': True,
                'response': full_response
            })

        except Exception as e:
            error_message = str(e)
            print(f"\nBedrock API Error:")
            print(f"Error Type: {type(e).__name__}")
            print(f"Error Message: {error_message}")
            
            if 'ThrottlingException' in error_message:
                return jsonify({
                    'error': 'Request rate limit exceeded. Please try again in a few seconds.',
                    'retry_after': 5
                }), 429
            elif 'ResourceNotFoundException' in error_message:
                return jsonify({
                    'error': 'The Bedrock agent could not be found. Please verify your Agent ID and Alias ID are correct and the agent is deployed in us-east-2.'
                }), 404
            elif 'AccessDeniedException' in error_message:
                return jsonify({
                    'error': 'Access denied. Please check your AWS credentials and IAM permissions for Bedrock.'
                }), 403
            else:
                return jsonify({
                    'error': f'Error processing query: {error_message}'
                }), 500

    except Exception as e:
        print(f"Query Error: {str(e)}")
        return jsonify({
            'error': f'Error processing request: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(debug=True)