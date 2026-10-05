import { BedDouble, CalendarDays, Coffee, Flag, Fuel, Hourglass, Link2, PackageOpen, Route, Timer, Truck } from 'lucide-react'
import StatCard from './StatCard.jsx'
import CycleStatus from './CycleStatus.jsx'
import { formatMiles } from '../../utils/formatting.js'
import { formatDateTime, formatDuration } from '../../utils/time.js'
import { EVENT_STYLES } from '../../utils/eventStyles.js'

export default function RouteSummary({ plan, onCopyLink }) {
  const { trip_summary: summary, route, hos_summary: hos } = plan

  const stats = [
    { icon: Route, label: 'Total distance', value: formatMiles(summary.total_distance_miles), hint: route.provider },
    { icon: Truck, label: 'Driving time', value: formatDuration(summary.driving_hours), hint: `Router estimate ${formatDuration(route.provider_duration_hours)}` },
    { icon: Hourglass, label: 'Total trip duration', value: formatDuration(summary.total_duration_hours), hint: 'Start to dropoff complete' },
    { icon: CalendarDays, label: 'Driving days', value: summary.driving_days, hint: `${summary.log_days} daily log${summary.log_days === 1 ? '' : 's'}` },
    { icon: Fuel, label: 'Fuel stops', value: summary.fuel_stops, accent: EVENT_STYLES.FUEL.color, hint: 'At most 1,000 mi apart' },
    { icon: BedDouble, label: 'Rest periods', value: summary.rest_periods, accent: EVENT_STYLES.REST.color, hint: '10-hr rests / restarts' },
    { icon: Coffee, label: '30-min breaks', value: summary.breaks, accent: EVENT_STYLES.BREAK.color, hint: 'Off-duty breaks' },
    { icon: Timer, label: 'Pickup / dropoff', value: `${formatDuration(summary.pickup_duration_hours)} / ${formatDuration(summary.dropoff_duration_hours)}`, accent: EVENT_STYLES.PICKUP.color, hint: 'On duty, not driving' },
  ]

  return (
    <div className="space-y-4">
      <section className="card p-5 sm:p-6" aria-labelledby="summary-title">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="eyebrow">Route summary</p>
            <h2 id="summary-title" className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-lg font-semibold tracking-tight">
              <span className="break-words">{summary.current_location}</span>
              <span className="text-muted" aria-hidden>→</span>
              <span className="break-words">{summary.pickup_location}</span>
              <span className="text-muted" aria-hidden>→</span>
              <span className="break-words">{summary.dropoff_location}</span>
            </h2>
            <p className="mt-1 text-sm text-ink-soft">
              Departs {formatDateTime(summary.trip_start)} · Arrives {formatDateTime(summary.trip_end)}
            </p>
          </div>
          {plan.id && (
            <button type="button" className="btn-ghost text-xs" onClick={onCopyLink} title="Copy a shareable link to this plan">
              <Link2 className="size-4" aria-hidden /> Copy link
            </button>
          )}
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {stats.map((stat) => (
            <StatCard key={stat.label} {...stat} />
          ))}
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          {route.legs.map((leg, index) => (
            <div key={leg.from + leg.to} className="flex min-w-0 items-center gap-3 rounded-xl bg-canvas px-3.5 py-2.5 text-sm">
              {index === 0 ? (
                <PackageOpen className="size-4 shrink-0" style={{ color: EVENT_STYLES.PICKUP.color }} aria-hidden />
              ) : (
                <Flag className="size-4 shrink-0" style={{ color: EVENT_STYLES.DROPOFF.color }} aria-hidden />
              )}
              <div className="min-w-0">
                <p className="truncate font-medium">
                  {index === 0 ? 'To pickup' : 'To dropoff'} · {formatMiles(leg.distance_miles)}
                </p>
                <p className="truncate text-xs text-muted">
                  {formatDuration(leg.planned_driving_hours)} driving · avg {leg.average_speed_mph} mph
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <CycleStatus hos={hos} />
    </div>
  )
}
