export default function StatCard({ icon: Icon, label, value, hint, accent = '#1d4ed8' }) {
  return (
    <div className="min-w-0 rounded-xl border border-line bg-white p-3.5">
      <div className="flex items-center gap-2 text-xs font-medium text-muted">
        {Icon && <Icon className="size-3.5 shrink-0" style={{ color: accent }} aria-hidden />}
        <span className="truncate">{label}</span>
      </div>
      <p className="mt-1.5 truncate text-lg font-semibold tracking-tight text-ink tabular-nums">{value}</p>
      {hint && <p className="mt-0.5 truncate text-xs text-muted">{hint}</p>}
    </div>
  )
}
