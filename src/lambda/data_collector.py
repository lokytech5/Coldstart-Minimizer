import boto3
import json
from datetime import datetime, timedelta


def lambda_handler(event, context):
    cloudwatch = boto3.client("cloudwatch")
    s3 = boto3.client("s3")
    bucket = "sagemaker-us-east-1-061039798341"
    key = "training/cloudwatch_metrics.json"

    # Fetch recent invocation data (last 24 hours, aggregated to 5-minute intervals)
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

    # Prepare data for incremental update
    existing_data = []
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        existing_data = json.loads(obj["Body"].read())
    except:
        pass
    new_data = [{"start": str(datetime.utcnow() - timedelta(minutes=i*5)), "target": [int(val)]}
                for i, val in enumerate(reversed(response["MetricDataResults"][0]["Values"] or [0]*288))]
    # Avoid excessive growth, keep recent half
    updated_data = existing_data + new_data[:len(new_data)//2]

    # Save updated data for next SageMaker retraining
    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(updated_data))
    return {"status": "updated", "data_points": len(updated_data)}
