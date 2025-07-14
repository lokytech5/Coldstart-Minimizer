import boto3
import json
import os
import base64


def lambda_handler(event, context):
    action = event.get("Input", {}).get("action", "check")
    endpoint_name = os.environ["ENDPOINT_NAME"]
    bucket = os.environ["BUCKET_NAME"]
    threshold = float(os.environ.get("THRESHOLD", 130))
    s3 = boto3.client("s3")
    lambda_client = boto3.client("lambda")
    target_function = os.environ.get("TARGET_FUNCTION", "init_manager")
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
            "instances": [{"start": latest_start, "target": [d["target"][0] for d in training_data[-12:]]}],
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
        return {"forecast": forecast, "trigger": False}  # <-- fixed here
    elif action == "init":
        print("Initializing JIT")
        client_context = base64.b64encode(
            json.dumps({"custom": {"COLD_START": "false"}}).encode()
        ).decode()
        lambda_client.invoke(
            FunctionName=target_function,
            InvocationType="Event",
            ClientContext=client_context
        )
        return {"status": "initialized"}
