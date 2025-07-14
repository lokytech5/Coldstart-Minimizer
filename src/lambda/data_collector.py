import boto3
import json
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def lambda_handler(event, context):
    cloudwatch = boto3.client("cloudwatch")
    s3 = boto3.client("s3")
    bucket = "sagemaker-us-east-1-061039798341"
    key = "training/cloudwatch_metrics.json"
    test_key = "training/test_data.json"

    # Check for test data first
    try:
        test_obj = s3.get_object(Bucket=bucket, Key=test_key)
        test_data = json.loads(test_obj["Body"].read())
        updated_data = test_data  # Use test data for spike simulation
        logger.info(f"Using test data from s3://{bucket}/{test_key}")
    except Exception as e:
        logger.warning(f"Test data not found, falling back to CloudWatch: {e}")
        # Fall back to CloudWatch data
        response = cloudwatch.get_metric_data(
            MetricDataQueries=[{
                "Id": "invocations",
                "MetricStat": {
                    "Metric": {"Namespace": "AWS/Lambda", "MetricName": "Invocations"},
                    "Period": 300,
                    "Stat": "Sum"
                }
            }],
            StartTime=datetime.utcnow() - timedelta(hours=24),
            EndTime=datetime.utcnow()
        )
        existing_data = []
        try:
            obj = s3.get_object(Bucket=bucket, Key=key)
            existing_data = json.loads(obj["Body"].read())
        except Exception:
            pass
        new_data = [
            {"start": str(datetime.utcnow() - timedelta(minutes=i*5)),
             "target": [int(val)]}
            for i, val in enumerate(reversed(response["MetricDataResults"][0]["Values"] or [0]*288))
        ]
        updated_data = existing_data + new_data[:len(new_data)//2]

    # Save updated data
    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(updated_data))
    return {"status": "updated", "data_points": len(updated_data)}
