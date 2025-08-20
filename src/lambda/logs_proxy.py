import os
import json
import boto3
from datetime import datetime, timedelta, timezone

logs = boto3.client("logs")

# Map short names -> log group names (override via env)
LOG_GROUPS = {
    "target": os.environ.get("LOG_GROUP_TARGET", "/aws/lambda/target_function"),
    "init": os.environ.get("LOG_GROUP_INIT", "/aws/lambda/init_manager"),
    "collector": os.environ.get("LOG_GROUP_COLLECTOR", "/aws/lambda/data_collector"),
    "sfn": os.environ.get("LOG_GROUP_SFN", "/aws/states/ecommerce_jit_workflow"),
}


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
        },
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    # Query params
    qsp = (event.get("queryStringParameters") or {})
    group_key = (qsp.get("group") or "target").lower()
    group = LOG_GROUPS.get(group_key, LOG_GROUPS["target"])

    # time window
    minutes = int(qsp.get("minutes", "15"))
    start_ts = int(
        (datetime.now(timezone.utc) - timedelta(minutes=minutes)).timestamp() * 1000
    )

    # optional CloudWatch Logs filterPattern (e.g., WARM-COLD, ERROR, ?WarmStart=1)
    pattern = qsp.get("pattern")  # None means no server-side filter
    limit = int(qsp.get("limit", "100"))
    next_token = qsp.get("next")  # pagination

    kwargs = {
        "logGroupName": group,
        "startTime": start_ts,
        "interleaved": True,
        "limit": limit,
    }
    if pattern:
        kwargs["filterPattern"] = pattern
    if next_token:
        kwargs["nextToken"] = next_token

    try:
        resp = logs.filter_log_events(**kwargs)
    except logs.exceptions.ResourceNotFoundException:
        return _response(404, {"error": f"log group not found: {group}", "group": group})
    except Exception as e:
        return _response(500, {"error": str(e)})

    items = []
    for ev in resp.get("events", []):
        items.append({
            "ts": datetime.fromtimestamp(ev["timestamp"] / 1000, tz=timezone.utc).isoformat(),
            "message": ev.get("message", ""),
            "stream": ev.get("logStreamName", ""),
        })

    return _response(200, {
        "group": group,
        "count": len(items),
        "items": items,
        "next": resp.get("nextToken"),  # pass back for pagination
    })
