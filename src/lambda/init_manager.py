import os
import boto3
import json
import base64


def lambda_handler(event, context):
    action = event.get("Input", {}).get("action", "check")
    endpoint_name = os.environ["ENDPOINT_NAME"]
    bucket = os.environ["BUCKET_NAME"]
    threshold = float(os.environ.get("THRESHOLD", 130))
    s3 = boto3.client("s3")
    lambda_client = boto3.client("lambda")
    stepfunctions = boto3.client("stepfunctions")
    target_function = os.environ.get("TARGET_FUNCTION", "init_manager")
    state_machine_arn = "arn:aws:states:us-east-1:061039798341:stateMachine:ecommerce_jit_workflow"
    key = "training/cloudwatch_metrics.json"

    obj = s3.get_object(Bucket=bucket, Key=key)
    training_data = json.loads(obj["Body"].read())
    latest_start = max(d["start"] for d in training_data)
    predictor = boto3.client("sagemaker-runtime").invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType="application/json",
        Body=json.dumps({
            "instances": [
                {
                    "start": latest_start,
                    "target": [d["target"][0] for d in training_data[-12:]]
                }
            ],
            "configuration": {
                "num_samples": 100,
                "output_types": ["quantiles"],
                "quantiles": ["0.5"]
            }
        })
    )
    forecast = json.loads(predictor["Body"].read())[
        "predictions"][0]["quantiles"]["0.5"]

    # Check if called from Step Functions or API Gateway
    is_apigw = "resource" in event and "httpMethod" in event
    result = None

    if action == "check":
        result = {"forecast": forecast, "trigger": max(forecast) > threshold}
        if is_apigw:
            # For API Gateway, wrap for proxy integration
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(result)
            }
        else:
            # For Step Functions, return as-is
            return result

    elif action == "init":
        client_context = base64.b64encode(json.dumps(
            {"custom": {"COLD_START": "false"}}).encode()).decode()
        lambda_client.invoke(
            FunctionName=target_function,
            InvocationType="Event",
            ClientContext=client_context
        )
        result = {"status": "initialized"}
        if is_apigw:
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(result)
            }
        else:
            return result
