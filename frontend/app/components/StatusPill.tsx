export default function StatusPill({ ok }: { ok: boolean }) {
  return (
    <span
      className={
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ring-1 " +
        (ok
          ? "bg-emerald-500/10 text-emerald-300 ring-emerald-500/20"
          : "bg-slate-700/40 text-slate-300 ring-slate-600")
      }
    >
      <span
        className={
          "h-1.5 w-1.5 rounded-full " + (ok ? "bg-emerald-400" : "bg-slate-400")
        }
      />
      {ok ? "Triggered" : "Idle"}
    </span>
  );
}
