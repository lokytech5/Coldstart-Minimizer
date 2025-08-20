export default function Spinner({
  size = 20,
  className = "",
}: { size?: number; className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block animate-spin rounded-full border-2 border-slate-300 border-t-transparent ${className}`}
      style={{ width: size, height: size }}
    />
  );
}
