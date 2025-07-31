import time
import boto3
import json

lambda_client = boto3.client("lambda", region_name="us-east-1")

# 1. Manually trigger init_manager to prewarm target_function
print("Invoking init_manager with action='init' to prewarm target_function...")

response = lambda_client.invoke(
    FunctionName="init_manager",
    InvocationType="RequestResponse",
    Payload=json.dumps({"Input": {"action": "init"}})
)

result = json.load(response["Payload"])
print("init_manager returned:", result)

# 2. Wait a moment (let JIT prewarm complete)
time.sleep(3)

# 3. Now invoke the target_function and check for "warm_start" in logs/response
print("Invoking target_function (should be WARM if JIT worked)...")

response = lambda_client.invoke(
    FunctionName="target_function",
    InvocationType="RequestResponse",
    Payload=json.dumps({})
)
result = json.load(response["Payload"])
print("target_function response:", result)

if result.get("warm_start"):
    print("\nSUCCESS! target_function is WARM (prewarmed by JIT). 🚀")
else:
    print("\nCOLD! target_function is COLD (JIT prewarm not effective). ❄️")
