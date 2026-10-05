import { forwardRef } from 'react'
import { Fuel } from 'lucide-react'
import { eventTitle, styleFor, DUTY_STATUS_LABEL } from '../../utils/eventStyles.js'
import { formatClock, formatDuration } from '../../utils/time.js'
import { formatMiles } from '../../utils/formatting.js'

const TimelineItem = forwardRef(function TimelineItem({ event, selected, onSelect, isLast }, ref) {
  const style = styleFor(event.type)
  const Icon = style.icon
  const driving = event.duty_status === 'DRIVING'
  const location = driving ? `${event.start_location.label} → ${event.end_location.label}` : event.location.label

  return (
    <li ref={ref} className="relative pl-12">
      {!isLast && <span className="absolute top-9 bottom-[-12px] left-[17px] w-0.5 bg-line" aria-hidden />}
      <span
        className="absolute top-1 left-0 grid size-9 place-items-center rounded-full border-2 border-white text-white shadow-sm"
        style={{ background: driving ? '#e8eefc' : style.color, color: driving ? style.color : '#fff' }}
        aria-hidden
      >
        <Icon className="size-4" />
      </span>
      <button
        type="button"
        onClick={() => onSelect(event.id, 'timeline')}
        className={`w-full rounded-xl border px-3.5 py-2.5 text-left transition ${selected ? 'border-brand-500 bg-brand-50/60 ring-2 ring-brand-100' : 'border-transparent hover:border-line hover:bg-canvas'}`}
        aria-pressed={selected}
      >
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
          <p className="text-sm font-semibold text-ink">
            {eventTitle(event)} <span className="font-medium text-ink-soft">— {formatDuration(event.duration_hours)}</span>
          </p>
          <p className="font-mono text-xs text-ink-soft tabular-nums">
            {formatClock(event.start)} – {formatClock(event.end)}
          </p>
        </div>
        <p className="mt-0.5 text-[13px] break-words text-ink-soft">{location}</p>
        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted">
          <span>{DUTY_STATUS_LABEL[event.duty_status]}</span>
          {driving ? (
            <span>{formatMiles(event.distance_miles, { decimals: true })} · avg {event.average_speed_mph} mph</span>
          ) : (
            <span>Mile {formatMiles(event.start_mile).replace(' mi', '')}</span>
          )}
        </div>
        {!driving && event.reason && <p className="mt-1 text-xs leading-snug text-muted">{event.reason}</p>}
        {event.fuel_station && (
          <p className="mt-1.5 inline-flex items-center gap-1 text-xs text-emerald-700">
            <Fuel className="size-3" aria-hidden /> {event.fuel_station.name} · {event.fuel_station.distance_miles} mi from route point
          </p>
        )}
      </button>
    </li>
  )
})

export default TimelineItem
