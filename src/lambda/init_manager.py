import os
import json
import base64
import boto3
import dateutil.parser


def _is_apigw(event):
    return isinstance(event, dict) and ("resource" in event and "httpMethod" in event)


def _get_mode(event):
    # priority: Input.mode (StepFn or POST body) > queryStringParameters.mode
    mode = (event.get("Input", {}) or {}).get("mode")
    qsp = event.get("queryStringParameters") or {}
    return (mode or qsp.get("mode") or "auto").lower()


def lambda_handler(event, context):
    # defaults from Step Functions-style payload
    action = (event.get("Input", {}) or {}).get("action", "check")
    mode = _get_mode(event)

    # --- Parse API Gateway proxied JSON body for POST /jit-status ---
    if _is_apigw(event) and event.get("body"):
        body_str = event["body"]
        if event.get("isBase64Encoded"):
            body_str = base64.b64decode(body_str).decode()
        try:
            payload = json.loads(body_str)
            # support {"Input":{"action":"init","mode":"spike"}} or flat {"action":"init"}
            action = (payload.get("Input") or {}).get(
                "action", action) or payload.get("action", action)
            mode = (payload.get("Input") or {}).get(
                "mode", mode) or payload.get("mode", mode)
        except Exception:
            pass

    # Optional: gracefully handle browser preflight if this ever hits Lambda
    if _is_apigw(event) and event.get("httpMethod") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            },
            "body": ""
        }

    endpoint_name = os.environ["ENDPOINT_NAME"]
    bucket = os.environ["BUCKET_NAME"]
    threshold = float(os.environ.get("THRESHOLD", 300))
    target_function = os.environ.get("TARGET_FUNCTION", "target_function")

    s3 = boto3.client("s3")
    lam = boto3.client("lambda")
    rt = boto3.client("sagemaker-runtime")

    # choose data source (demo vs live)
    key = "training/cloudwatch_metrics.json"
    if mode == "spike":
        key = "training/demo_spike.json"
    elif mode == "calm":
        key = "training/demo_calm.json"

    # load & shape full series
    obj = s3.get_object(Bucket=bucket, Key=key)
    points = json.loads(obj["Body"].read())
    points.sort(key=lambda d: dateutil.parser.parse(d["start"]))

    series_start = points[0]["start"]
    series_target = [int(d["target"][0]) for d in points if d.get("target")]

    # forecast p50 & p90
    payload = {
        "instances": [{
            "start": series_start,
            "target": series_target
        }],
        "configuration": {
            "num_samples": 200,
            "output_types": ["quantiles"],
            "quantiles": ["0.5", "0.9"]
        }
    }
    resp = rt.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType="application/json",
        Body=json.dumps(payload)
    )
    pred = json.loads(resp["Body"].read())["predictions"][0]["quantiles"]
    q50 = [float(x) for x in pred["0.5"]]
    q90 = [float(x) for x in pred["0.9"]]

    will_spike = max(q90) >= threshold
    if mode == "spike":
        will_spike = True
    if mode == "calm":
        will_spike = False

    result = {
        "forecast": q50,
        "forecast_p90": q90,
        "trigger": will_spike,
        "threshold": threshold,
        "mode": mode
    }

    # action handling
    if action == "init":
        client_context = base64.b64encode(json.dumps(
            {"custom": {"COLD_START": "false"}}
        ).encode()).decode()
        lam.invoke(
            FunctionName=target_function,
            InvocationType="Event",
            ClientContext=client_context
        )
        body = {"status": "initialized", "mode": mode}
    else:
        body = result

    # API Gateway proxy response (with CORS)
    if _is_apigw(event):
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
            },
            "body": json.dumps(body)
        }
    return body
