"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Pause, Play, RefreshCw, ScrollText } from "lucide-react";
import clsx from "clsx";
import Spinner from "./Spinner";
import { fetchLogs, type LogsItem, type LogsResponse } from "@/app/lib/api";

type Props = {
  base: string;
  mock: boolean;
  pollMs?: number;
};

const GROUPS: { key: "target" | "init" | "collector" | "sfn"; label: string }[] = [
  { key: "target", label: "target_function" },
  { key: "init", label: "init_manager" },
  { key: "collector", label: "data_collector" },
  { key: "sfn", label: "step_functions" },
];

export default function LiveLogs({ base, mock, pollMs = 2000 }: Props) {
  const [group, setGroup] = useState<"target" | "init" | "collector" | "sfn">("target");
  const [minutes, setMinutes] = useState(15);
  const [pattern, setPattern] = useState<string>("[WARM-COLD]"); // nice demo default
  const [items, setItems] = useState<LogsItem[]>([]);
  const [nextToken, setNextToken] = useState<string | undefined>(undefined);
  const [live, setLive] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  const listRef = useRef<HTMLDivElement>(null);
  const seen = useRef<Set<string>>(new Set()); // de-dup across polls

  const clearAll = useCallback(() => {
    setItems([]);
    setNextToken(undefined);
    seen.current.clear();
  }, []);

  const scrollToBottom = useCallback(() => {
    if (!autoScroll) return;
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [autoScroll]);

  const merge = useCallback((resp: LogsResponse) => {
    const fresh: LogsItem[] = [];
    for (const it of resp.items) {
      const key = `${it.ts}|${it.stream}|${it.message}`;
      if (!seen.current.has(key)) {
        seen.current.add(key);
        fresh.push(it);
      }
    }
    if (fresh.length) {
      setItems((prev) => [...prev, ...fresh]);
      // let the browser paint, then scroll
      setTimeout(scrollToBottom, 0);
    }
    setNextToken(resp.next);
  }, [scrollToBottom]);

  const load = useCallback(
    async ({ reset = false }: { reset?: boolean } = {}) => {
      setLoading(true);
      setError(null);
      try {
        const resp = await fetchLogs({
          base,
          mock,
          group,
          minutes,
          pattern,
          limit: 100,
          next: reset ? undefined : nextToken,
        });
        merge(resp);
      } catch (e: any) {
        setError(e?.message ?? "Failed to load logs");
      } finally {
        setLoading(false);
      }
    },
    [base, mock, group, minutes, pattern, nextToken, merge]
  );

  // initial + refetch when group/minutes/pattern change
  useEffect(() => {
    clearAll();
    load({ reset: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [group, minutes, pattern]);

  // polling
  useEffect(() => {
    if (!live) return;
    const id = setInterval(() => load(), pollMs);
    return () => clearInterval(id);
  }, [live, load, pollMs]);

  // auto-scroll if user is near bottom; stop autoscroll if they scroll up
  const onScroll = useCallback(() => {
    const el = listRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setAutoScroll(nearBottom);
  }, []);

  const headerRight = useMemo(
    () => (
      <div className="flex items-center gap-2">
        <button
          onClick={() => setLive((v) => !v)}
          className={clsx(
            "inline-flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium ring-1",
            live
              ? "bg-emerald-600/15 text-emerald-300 ring-emerald-600/30 hover:bg-emerald-600/25"
              : "bg-slate-800 text-slate-300 ring-slate-700 hover:bg-slate-700"
          )}
          title={live ? "Pause live tail" : "Resume live tail"}
        >
          {live ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
          {live ? "Live" : "Paused"}
        </button>
        <button
          onClick={() => load()}
          className={clsx(
            "inline-flex items-center gap-2 rounded-lg bg-slate-800 px-2.5 py-1.5 text-xs font-medium text-slate-200 ring-1 ring-slate-700 hover:bg-slate-700",
            loading && "opacity-60"
          )}
          title="Refresh now"
        >
          <RefreshCw className={clsx("h-3.5 w-3.5", loading && "animate-spin")} />
          Refresh
        </button>
      </div>
    ),
    [live, loading, load]
  );

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-sm">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-slate-400">
          <ScrollText className="h-4 w-4" />
          <span className="text-sm font-medium text-slate-200">Live logs</span>
        </div>
        {headerRight}
      </div>

      {/* Controls */}
      <div className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
        <select
          value={group}
          onChange={(e) => setGroup(e.target.value as any)}
          className="rounded-lg border border-slate-700 bg-slate-800/70 px-2 py-1.5 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-600"
        >
          {GROUPS.map((g) => (
            <option key={g.key} value={g.key}>
              {g.label}
            </option>
          ))}
        </select>

        <select
          value={minutes}
          onChange={(e) => setMinutes(parseInt(e.target.value, 10))}
          className="rounded-lg border border-slate-700 bg-slate-800/70 px-2 py-1.5 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-600"
        >
          {[5, 15, 30, 60].map((m) => (
            <option key={m} value={m}>
              Last {m} min
            </option>
          ))}
        </select>

        <input
          value={pattern}
          onChange={(e) => setPattern(e.target.value)}
          placeholder="CloudWatch filter pattern (ex: [WARM-COLD] or ?WarmStart=1)"
          className="rounded-lg border border-slate-700 bg-slate-800/70 px-2 py-1.5 text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-600"
        />
      </div>

      {/* List */}
      <div
        ref={listRef}
        onScroll={onScroll}
        className="h-64 overflow-auto rounded-xl bg-slate-950 p-3 ring-1 ring-slate-800"
      >
        {items.length === 0 && !loading && !error && (
          <div className="grid h-full place-items-center text-sm text-slate-400">
            No log lines yet.
          </div>
        )}
        {items.map((it, idx) => (
          <div key={`${it.ts}-${idx}`} className="whitespace-pre-wrap font-mono text-xs leading-5">
            <span className="text-slate-500">{new Date(it.ts).toLocaleTimeString()} </span>
            <span className="text-slate-400">[{it.stream.split("/").at(-1)}]</span>{" "}
            <span className="text-slate-200">{it.message.trimEnd()}</span>
          </div>
        ))}
        {loading && (
          <div className="mt-2 flex items-center justify-center gap-2 text-xs text-slate-400">
            <Spinner size={14} />
            <span>Loading…</span>
          </div>
        )}
        {error && (
          <div className="mt-2 rounded-md border border-rose-400/20 bg-rose-500/10 px-2 py-1 text-xs text-rose-300">
            {error}
          </div>
        )}
      </div>

      {/* Pager */}
      <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
        <div>
          Showing <span className="text-slate-200">{items.length}</span> lines
          {autoScroll ? " · auto-scroll" : " · scroll paused"}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => load()} // continue with nextToken
            disabled={!nextToken || loading}
            className={clsx(
              "rounded-md px-2 py-1 ring-1",
              nextToken && !loading
                ? "bg-slate-800 text-slate-200 ring-slate-700 hover:bg-slate-700"
                : "bg-slate-900/40 text-slate-500 ring-slate-800 cursor-not-allowed"
            )}
          >
            Load more
          </button>
          <button
            onClick={() => {
              clearAll();
              load({ reset: true });
            }}
            className="rounded-md bg-slate-800 px-2 py-1 text-slate-200 ring-1 ring-slate-700 hover:bg-slate-700"
          >
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}
