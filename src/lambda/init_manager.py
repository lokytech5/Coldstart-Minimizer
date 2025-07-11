import boto3
import json
import os
from datetime import datetime


def lambda_handler(event, context):
    action = event.get("Input", {}).get("action", "check")
    endpoint_name = os.environ["ENDPOINT_NAME"]
    bucket = os.environ["BUCKET_NAME"]
    threshold = float(os.environ.get("THRESHOLD", 130))
    s3 = boto3.client("s3")
    lambda_client = boto3.client("lambda")
    target_function = "init_manager"  # Replace with actual function name
    key = "training/cloudwatch_metrics.json"

    # Get latest training data for context
    obj = s3.get_object(Bucket=bucket, Key=key)
    training_data = json.loads(obj["Body"].read())
    latest_start = max(d["start"] for d in training_data)
    target_length = len(training_data[0]["target"])

    # Get forecast from the SageMaker endpoint
    predictor = boto3.client("sagemaker-runtime").invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType="application/json",
        Body=json.dumps({
            "instances": [{"start": latest_start, "target": [0] * target_length}],
            "configuration": {
                "num_samples": 100,
                "output_types": ["quantiles"],
                "quantiles": ["0.5"]
            }
        })
    )
    forecast = json.loads(predictor["Body"].read())[
        "predictions"][0]["quantiles"]["0.5"]

    if action == "check":
        if max(forecast) > threshold:
            print("Surge detected, initiating JIT initialization")
            return {"forecast": forecast, "trigger": True}
        return {"forecast": forecast, "trigger": False}
    elif action == "init":
        print("Initializing JIT")
        lambda_client.invoke(
            FunctionName=target_function,
            InvocationType="Event"  # Asynchronous warm-up
        )
        return {"status": "initialized"}
