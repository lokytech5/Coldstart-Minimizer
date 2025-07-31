import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()


def cpu_intensive_task(size=80):
    # Simple matrix multiplication in pure Python
    a = [[i + j for j in range(size)] for i in range(size)]
    b = [[i - j for j in range(size)] for i in range(size)]
    result = [[sum(a[i][k] * b[k][j] for k in range(size))
               for j in range(size)] for i in range(size)]
    return result[0][0]


def lambda_handler(event, context):
    start_time = time.time()

    # Check if this invocation is a cold start or warm start
    custom = getattr(getattr(context, "client_context", None), "custom", {})
    is_warm = ("COLD_START" not in custom or custom.get(
        "COLD_START") != "true")

    if is_warm:
        logger.info(
            "WARM invocation: Prewarmed by JIT workflow (Step Function)")
    else:
        logger.info("COLD invocation: Normal Lambda cold start")

    # CPU burn for demonstration
    cpu_intensive_task(size=80)

    exec_time = (time.time() - start_time) * 1000  # ms

    # Log and return result
    response = {
        "status": "success",
        "execution_time_ms": exec_time,
        "warm_start": is_warm
    }
    logger.info(f"Lambda completed. Warm: {is_warm} | Time: {exec_time:.2f}ms")
    return response


if __name__ == "__main__":
    class MockContext:
        def __init__(self, warm=False):
            self.client_context = type(
                'obj', (object,), {"custom": {"COLD_START": "true" if not warm else "false"}})()
    print(lambda_handler({}, MockContext(warm=True)))
    print(lambda_handler({}, MockContext(warm=False)))
