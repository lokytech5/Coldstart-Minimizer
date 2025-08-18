import os
import json
import boto3
import logging
from datetime import datetime, timedelta

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BUCKET_NAME = os.environ.get("BUCKET_NAME", "sagemaker-us-east-1-061039798341")
# the Lambda you're modeling
FUNCTION_NAME = os.environ.get("FUNCTION_NAME", "target_function")
KEY = os.environ.get("OUTPUT_KEY", "training/cloudwatch_metrics.json")
# change back to train.json after testing
TEST_KEY = os.environ.get(
    "TEST_KEY", "training/ecommerce_invocation_counts_demon.json")

# 1-minute points, 24h lookback (override via env if needed)
PERIOD_SECONDS = int(os.environ.get("PERIOD_SECONDS", "60"))
LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", "24"))


def _iso_no_tz(dt: datetime) -> str:
    """Return ISO string without timezone, seconds precision."""
    return dt.replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")


def lambda_handler(event, context):
    cloudwatch = boto3.client("cloudwatch")
    s3 = boto3.client("s3")

    # --- 1) Test override (if present) ---
    try:
        test_obj = s3.get_object(Bucket=BUCKET_NAME, Key=TEST_KEY)
        test_data = json.loads(test_obj["Body"].read())
        logger.info(
            "Using test data from s3://%s/%s (%d points)",
            BUCKET_NAME, TEST_KEY, len(test_data)
        )
        updated_data = _clean_and_sort(test_data)
        _write_series(s3, updated_data)
        return {"status": "updated (test)", "data_points": len(updated_data)}
    except Exception as e:
        logger.info(
            "No test data at s3://%s/%s → CloudWatch. (%s)",
            BUCKET_NAME, TEST_KEY, e
        )

    # --- 2) Fetch existing series (if any) ---
    existing = []
    try:
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=KEY)
        existing = json.loads(obj["Body"].read())
        logger.info("Loaded existing series: %d points", len(existing))
    except Exception:
        logger.info("No existing series yet; starting fresh.")

    # --- 3) Pull 1-min Invocations for the target function ---
    end = datetime.utcnow()
    start = end - timedelta(hours=LOOKBACK_HOURS)

    resp = cloudwatch.get_metric_data(
        MetricDataQueries=[{
            "Id": "invocations",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/Lambda",
                    "MetricName": "Invocations",
                    "Dimensions": [{
                        "Name": "FunctionName",
                        "Value": FUNCTION_NAME
                    }]
                },
                "Period": PERIOD_SECONDS,
                "Stat": "Sum"
            }
        }],
        StartTime=start,
        EndTime=end,
        ScanBy="TimestampAscending"
    )

    results = resp.get("MetricDataResults", [])
    values = results[0].get("Values", []) if results else []
    timestamps = results[0].get("Timestamps", []) if results else []

    # Pair, sort, and normalize
    pairs = sorted(zip(timestamps, values), key=lambda p: p[0])
    cw_points = [
        {"start": _iso_no_tz(ts), "target": [int(v)]}
        for ts, v in pairs
        if v is not None
    ]
    logger.info(
        "Fetched %d CloudWatch points (period=%ss)",
        len(cw_points),
        PERIOD_SECONDS
    )

    # --- 4) Merge (existing + new), sort, de-dupe by timestamp ---
    merged = _merge_series(existing, cw_points)
    _write_series(s3, merged)
    return {"status": "updated", "data_points": len(merged)}


def _merge_series(existing, new_points):
    """Append, sort by 'start', and drop duplicates (keep latest)."""
    if not isinstance(existing, list):
        existing = []
    if not isinstance(new_points, list):
        new_points = []

    # build map of start -> record (new overwrites old)
    by_ts = {}
    for d in existing:
        if isinstance(d, dict) and "start" in d and "target" in d:
            by_ts[str(d["start"])] = d
    for d in new_points:
        if isinstance(d, dict) and "start" in d and "target" in d:
            by_ts[str(d["start"])] = d

    cleaned = [by_ts[k] for k in sorted(by_ts.keys())]
    logger.info("Merged series size: %d", len(cleaned))
    return cleaned


def _clean_and_sort(points):
    """Ensure proper schema + sorted ascending by 'start'."""
    def _ok(d):
        return (
            isinstance(d, dict) and
            "start" in d and
            "target" in d and
            isinstance(d["target"], list) and
            len(d["target"]) > 0
        )

    safe = []
    for d in points:
        if _ok(d):
            try:
                v = int(d["target"][0])
                safe.append({"start": str(d["start"]), "target": [v]})
            except Exception:
                continue
    safe.sort(key=lambda d: str(d["start"]))
    return safe


def _write_series(s3_client, series):
    s3_client.put_object(Bucket=BUCKET_NAME, Key=KEY, Body=json.dumps(series))
    logger.info("Wrote %d points to s3://%s/%s", len(series), BUCKET_NAME, KEY)
