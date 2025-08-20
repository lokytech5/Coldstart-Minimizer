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

type GroupKey = "target" | "init" | "collector" | "sfn";

const GROUPS: { key: GroupKey; label: string }[] = [
  { key: "target", label: "target_function" },
  { key: "init", label: "init_manager" },
  { key: "collector", label: "data_collector" },
  { key: "sfn", label: "step_functions" },
];

const PRESETS = [
  { label: "All", value: "" },
  { label: "Errors", value: "ERROR" },
  { label: "Warm", value: "{ $.WarmStart = 1 }" }, // JSON filter
  { label: "Cold", value: "{ $.WarmStart = 0 }" },
  { label: "Reports", value: "REPORT" },
];

/* ---------------- SFN helpers (label-first rendering) ---------------- */

function parseJSONSafe(s: string): any | null {
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

// Label pill text for SFN state
function sfnStateLabel(obj: any): string {
  return (
    obj?.details?.name ??
    obj?.details?.resource ??
    obj?.details?.resourceType ??
    "Step"
  );
}

// Short execution id tail for the bracket tag
function sfnExecTail(obj: any): string | null {
  const tail = (obj?.execution_arn as string | undefined)?.split(":").pop();
  return tail ? tail.slice(-8) : null;
}

// Color for the status/type badge
function sfnTypeClass(type?: string) {
  switch (type) {
    case "ExecutionStarted":
    case "TaskStarted":
    case "TaskStateEntered":
    case "ChoiceStateEntered":
      return "bg-amber-500/10 text-amber-300 ring-amber-400/20";
    case "TaskSucceeded":
    case "TaskStateExited":
    case "ChoiceStateExited":
    case "ExecutionSucceeded":
      return "bg-emerald-500/10 text-emerald-300 ring-emerald-400/20";
    case "ExecutionFailed":
    case "TaskFailed":
      return "bg-rose-500/10 text-rose-300 ring-rose-400/20";
    default:
      return "bg-slate-700/40 text-slate-300 ring-slate-600/40";
  }
}

// Blue label pill for the state name
function sfnLabelClass() {
  return "bg-sky-500/10 text-sky-300 ring-sky-400/20";
}

export default function LiveLogs({ base, mock, pollMs = 3000 }: Props) {
  const [group, setGroup] = useState<GroupKey>("target");
  const [minutes, setMinutes] = useState(15);
  const [pattern, setPattern] = useState<string>("");
  const [items, setItems] = useState<LogsItem[]>([]);
  const [nextToken, setNextToken] = useState<string | undefined>(undefined);
  const [live, setLive] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const listRef = useRef<HTMLDivElement>(null);
  const seen = useRef<Set<string>>(new Set());

  const clearAll = useCallback(() => {
    setItems([]);
    setNextToken(undefined);
    setLastUpdated(null);
    seen.current.clear();
  }, []);

  const scrollToBottom = useCallback(() => {
    if (!autoScroll) return;
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [autoScroll]);

  const merge = useCallback(
    (resp: LogsResponse) => {
      const fresh: LogsItem[] = [];
      for (const it of resp.items) {
        const key = `${it.ts}|${it.stream}|${it.message}`;
        if (!seen.current.has(key)) {
          seen.current.add(key);
          fresh.push(it);
        }
      }
      if (fresh.length) {
        setItems((prev) => {
          const merged = [...prev, ...fresh];
          const last = merged[merged.length - 1];
          if (last?.ts) setLastUpdated(last.ts);
          return merged;
        });
        setTimeout(scrollToBottom, 0);
      }
      setNextToken(resp.next);
    },
    [scrollToBottom]
  );

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
        setLastUpdated((prev) => prev ?? new Date().toISOString());
      } catch (e: any) {
        setError(e?.message ?? "Failed to load logs");
      } finally {
        setLoading(false);
      }
    },
    [base, mock, group, minutes, pattern, nextToken, merge]
  );

  useEffect(() => {
    clearAll();
    load({ reset: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [group, minutes, pattern]);

  useEffect(() => {
    if (!live) return;
    const id = setInterval(() => load(), pollMs);
    return () => clearInterval(id);
  }, [live, load, pollMs]);

  const onScroll = useCallback(() => {
    const el = listRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setAutoScroll(nearBottom);
  }, []);

  // colorize plain messages (non-SFN)
  const tint = (m: string) => {
    if (m.includes("ERROR") || m.includes("TaskFailed")) return "text-rose-300";
    if (m.startsWith("START")) return "text-emerald-300";
    if (m.startsWith("END")) return "text-sky-300";
    if (m.startsWith("REPORT")) return "text-indigo-300";
    if (m.includes("Execution") || m.includes("TaskState")) return "text-violet-300";
    return "text-slate-200";
  };

  const headerRight = useMemo(
    () => (
      <div className="flex items-center gap-3">
        <div className="text-[11px] text-slate-500">
          {lastUpdated ? <>Updated {new Date(lastUpdated).toLocaleTimeString()}</> : "—"}
        </div>
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
    [live, loading, load, lastUpdated]
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
      <div className="mb-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
        <select
          value={group}
          onChange={(e) => setGroup(e.target.value as GroupKey)}
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

        <div className="flex items-center gap-2">
          <input
            value={pattern}
            onChange={(e) => setPattern(e.target.value)}
            placeholder="CloudWatch filter pattern (ex: ERROR or { $.WarmStart = 1 })"
            className="flex-1 rounded-lg border border-slate-700 bg-slate-800/70 px-2 py-1.5 text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-600"
          />
        </div>
      </div>

      {/* Quick filter chips */}
      <div className="mb-3 flex flex-wrap gap-2">
        {PRESETS.map((p) => (
          <button
            key={p.label}
            onClick={() => setPattern(p.value)}
            className={clsx(
              "rounded-full px-2.5 py-1 text-xs ring-1 transition",
              pattern === p.value
                ? "bg-indigo-600 text-white ring-indigo-500"
                : "bg-slate-800 text-slate-300 ring-slate-700 hover:bg-slate-700"
            )}
            title={`Filter: ${p.value || "none"}`}
          >
            {p.label}
          </button>
        ))}
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

        {items.map((it, idx) => {
          const isSFN = group === "sfn";
          const sfnObj = isSFN ? parseJSONSafe(it.message) : null;
          const sfnType: string | undefined = sfnObj?.type;
          const execTail = isSFN ? sfnExecTail(sfnObj) : null;
          const label = isSFN ? sfnStateLabel(sfnObj) : null;

          return (
            <div key={`${it.ts}-${idx}`} className="whitespace-pre-wrap font-mono text-xs leading-5">
              <span className="text-slate-500">{new Date(it.ts).toLocaleTimeString()} </span>

              {/* Bracket tag */}
              <span className="text-slate-400">
                {isSFN ? `[SFN${execTail ? `:${execTail}` : ""}]` : `[${it.stream.split("/").at(-1)}]`}
              </span>{" "}

              {/* Label-first for SFN */}
              {isSFN && label && (
                <span className={`ml-1 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] ring-1 ${sfnLabelClass()}`}>
                  {label}
                </span>
              )}{" "}

              {/* Status/type badge */}
              {isSFN && sfnType && (
                <span
                  className={`ml-1 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] ring-1 ${sfnTypeClass(
                    sfnType
                  )}`}
                >
                  {sfnType}
                </span>
              )}{" "}

              {/* Message */}
              <span className={tint(it.message)}>{it.message.trimEnd()}</span>
            </div>
          );
        })}

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
            onClick={() => load()}
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
