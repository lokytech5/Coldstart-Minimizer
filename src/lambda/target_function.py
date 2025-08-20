import os
import time
import json
import logging

# ---------- logging ----------
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# ---------- cold/warm detector ----------
_IS_COLD = True          # flips to False after first invoke in THIS environment
_WARM_SEQ = 0            # counts warm hits in THIS environment only

# Make the demo work lighter by default.
# (Optionally override via env var WORK_SIZE without redeploying code.)
WORK_SIZE = int(os.environ.get("WORK_SIZE", "40"))


def cpu_intensive_task(size=WORK_SIZE):
    a = [[i + j for j in range(size)] for i in range(size)]
    b = [[i - j for j in range(size)] for i in range(size)]
    result = [[sum(a[i][k] * b[k][j] for k in range(size))
               for j in range(size)] for i in range(size)]
    return result[0][0]


def _emit_emf(function_name: str, cold_start: bool, exec_ms: float):
    """Emit CloudWatch Embedded Metric Format for dashboards."""
    metric = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": "ColdStartDemo",
                "Dimensions": [["FunctionName"]],
                "Metrics": [
                    {"Name": "WarmStart", "Unit": "Count"},
                    {"Name": "ExecTimeMs", "Unit": "Milliseconds"}
                ]
            }]
        },
        "FunctionName": function_name,
        "WarmStart": 0 if cold_start else 1,
        "ExecTimeMs": exec_ms
    }
    print(json.dumps(metric))  # EMF is picked up from stdout


def lambda_handler(event, context):
    global _IS_COLD, _WARM_SEQ
    t0 = time.time()

    # 1) Cold vs warm (per environment)
    cold = _IS_COLD
    if cold:
        _IS_COLD = False
        _WARM_SEQ = 0
    else:
        _WARM_SEQ += 1

    # 2) Was this explicitly pre-warmed by the JIT workflow?
    client_custom = getattr(
        getattr(context, "client_context", None), "custom", {}) or {}
    jit_prewarm = (client_custom.get("COLD_START") == "false")

    # 3) Friendly log line for your audience
    status = "AM COLD (#0)" if cold else f"AM WARM (#{_WARM_SEQ})"
    suffix = " (JIT prewarmed)" if (jit_prewarm and not cold) else ""
    logger.info(f"[WARM-COLD] {status}{suffix}")

    # 4) Do work (simulated)
    cpu_intensive_task()

    exec_ms = (time.time() - t0) * 1000.0
    logger.info(
        f"[WARM-COLD] done in {exec_ms:.2f} ms | warm={not cold} | jit={jit_prewarm} | size={WORK_SIZE}")

    # 5) Emit metrics for dashboards
    _emit_emf(context.function_name, cold, exec_ms)

    return {
        "status": "success",
        "cold_start": cold,
        "warm_seq": 0 if cold else _WARM_SEQ,
        "jit_prewarm": jit_prewarm,
        "execution_time_ms": exec_ms
    }
