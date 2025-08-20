export type JitStatus = {
  forecast: number[];
  forecast_p90: number[];
  trigger: boolean;
  threshold: number;
  mode?: string;
} | null;

const MOCK: JitStatus = {
  forecast: [127.7, 126.24, 125.21, 123.52, 124.09, 122.64, 125.23, 127.55, 130.86, 162.68],
  forecast_p90: [181.22, 184.08, 180.88, 170.76, 177.44, 171.95, 178.86, 171.44, 180.65, 229.61],
  trigger: true,
  threshold: 100,
  mode: "mock",
};

export async function fetchStatus(opts: { mock: boolean; base: string }): Promise<JitStatus> {
  if (opts.mock || !opts.base) {
    await sleep(300);
    return MOCK;
  }
  const res = await fetch(`${opts.base}/jit-status`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET /jit-status failed (${res.status})`);
  const data = await res.json();
  // Your backend returns an array with one object — normalize it.
  if (Array.isArray(data)) return data[0] ?? null;
  return data ?? null;
}

export async function triggerInit(opts: { mock: boolean; base: string }) {
  if (opts.mock || !opts.base) {
    await sleep(400);
    return { ok: true, mock: true };
  }
  const body = { Input: { action: "init" } };
  const res = await fetch(`${opts.base}/jit-status`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST /jit-status failed (${res.status})`);
  return res.json();
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

export type LogsItem = { ts: string; message: string; stream: string };
export type LogsResponse = { group: string; count: number; items: LogsItem[]; next?: string };

export async function fetchLogs(opts: {
  base: string;
  mock: boolean;
  group?: "target" | "init" | "collector" | "sfn";
  minutes?: number;
  pattern?: string;
  limit?: number;
  next?: string;
}): Promise<LogsResponse> {
  const { base, mock, group = "target", minutes = 15, pattern, limit = 100, next } = opts;

  if (mock || !base) {
    // synthesize a few friendly lines
    const now = Date.now();
    const mk = (i: number, warm = true): LogsItem => ({
      ts: new Date(now - (20 - i) * 1000).toISOString(),
      stream: "mock/stream",
      message: warm
        ? `[WARM-COLD] AM WARM (#${i}) | done in ${(300 + i * 7).toFixed(2)} ms | warm=true`
        : `[WARM-COLD] AM COLD (#0) | done in ${(430 + i * 9).toFixed(2)} ms | warm=false`,
    });
    const items = [mk(0, false), ...Array.from({ length: 12 }, (_, i) => mk(i + 1, true))];
    return { group: `/mock/${group}`, count: items.length, items };
  }

  const params = new URLSearchParams({
    group,
    minutes: String(minutes),
    limit: String(limit),
  });
  if (pattern) params.set("pattern", pattern);
  if (next) params.set("next", next);

  const res = await fetch(`${base}/logs?${params.toString()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET /logs failed (${res.status})`);
  return res.json();
}

