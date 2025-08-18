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
