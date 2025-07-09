import json
import boto3
import pandas as pd
from datetime import timedelta
import os

def process_dataset(bucket, input_key, output_key):
    s3 = boto3.client('s3')
    local_path = "/tmp/2020-Apr.csv"
    
    try:
        print(f"Downloading s3://{bucket}/{input_key} to {local_path}")
        s3.download_file(bucket, input_key, local_path)
    except Exception as e:
        print(f"Error downloading file: {e}")
        return
    
    try:
        print("Reading and processing CSV file...")
        df = pd.read_csv(local_path, encoding='ISO-8859-1')
        
        # Parse and floor timestamps
        df['event_time'] = pd.to_datetime(df['event_time'])
        df['time_bin'] = df['event_time'].dt.floor('5min')
        
        # Group by time_bin and count
        full_range = pd.date_range(start=df['time_bin'].min(), end=df['time_bin'].max(), freq='5min')
        grouped = df.groupby('time_bin').size().reindex(full_range, fill_value=0)
        
        request_counts = grouped.tolist()
        start_time = grouped.index[0].isoformat()
        
        # Format DeepAR JSON Line
        data = {
            "start": start_time,
            "target": request_counts
        }
        
        print(f"Uploading processed data to s3://{bucket}/{output_key}")
        s3.put_object(
            Bucket=bucket,
            Key=output_key,
            Body=json.dumps([data]),  # Wrap in list for batch training format
            ContentType='application/json'
        )
        
        print("Upload complete.")
    except Exception as e:
        print(f"Error during processing: {e}")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

if __name__ == "__main__":
    bucket = "sagemaker-us-east-1-061039798341"
    input_key = "2020-Apr.csv"
    output_key = "training/train.json"
    process_dataset(bucket, input_key, output_key)
