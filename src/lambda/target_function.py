import boto3
import time
import numpy as np
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

s3 = boto3.client("s3")
bucket = "sagemaker-us-east-1-061039798341"


def lambda_handler(event, context):
    start_time = time.time()
    custom = getattr(getattr(context, "client_context", None), "custom", {})
    is_warm = (
        "COLD_START" not in custom or custom.get("COLD_START") != "true"
    )

    # Simulate e-commerce workload: product lookup with CPU-intensive tasks
    try:
        # Mock database query (S3 access)
        s3_response = s3.list_objects_v2(Bucket=bucket, Prefix="training/")
        item_count = len(s3_response.get("Contents", [])
                         ) if "Contents" in s3_response else 0

        # CPU-intensive task (e.g., matrix multiplication for recommendation engine)
        matrix_size = 100
        a = np.random.rand(matrix_size, matrix_size)
        b = np.random.rand(matrix_size, matrix_size)
        _ = np.dot(a, b)  # Simulate computation and avoid flake8 F841

        # Simulate API response
        response = {
            "status": "success",
            "item_count": item_count,
            "execution_time_ms": (time.time() - start_time) * 1000,
            "warm_start": is_warm
        }
        logger.info(f"Processed request: {response}")
        return response
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return {
            "status": "error",
            "execution_time_ms": (time.time() - start_time) * 1000,
            "warm_start": is_warm
        }


if __name__ == "__main__":
    # Simulate local execution for testing
    class MockContext:
        def __init__(self):
            self.client_context = type(
                'obj', (object,), {"custom": {"COLD_START": "true"}})()
    event = {}
    print(lambda_handler(event, MockContext()))
