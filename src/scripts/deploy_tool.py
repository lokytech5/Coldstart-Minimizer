import boto3
import json
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def prepare_test_data(bucket="sagemaker-us-east-1-061039798341"):
    """Prepare synthetic test data for local testing."""
    s3 = boto3.client("s3")
    test_data = [
        {"start": str(datetime.utcnow() - timedelta(minutes=i*5)),
         "target": [100 + i*10]}
        for i in range(12)  # 1 hour of data, 5-minute intervals
    ]
    try:
        s3.put_object(Bucket=bucket, Key="training/test_data.json",
                      Body=json.dumps(test_data))
        logger.info(
            f"Uploaded test data to s3://{bucket}/training/test_data.json")
    except Exception as e:
        logger.error(f"Failed to upload test data: {e}")
        raise


def invoke_lambda(function_name, payload):
    """Invoke a Lambda function locally or via AWS for testing."""
    lambda_client = boto3.client("lambda")
    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload)
        )
        result = json.load(response["Payload"])
        logger.info(f"Invoked {function_name}: {result}")
        return result
    except Exception as e:
        logger.error(f"Failed to invoke {function_name}: {e}")
        raise


def test_workflow():
    """Test the end-to-end workflow locally."""
    bucket = "sagemaker-us-east-1-061039798341"
    threshold = 130

    # Step 1: Prepare test data
    prepare_test_data(bucket)

    # Step 2: Simulate data_collector
    data_collector_payload = {}
    data_collector_result = invoke_lambda(
        "data_collector", data_collector_payload)
    if data_collector_result.get("status") != "updated":
        logger.error("data_collector test failed")
        return False

    # Step 3: Simulate init_manager check
    init_manager_check_payload = {"Input": {"action": "check"}}
    init_manager_check_result = invoke_lambda(
        "init_manager", init_manager_check_payload)
    forecast = init_manager_check_result.get("forecast", [])
    trigger = init_manager_check_result.get("trigger", False)
    if not forecast or (max(forecast) > threshold and not trigger):
        logger.error("init_manager check test failed")
        return False

    # Step 4: Simulate init_manager init (if triggered)
    if trigger:
        init_manager_init_payload = {"Input": {"action": "init"}}
        init_manager_init_result = invoke_lambda(
            "init_manager", init_manager_init_payload)
        if init_manager_init_result.get("status") != "initialized":
            logger.error("init_manager init test failed")
            return False

    logger.info("Workflow test completed successfully")
    return True


def main():
    """Main function to run the testing tool."""
    logger.info("Starting ColdStart workflow test...")
    if test_workflow():
        logger.info("All tests passed. Ready to push to CI/CD pipeline.")
    else:
        logger.warning(
            "Tests failed. Review logs and fix issues before pushing.")


if __name__ == "__main__":
    main()
