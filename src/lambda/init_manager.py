import os
import json
import base64
import boto3
import dateutil.parser


def _is_apigw(event):
    return isinstance(event, dict) and ("resource" in event and "httpMethod" in event)


def _get_mode(event):
    # priority: Input.mode > queryStringParameters.mode
    mode = (event.get("Input", {}) or {}).get("mode")
    qsp = event.get("queryStringParameters") or {}
    return (mode or qsp.get("mode") or "auto").lower()


def _get_sfn_arn():
    """
    Resolve the Step Functions state machine ARN at runtime.
    - Prefer env SFN_ARN if provided.
    - Otherwise build from AWS_REGION + Account ID + SFN_NAME (default: ecommerce_jit_workflow).
    """
    arn = os.environ.get("SFN_ARN")
    if arn:
        return arn
    name = os.environ.get("SFN_NAME", "ecommerce_jit_workflow")
    region = os.environ.get("AWS_REGION", "us-east-1")
    try:
        account = boto3.client("sts").get_caller_identity()["Account"]
    except Exception:
        return None
    return f"arn:aws:states:{region}:{account}:stateMachine:{name}"


def _get_target(event):
    """Resolve target function from body/query with allow-list enforcement."""
    default = os.environ.get("TARGET_FUNCTION", "target_function")
    allowed = [x.strip() for x in (os.environ.get(
        "ALLOWED_TARGETS") or "").split(",") if x.strip()]

    body = {}
    if isinstance(event, dict) and event.get("body"):
        s = event["body"]
        if event.get("isBase64Encoded"):
            s = base64.b64decode(s).decode()
        try:
            body = json.loads(s)
        except Exception:
            pass

    qsp = (event.get("queryStringParameters") or {})
    target = (body.get("target")
              or (body.get("Input") or {}).get("target")
              or qsp.get("target")
              or default)

    if allowed and target not in allowed:
        raise ValueError(f"target '{target}' not allowed")
    return target


def lambda_handler(event, context):
    # ---- Inputs / mode -------------------------------------------------------
    action = (event.get("Input", {}) or {}).get("action", "check")
    mode = _get_mode(event)

    # Parse API Gateway proxied POST body (JSON)
    if _is_apigw(event) and event.get("body"):
        body_str = event["body"]
        if event.get("isBase64Encoded"):
            body_str = base64.b64decode(body_str).decode()
        try:
            payload = json.loads(body_str)
            action = (payload.get("Input") or {}).get(
                "action", action) or payload.get("action", action)
            mode = (payload.get("Input") or {}).get(
                "mode", mode) or payload.get("mode", mode)
        except Exception:
            pass

    # Handle CORS preflight if OPTIONS ever hits Lambda
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

    # ---- Env / clients -------------------------------------------------------
    endpoint_name = os.environ["ENDPOINT_NAME"]
    bucket = os.environ["BUCKET_NAME"]
    threshold = float(os.environ.get("THRESHOLD", 300))
    target_function = os.environ.get("TARGET_FUNCTION", "target_function")
    # <- add this env in Terraform to the rule name
    schedule_rule = os.environ.get("SCHEDULE_RULE")

    s3 = boto3.client("s3")
    lam = boto3.client("lambda")
    rt = boto3.client("sagemaker-runtime")
    events = boto3.client("events")  # <- NEW

    # ---- DEMO-GATE: If API Gateway POST called us, enable schedule + trigger SFN FIRST ----------
    if _is_apigw(event) and event.get("httpMethod") == "POST":
        # 1) Enable the disabled EventBridge rule so autoschedule takes over after the demo click
        if schedule_rule:
            try:
                state = (events.describe_rule(
                    Name=schedule_rule) or {}).get("State")
                if state != "ENABLED":
                    events.enable_rule(Name=schedule_rule)
                    print(f"[demo] Enabled schedule rule: {schedule_rule}")
                else:
                    print(f"[demo] Schedule already enabled: {schedule_rule}")
            except Exception as e:
                print(f"[warn] Enabling schedule failed: {e}")

        # 2) Kick the Step Function first (so the supervisor sees an immediate run)
        sfn_arn = _get_sfn_arn()
        if sfn_arn:
            try:
                sfn = boto3.client("stepfunctions")
                sfn.start_execution(
                    stateMachineArn=sfn_arn,
                    input=json.dumps({"Input": {"action": "check"}})
                )
                print(f"[demo] Started Step Function first: {sfn_arn}")
            except Exception as e:
                print(f"[warn] SFN start failed: {e}")
        else:
            print("[warn] No SFN ARN could be resolved; skipping SFN start")

    # ---- Data source selection -----------------------------------------------
    key = "training/cloudwatch_metrics.json"
    if mode == "spike":
        key = "training/demo_spike.json"
    elif mode == "calm":
        key = "training/demo_calm.json"

    # ---- Load & shape series --------------------------------------------------
    obj = s3.get_object(Bucket=bucket, Key=key)
    points = json.loads(obj["Body"].read())
    points.sort(key=lambda d: dateutil.parser.parse(d["start"]))

    series_start = points[0]["start"]
    series_target = [int(d["target"][0]) for d in points if d.get("target")]

    # ---- Forecast (p50 & p90) -------------------------------------------------
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
    if mode == "spike":  # force for demo
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

    # ---- Action handling ------------------------------------------------------
    if action == "init":
        client_context = base64.b64encode(json.dumps(
            {"custom": {"COLD_START": "false"}}
        ).encode()).decode()
        target_to_invoke = _get_target(event) if _is_apigw(
            event) else os.environ.get("TARGET_FUNCTION", "target_function")

        lam.invoke(
            FunctionName=target_to_invoke,
            InvocationType="Event",
            ClientContext=client_context
        )
        body = {"status": "initialized",
                "mode": mode, "target": target_to_invoke}
    else:  # "check"
        body = result

    # ---- API Gateway proxy response (with CORS) -------------------------------
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

    # Non-APIGW invocations (Step Functions / EventBridge)
    return body
