import { ChevronDown } from 'lucide-react'
import DailyLogGraph from './DailyLogGraph.jsx'
import LogRemarks from './LogRemarks.jsx'
import { DUTY_STATUSES } from '../../utils/eventStyles.js'
import { formatDay, formatDuration } from '../../utils/time.js'
import { formatMiles } from '../../utils/formatting.js'

function Field({ label, value }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-semibold tracking-wide text-muted uppercase">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium break-words text-ink">{value || '—'}</dd>
    </div>
  )
}

export default function DailyLog({ log, totalDays, summary, expanded, onToggle, selectedEventId, onSelectEvent }) {
  const date = `${log.date}T00:00`
  const { cycle } = log
  return (
    <article className="daily-log card overflow-hidden" aria-labelledby={`log-${log.date}`}>
      <button type="button" onClick={onToggle} className="no-print flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-5 py-4 text-left hover:bg-canvas/60" aria-expanded={expanded}>
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-50 text-sm font-bold text-brand-700">{log.day_number}</span>
        <span className="min-w-0 flex-1">
          <span id={`log-${log.date}`} className="block font-semibold">
            Day {log.day_number} of {totalDays} · {formatDay(date, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
          </span>
          <span className="block truncate text-xs text-muted">
            {log.start_location} → {log.end_location}
          </span>
        </span>
        <span className="hidden gap-4 text-xs text-ink-soft sm:flex">
          <span><strong className="text-ink">{formatMiles(log.miles)}</strong> driven</span>
          <span><strong className="text-ink">{formatDuration(log.totals.driving)}</strong> driving</span>
          <span><strong className="text-ink">{formatDuration(log.total_on_duty_hours)}</strong> on duty</span>
        </span>
        <ChevronDown className={`size-5 text-muted transition ${expanded ? 'rotate-180' : ''}`} aria-hidden />
      </button>

      <div className={`log-body border-t border-line px-5 py-5 ${expanded ? '' : 'hidden'}`}>
        {/* print-only title */}
        <h3 className="mb-3 hidden text-lg font-bold print:block">Driver&apos;s Daily Log — Day {log.day_number} of {totalDays}</h3>

        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
          <Field label="Date" value={formatDay(date, { month: '2-digit', day: '2-digit', year: 'numeric' })} />
          <Field label="Driver" value={summary.driver_name} />
          <Field label="Carrier" value={summary.carrier_name} />
          <Field label="Truck / trailer #" value={summary.truck_number} />
          <Field label="From" value={log.start_location} />
          <Field label="To" value={log.end_location} />
          <Field label="Miles driving today" value={formatMiles(log.miles, { decimals: true })} />
          <Field label="Trip miles to date" value={formatMiles(log.cumulative_miles, { decimals: true })} />
        </dl>

        <p className="no-print mt-5 text-xs text-muted sm:hidden">Swipe the graph sideways to see all 24 hours.</p>
        <div className="mt-2 overflow-x-auto rounded-xl border border-line sm:mt-5">
          <DailyLogGraph log={log} selectedEventId={selectedEventId} onSelectEvent={onSelectEvent} />
        </div>

        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-ink-soft">
          {DUTY_STATUSES.map((status) => (
            <span key={status.key} className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-4 rounded-sm" style={{ background: status.color, opacity: 0.35 }} />
              {status.label}: <strong className="text-ink">{formatDuration(log.totals[status.total])}</strong>
            </span>
          ))}
          <span className="inline-flex items-center gap-1.5">
            <span className="h-0.5 w-5 rounded bg-[#1e3a8a]" /> Duty status line
          </span>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_280px]">
          <LogRemarks remarks={log.remarks} onSelectEvent={onSelectEvent} />
          <div className="rounded-xl bg-canvas p-4">
            <h4 className="text-xs font-semibold tracking-wide text-ink-soft uppercase">Day totals &amp; 70-hr recap</h4>
            <dl className="mt-2 space-y-1.5 text-sm">
              {[
                ['Driving', formatDuration(log.totals.driving)],
                ['On duty (incl. driving)', formatDuration(log.total_on_duty_hours)],
                ['Off duty + sleeper', formatDuration(log.totals.off_duty + log.totals.sleeper_berth)],
                ['Cycle used (8 days)', `${cycle.used_hours.toFixed(1)} h`],
                ['Cycle remaining', `${cycle.remaining_hours.toFixed(1)} h`],
                ['Available tomorrow', `${cycle.available_tomorrow_hours.toFixed(1)} h`],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between gap-3">
                  <dt className="text-ink-soft">{label}</dt>
                  <dd className="font-semibold tabular-nums">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </div>
    </article>
  )
}
