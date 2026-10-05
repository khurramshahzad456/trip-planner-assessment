import { useState } from 'react'
import { ChevronDown, CircleCheck, CircleX, ShieldCheck, TriangleAlert } from 'lucide-react'
import { formatDuration } from '../../utils/time.js'

const STATUS_STYLES = {
  FITS: { tone: 'bg-emerald-50 text-emerald-800 border-emerald-200', icon: CircleCheck, title: 'Fits within the current cycle' },
  RECOVERY_REQUIRED: { tone: 'bg-amber-50 text-amber-900 border-amber-200', icon: TriangleAlert, title: 'Needs more cycle hours than remain' },
  NO_HOURS_AVAILABLE: { tone: 'bg-red-50 text-red-800 border-red-200', icon: TriangleAlert, title: 'No cycle hours available' },
}

function hoursLabel(hours) {
  return `${Number(hours).toFixed(hours % 1 ? 1 : 0)} h`
}

export default function CycleStatus({ hos }) {
  const [showChecks, setShowChecks] = useState(false)
  const status = STATUS_STYLES[hos.status] ?? STATUS_STYLES.FITS
  const StatusIcon = status.icon
  const limit = hos.cycle_limit_hours
  const usedPct = Math.min(100, (hos.cycle_used_hours / limit) * 100)
  const neededPct = Math.min(100 - usedPct, (hos.required_on_duty_hours / limit) * 100)
  const overflow = hos.required_on_duty_hours > hos.cycle_remaining_hours

  return (
    <section className="card p-5 sm:p-6" aria-labelledby="cycle-title">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="eyebrow">70-hour / 8-day cycle</p>
          <h2 id="cycle-title" className="mt-1 text-base font-semibold">Hours-of-Service status</h2>
        </div>
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${status.tone}`}>
          <StatusIcon className="size-3.5" aria-hidden /> {status.title}
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          ['Cycle used', hoursLabel(hos.cycle_used_hours)],
          ['Cycle remaining', hoursLabel(hos.cycle_remaining_hours)],
          ['Trip on-duty hours', formatDuration(hos.required_on_duty_hours)],
          ['Used at arrival', hoursLabel(hos.cycle_used_at_arrival_hours)],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl bg-canvas px-3.5 py-2.5">
            <dt className="text-xs text-muted">{label}</dt>
            <dd className="mt-0.5 font-semibold tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-4" aria-hidden>
        <div className="flex h-2.5 overflow-hidden rounded-full bg-slate-100">
          <div className="bg-slate-500" style={{ width: `${usedPct}%` }} />
          <div className={overflow ? 'bg-amber-500' : 'bg-brand-500'} style={{ width: `${neededPct}%` }} />
        </div>
        <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">
          <span className="inline-flex items-center gap-1.5"><span className="size-2 rounded-full bg-slate-500" /> Already used</span>
          <span className="inline-flex items-center gap-1.5"><span className={`size-2 rounded-full ${overflow ? 'bg-amber-500' : 'bg-brand-500'}`} /> Needed for this trip</span>
          <span className="ml-auto">{limit} h limit</span>
        </div>
      </div>

      <p className="mt-4 text-sm text-ink-soft">{hos.message}</p>
      {hos.warnings.length > 0 && (
        <ul className="mt-2 space-y-1">
          {hos.warnings.map((warning) => (
            <li key={warning} className="flex gap-2 text-sm text-amber-800">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden /> {warning}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 rounded-xl border border-line">
        <button type="button" onClick={() => setShowChecks((v) => !v)} className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm font-medium" aria-expanded={showChecks}>
          <ShieldCheck className={`size-4 ${hos.all_checks_passed ? 'text-emerald-600' : 'text-red-600'}`} aria-hidden />
          {hos.all_checks_passed ? 'All compliance checks passed' : 'Some compliance checks failed'}
          <span className="text-xs font-normal text-muted">({hos.compliance_checks.length} rules audited)</span>
          <ChevronDown className={`ml-auto size-4 text-muted transition ${showChecks ? 'rotate-180' : ''}`} aria-hidden />
        </button>
        {showChecks && (
          <ul className="divide-y divide-line border-t border-line">
            {hos.compliance_checks.map((check) => (
              <li key={check.rule} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                {check.passed ? <CircleCheck className="size-4 shrink-0 text-emerald-600" aria-label="passed" /> : <CircleX className="size-4 shrink-0 text-red-600" aria-label="failed" />}
                <span className="flex-1">{check.label}</span>
                {check.observed != null && (
                  <span className="text-xs text-muted tabular-nums">
                    max {check.unit === 'hours' ? formatDuration(check.observed) : `${check.observed} mi`} / {check.unit === 'hours' ? formatDuration(check.limit) : `${check.limit.toLocaleString()} mi`}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
