import { CircleCheck, LoaderCircle } from 'lucide-react'
import { PLANNING_STEPS } from '../../hooks/useTripPlanner.js'

export default function LoadingState({ step, slow }) {
  return (
    <div className="card overflow-hidden" role="status" aria-live="polite">
      <div className="h-1 w-full overflow-hidden bg-brand-50">
        <div className="animate-progress h-full w-2/5 rounded-full bg-brand-500" />
      </div>
      <div className="p-6 sm:p-8">
        <p className="eyebrow">Planning your trip</p>
        <h2 className="mt-1 text-lg font-semibold">Crunching the route and Hours-of-Service rules</h2>
        <ol className="mt-6 space-y-4">
          {PLANNING_STEPS.map((item, index) => {
            const done = index < step
            const active = index === step
            return (
              <li key={item.key} className="flex items-center gap-3">
                {done ? (
                  <CircleCheck className="size-5 text-emerald-600" aria-hidden />
                ) : active ? (
                  <LoaderCircle className="size-5 animate-spin text-brand-600" aria-hidden />
                ) : (
                  <span className="size-5 rounded-full border-2 border-line" aria-hidden />
                )}
                <span className={`text-sm ${done ? 'text-ink-soft' : active ? 'font-semibold text-ink' : 'text-muted'}`}>{item.label}</span>
              </li>
            )
          })}
        </ol>
        {slow && (
          <p className="mt-6 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Still working… the free-tier server may be waking up, and long routes take longer to process. This can take up to a minute.
          </p>
        )}
      </div>
    </div>
  )
}
