import { DUTY_STATUSES } from '../../utils/eventStyles.js'

const COLORS = Object.fromEntries(DUTY_STATUSES.map((s) => [s.key, s.color]))

export default function LogRemarks({ remarks, onSelectEvent }) {
  return (
    <div>
      <h4 className="text-xs font-semibold tracking-wide text-ink-soft uppercase">Remarks · duty status changes</h4>
      <ol className="mt-2 gap-x-6 space-y-1.5 sm:columns-2">
        {remarks.map((remark, index) => (
          <li key={`${remark.time}-${index}`} className="flex min-w-0 break-inside-avoid items-start gap-2.5 text-[13px]">
            <span className="mt-0.5 font-mono text-xs font-medium text-ink tabular-nums">{remark.time}</span>
            <span className="mt-[5px] size-2 shrink-0 rounded-full" style={{ background: COLORS[remark.status] }} aria-hidden />
            <button
              type="button"
              disabled={!remark.event_id}
              onClick={() => onSelectEvent(remark.event_id, 'log')}
              className="min-w-0 text-left enabled:hover:text-brand-700 disabled:cursor-default"
            >
              <span className="font-medium">{remark.activity}</span>
              <span className="text-ink-soft"> — {remark.location}</span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  )
}
