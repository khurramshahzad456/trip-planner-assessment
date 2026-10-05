import { Fuel, Route, ScrollText, ShieldCheck } from 'lucide-react'

const FEATURES = [
  { icon: Route, title: 'Real truck route', text: 'Geocoded with OpenStreetMap and routed with OSRM.' },
  { icon: ShieldCheck, title: 'HOS-compliant schedule', text: '11 / 14-hour limits, 30-minute breaks, 10-hour resets and the 70/8 cycle.' },
  { icon: Fuel, title: 'Fuel & rest stops', text: 'Placed along the actual route, with fuel at least every 1,000 miles.' },
  { icon: ScrollText, title: 'Daily ELD logs', text: 'One 24-hour log sheet per day, drawn from the same timeline.' },
]

export default function EmptyState({ onDemo, disabled }) {
  return (
    <div className="card flex h-full flex-col p-6 sm:p-8">
      <p className="eyebrow">Trip summary</p>
      <h2 className="mt-1 text-xl font-semibold tracking-tight">Plan a trip to see the route, stops and log sheets</h2>
      <p className="mt-2 max-w-xl text-sm text-ink-soft">
        Enter where the driver is now, the pickup and the dropoff, plus hours already used in the current cycle.
        The planner builds a minute-by-minute duty schedule and fills out every daily log.
      </p>
      <ul className="mt-6 grid gap-3 sm:grid-cols-2">
        {FEATURES.map(({ icon: Icon, title, text }) => (
          <li key={title} className="flex gap-3 rounded-xl border border-line bg-canvas/60 p-4">
            <Icon className="mt-0.5 size-5 shrink-0 text-brand-600" aria-hidden />
            <div>
              <p className="text-sm font-semibold">{title}</p>
              <p className="mt-0.5 text-[13px] text-ink-soft">{text}</p>
            </div>
          </li>
        ))}
      </ul>
      <div className="mt-auto pt-6">
        <button type="button" onClick={onDemo} className="btn-secondary" disabled={disabled}>
          Try the demo: Los Angeles → Phoenix → Dallas
        </button>
      </div>
    </div>
  )
}
