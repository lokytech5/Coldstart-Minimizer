import json
import boto3
import pandas as pd
from datetime import datetime, timedelta
import os

def process_dataset(bucket, input_key, output_key):
    s3 = boto3.client('s3')
    
    # Download the file with error handling
    local_path = "/tmp/2020-Apr.csv"
    try:
        s3.download_file(bucket, input_key, local_path)
    except Exception as e:
        print(f"Error downloading file: {e}")
        return
    
    # Load and process the dataset
    try:
        df = pd.read_csv(local_path, encoding='ISO-8859-1')
        df['event_time'] = pd.to_datetime(df['event_time'])
        
        # Aggregate events by 5-minute intervals
        df['time_bin'] = df['event_time'].dt.floor('5min')
        request_counts = df.groupby('time_bin').size().reindex(
            pd.date_range(df['time_bin'].min(), df['time_bin'].max(), freq='5min'),
            fill_value=0
        ).tolist()
        
        timestamps = [df['time_bin'].min() + timedelta(minutes=5 * i) for i in range(len(request_counts))]
        
        data = {
            "start": timestamps[0].isoformat(),
            "target": request_counts,
            "cat": [0],
            "dynamic_feat": []
        }
        
        # Upload processed data to S3
        s3.put_object(
            Bucket=bucket,
            Key=output_key,
            Body=json.dumps([data])
        )
        print(f"Uploaded processed data to s3://{bucket}/{output_key}")
    except Exception as e:
        print(f"Error processing data: {e}")
        return
    
    # Clean up
    os.remove(local_path)

if __name__ == "__main__":
    bucket = "sagemaker-us-east-1-061039798341"
    input_key = "2020-Apr.csv"  # Updated to match root-level file
    output_key = "training/train.json"
    process_dataset(bucket, input_key, output_key)
