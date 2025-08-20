"use client";
import { useMemo, useState } from "react";
import { BarChart3, Flame, Gauge, LineChart, Power, RefreshCw, Rocket, ShieldCheck } from "lucide-react";
import { fetchStatus, triggerInit, type JitStatus } from "../app/lib/api";
import ForecastChart from "../app/components/ForecastChart";
import StatusPill from "../app/components/StatusPill";
import clsx from "clsx";
import Spinner from "./components/Spinner";
import LiveLogs from "./components/LiveLogs";

export default function JITDashboard() {
  const [status, setStatus] = useState<JitStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [initLoading, setInitLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasStarted, setHasStarted] = useState(false);

  const [mockMode, setMockMode] = useState<boolean>(() => !process.env.NEXT_PUBLIC_JIT_API_BASE);
  const API_BASE = process.env.NEXT_PUBLIC_JIT_API_BASE ?? "";

  const lastForecast = useMemo(() => status?.forecast?.at(-1) ?? null, [status]);
  const lastP90 = useMemo(() => status?.forecast_p90?.at(-1) ?? null, [status]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const s = await fetchStatus({ mock: mockMode, base: API_BASE });
      setStatus(s);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load status");
    } finally {
      setLoading(false);
    }
  };

  const onInit = async () => {
    setInitLoading(true);
    setError(null);
    try {
      await triggerInit({ mock: mockMode, base: API_BASE });
      setHasStarted(true);
      await load();
    } catch (e: any) {
      setError(e?.message ?? "Init failed");
    } finally {
      setInitLoading(false);
    }
  };

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      {/* Header */}
      <div className="mb-8 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">
            Just-In-Time Warm Dashboard
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Forecast-driven pre-warming to minimize Lambda cold starts.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 rounded-full border border-slate-700 bg-slate-800/60 px-3 py-1.5 text-sm text-slate-200 shadow-sm hover:shadow transition">
            <input
              type="checkbox"
              className="h-4 w-4 accent-indigo-500"
              checked={mockMode}
              onChange={(e) => setMockMode(e.target.checked)}
            />
            Mock mode
          </label>

          <button
            onClick={load}
            disabled={loading}
            className={clsx(
              "inline-flex items-center gap-2 rounded-lg bg-slate-800 px-3 py-2 text-sm font-medium text-slate-200 ring-1 ring-slate-700 hover:bg-slate-700 hover:ring-slate-600",
              loading && "opacity-60"
            )}
          >
            <RefreshCw className={clsx("h-4 w-4", loading && "animate-spin")} />
            Refresh
          </button>

          <button
            onClick={onInit}
            disabled={initLoading}
            className={clsx(
              "inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white shadow hover:bg-indigo-500",
              initLoading && "opacity-60"
            )}
          >
           {initLoading ? <Spinner size={16} /> : <Rocket className="h-4 w-4" />}
            {initLoading ? "Initializing…" : "Initialize JIT now"}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-6 rounded-lg border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
          {error}
        </div>
      )}

      {/* KPI Cards */}
      <section className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-400">
              <Gauge className="h-4 w-4" />
              <span className="text-xs uppercase tracking-wide">Trigger</span>
            </div>
            <StatusPill ok={!!status?.trigger} />
          </div>
          <div className="text-2xl font-semibold text-white">
            {status?.trigger ? "Yes" : "No"}
          </div>
          <p className="mt-1 text-xs text-slate-500">Forecast exceeded threshold?</p>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-sm">
          <div className="mb-3 flex items-center gap-2 text-slate-400">
            <Flame className="h-4 w-4" />
            <span className="text-xs uppercase tracking-wide">Threshold</span>
          </div>
          <div className="text-2xl font-semibold text-white">{status?.threshold ?? "—"}</div>
          <p className="mt-1 text-xs text-slate-500">Requests / min</p>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-sm">
          <div className="mb-3 flex items-center gap-2 text-slate-400">
            <LineChart className="h-4 w-4" />
            <span className="text-xs uppercase tracking-wide">Last Forecast</span>
          </div>
          <div className="text-2xl font-semibold text-white">{lastForecast ?? "—"}</div>
          <p className="mt-1 text-xs text-slate-500">Most recent prediction</p>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-sm">
          <div className="mb-3 flex items-center gap-2 text-slate-400">
            <ShieldCheck className="h-4 w-4" />
            <span className="text-xs uppercase tracking-wide">p90</span>
          </div>
          <div className="text-2xl font-semibold text-white">{lastP90 ?? "—"}</div>
          <p className="mt-1 text-xs text-slate-500">Upper-bound confidence</p>
        </div>
      </section>

    {/* Content grid */}
<section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
  {/* Left column: chart + logs stacked */}
  <div className="lg:col-span-2 flex flex-col gap-6">
    {/* Forecast card */}
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2 text-slate-400">
          <BarChart3 className="h-4 w-4" />
          <span className="text-sm font-medium text-slate-200">Forecast (next 10 mins)</span>
        </div>
        {!hasStarted && (
          <span className="text-xs text-slate-500">No data yet — click “Initialize JIT now”.</span>
        )}
      </div>

      <ForecastChart
        forecast={status?.forecast ?? []}
        p90={status?.forecast_p90 ?? []}
        threshold={status?.threshold ?? 0}
        loading={loading && !status}
      />
    </div>

    {/* Live logs card (its own card; do not nest inside the chart card) */}
    <LiveLogs base={API_BASE} mock={mockMode} />
  </div>

  {/* Right column: raw + manual init */}
  <div className="flex flex-col gap-4">
    {/* Raw response */}
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-sm">
      <div className="mb-2 text-sm font-medium text-slate-200">Raw response</div>
      <pre className="max-h-72 overflow-auto rounded-xl bg-slate-950 p-3 text-xs text-slate-200 ring-1 ring-slate-800">
{JSON.stringify(status ?? { message: "No data yet" }, null, 2)}
      </pre>
    </div>

    {/* Manual init */}
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-sm">
      <div className="mb-2 text-sm font-medium text-slate-200">Manual init call</div>
      <p className="mb-2 text-xs text-slate-400">
        We send a POST to <span className="font-mono">{API_BASE ? `${API_BASE}/jit-status` : "/jit-status"}</span> with:
      </p>
      <code className="rounded bg-slate-800 px-1 py-0.5 text-xs text-slate-200 ring-1 ring-slate-700">
        {'{"Input":{"action":"init"}}'}
      </code>
      <div className="mt-3">
        <button
          onClick={onInit}
          disabled={initLoading}
          className={clsx(
            "inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white shadow hover:bg-indigo-500",
            initLoading && "opacity-60"
          )}
        >
          <Power className="h-4 w-4" />
          Send init payload
        </button>
      </div>
    </div>
  </div>
</section>


      {/* Footer */}
      <footer className="mt-10 text-center text-xs text-slate-500">
        Built for the cold-start demo · {mockMode ? "Mock mode" : "Live mode"}
      </footer>

    </main>
  );
}
