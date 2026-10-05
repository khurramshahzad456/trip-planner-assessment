import { Fuel } from 'lucide-react'
import { styleFor } from '../../utils/eventStyles.js'
import { formatDateTime, formatDuration } from '../../utils/time.js'
import { formatMiles } from '../../utils/formatting.js'

export default function StopCard({ stop }) {
  const style = styleFor(stop.type)
  const Icon = style.icon
  return (
    <div className="w-60 max-w-full text-ink">
      <div className="flex items-center gap-2">
        <span className="grid size-7 shrink-0 place-items-center rounded-full text-white" style={{ background: style.color }}>
          <Icon className="size-3.5" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold tracking-wide uppercase" style={{ color: style.color }}>{style.label}</p>
          <p className="truncate text-sm font-semibold">{stop.label}</p>
        </div>
      </div>
      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
        {stop.arrival && (<><dt className="text-muted">Arrive</dt><dd className="font-medium">{formatDateTime(stop.arrival)}</dd></>)}
        <dt className="text-muted">{stop.type === 'CURRENT' ? 'Depart' : 'Leave'}</dt>
        <dd className="font-medium">{formatDateTime(stop.departure)}</dd>
        {stop.duration_hours > 0 && (<><dt className="text-muted">Duration</dt><dd className="font-medium">{formatDuration(stop.duration_hours)}</dd></>)}
        <dt className="text-muted">Route mile</dt>
        <dd className="font-medium">{formatMiles(stop.mile)}</dd>
      </dl>
      <p className="mt-2 text-xs leading-snug text-ink-soft">{stop.reason}</p>
      {stop.fuel_station && (
        <p className="mt-2 flex gap-1.5 rounded-lg bg-emerald-50 px-2 py-1.5 text-xs text-emerald-800">
          <Fuel className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>Nearest station: <strong>{stop.fuel_station.name}</strong> ({stop.fuel_station.distance_miles} mi from planned point)</span>
        </p>
      )}
    </div>
  )
}
