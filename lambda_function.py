import json
import pandas as pd
from datetime import datetime
import boto3
from typing import Dict, Any

def load_trading_data(s3_bucket: str, file_key: str) -> pd.DataFrame:
    """Load trading data from S3 bucket"""
    s3 = boto3.client('s3')
    response = s3.get_object(Bucket=s3_bucket, Key=file_key)
    df = pd.read_csv(response['Body'])
    return df

def analyze_trades(event: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze trading data based on provided parameters"""
    try:
        # Load trading data from S3
        df = load_trading_data(
            s3_bucket=event['s3Bucket'],
            file_key=event['dataFile']
        )
        
        # Apply filters
        filtered_df = df.copy()
        if event.get('symbol'):
            filtered_df = filtered_df[filtered_df['Ticker'] == event['symbol']]
        
        if event.get('optionType') and event['optionType'] != 'ALL':
            filtered_df = filtered_df[filtered_df['Option_Type'] == event['optionType']]
            
        if event.get('dateRange'):
            start_date = datetime.strptime(event['dateRange']['startDate'], '%Y-%m-%d')
            end_date = datetime.strptime(event['dateRange']['endDate'], '%Y-%m-%d')
            filtered_df = filtered_df[
                (pd.to_datetime(filtered_df['Posted_Date']) >= start_date) &
                (pd.to_datetime(filtered_df['Posted_Date']) <= end_date)
            ]
            
        # Calculate metrics
        total_trades = len(filtered_df)
        profit_loss = filtered_df['Amount'].sum()
        winning_trades = len(filtered_df[filtered_df['Amount'] > 0])
        win_rate = (winning_trades / total_trades) if total_trades > 0 else 0
        avg_return = profit_loss / total_trades if total_trades > 0 else 0
        
        return {
            'totalTrades': total_trades,
            'profitLoss': round(profit_loss, 2),
            'winRate': round(win_rate * 100, 2),
            'averageReturn': round(avg_return, 2)
        }
        
    except Exception as e:
        return {
            'error': str(e)
        }

def calculate_stats(event: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate trading statistics based on specified metrics"""
    try:
        # Load trading data
        df = load_trading_data(
            s3_bucket=event['s3Bucket'],
            file_key=event['dataFile']
        )
        
        metric = event['metric']
        group_by = event['groupBy']
        
        if group_by == 'symbol':
            group_col = 'Ticker'
        elif group_by == 'option_type':
            group_col = 'Option_Type'
        else:  # month
            df['Month'] = pd.to_datetime(df['Posted_Date']).dt.to_period('M')
            group_col = 'Month'
            
        if metric == 'profit':
            results = df.groupby(group_col)['Amount'].sum()
        elif metric == 'volume':
            results = df.groupby(group_col)['Quantity'].sum()
        else:  # win_rate
            def calc_win_rate(group):
                wins = len(group[group['Amount'] > 0])
                total = len(group)
                return (wins / total * 100) if total > 0 else 0
            
            results = df.groupby(group_col).apply(calc_win_rate)
            
        return {
            'results': [
                {'group': str(group), 'value': round(float(value), 2)}
                for group, value in results.items()
            ]
        }
        
    except Exception as e:
        return {
            'error': str(e)
        }

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler"""
    try:
        action_type = event['actionGroup']
        
        if action_type == 'analyzeTrades':
            return analyze_trades(event)
        elif action_type == 'calculateStats':
            return calculate_stats(event)
        else:
            return {
                'error': f'Unknown action type: {action_type}'
            }
            
    except Exception as e:
        return {
            'error': f'Lambda execution error: {str(e)}'
        } 
def process_csv_file(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process uploaded CSV file and reorganize data"""
    try:
        # Load CSV from S3
        df = load_trading_data(
            s3_bucket=event['s3Bucket'],
            file_key=event['sourceFile']
        )
        
        # Process dates
        def process_date(row):
            date_str = str(row['Date']).strip()
            if 'as o' in date_str.lower():
                posted_date = date_str.split('as o')[0].strip()
                return pd.Series({
                    'Posted_Date': posted_date,
                    'Transaction_Date': posted_date
                })
            return pd.Series({
                'Posted_Date': date_str,
                'Transaction_Date': date_str
            })
        
        # Apply date processing
        date_df = df.apply(process_date, axis=1)
        df = pd.concat([df, date_df], axis=1)
        
        # Process symbol information
        def process_symbol(symbol_str):
            parts = str(symbol_str).split()
            if len(parts) >= 4:
                return {
                    'Ticker': parts[0],
                    'Expiry_Date': parts[1],
                    'Option_Type': parts[2],
                    'Strike_Price': parts[3]
                }
            return {
                'Ticker': symbol_str,
                'Expiry_Date': '',
                'Option_Type': '',
                'Strike_Price': ''
            }
        
        # Apply symbol processing
        symbol_data = df['Symbol'].apply(process_symbol).apply(pd.Series)
        
        # Create final dataframe
        processed_df = pd.concat([
            df[['Action', 'Quantity', 'Price', 'Fees & Comm', 'Amount']],
            date_df,
            symbol_data
        ], axis=1)
        
        # Save processed file
        output_key = f"processed/{event['sourceFile'].split('/')[-1]}"
        
        # Save to S3
        s3 = boto3.client('s3')
        s3.put_object(
            Bucket=event['s3Bucket'],
            Key=output_key,
            Body=processed_df.to_csv(index=False)
        )
        
        return {
            'status': 'success',
            'processedFile': output_key,
            'summary': {
                'totalRows': len(processed_df),
                'dateRange': f"{processed_df['Posted_Date'].min()} to {processed_df['Posted_Date'].max()}",
                'uniqueSymbols': processed_df['Ticker'].nunique()
            }
        }
        
    except Exception as e:
        return {
            'error': str(e)
        }