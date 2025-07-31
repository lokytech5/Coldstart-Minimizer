import boto3
import json
import time
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def prepare_test_data(bucket="sagemaker-us-east-1-061039798341"):
    s3 = boto3.client("s3")
    now = datetime.utcnow()
    test_data = [
        {"start": str(now - timedelta(minutes=i*5)), "target": [100 + i*5]}
        for i in range(5)  # Baseline
    ]
    test_data.extend([
        {"start": str(now - timedelta(minutes=25)), "target": [350]},
        {"start": str(now - timedelta(minutes=30)), "target": [420]},
        {"start": str(now - timedelta(minutes=35)), "target": [390]},
    ])
    test_data.extend([
        {"start": str(now - timedelta(minutes=40 + i*5)), "target": [90]}
        for i in range(3)  # After spike
    ])
    s3.put_object(Bucket=bucket, Key="training/test_data.json",
                  Body=json.dumps(test_data))
    logger.info("Uploaded test_data.json with spike.")


def invoke_step_function(state_machine_arn, input_payload=None):
    sfn = boto3.client("stepfunctions")
    input_payload = input_payload or {"Input": {"action": "check"}}
    logger.info("Starting Step Function execution...")
    response = sfn.start_execution(
        stateMachineArn=state_machine_arn,
        input=json.dumps(input_payload)
    )
    exec_arn = response["executionArn"]
    logger.info(f"Execution started: {exec_arn}")

    # Wait for completion
    for _ in range(60):
        desc = sfn.describe_execution(executionArn=exec_arn)
        status = desc["status"]
        if status in ["SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"]:
            break
        time.sleep(3)
    desc = sfn.describe_execution(executionArn=exec_arn)
    logger.info(f"Step Function execution finished: {desc['status']}")
    logger.info(f"Output: {desc.get('output')}")
    return desc


def main():
    bucket = "sagemaker-us-east-1-061039798341"
    step_function_arn = "arn:aws:states:us-east-1:061039798341:stateMachine:ecommerce_jit_workflow"
    prepare_test_data(bucket)
    result = invoke_step_function(step_function_arn)
    print("\n==== Step Function Output ====\n")
    print(result.get("output"))
    print("\n=============================\n")


if __name__ == "__main__":
    main()
