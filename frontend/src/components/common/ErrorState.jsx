import { RefreshCw, TriangleAlert } from 'lucide-react'

const TITLES = {
  routing_failed: 'We couldn’t calculate that route',
  geocoding_failed: 'We couldn’t find one of those locations',
  validation_error: 'Please check the trip details',
  network: 'Can’t reach the planning service',
  timeout: 'The request timed out',
  provider_unavailable: 'A map service is temporarily unavailable',
}

export default function ErrorState({ error, onRetry }) {
  const title = TITLES[error?.code] ?? 'Something went wrong'
  return (
    <div className="card border-red-200 p-6 sm:p-8" role="alert">
      <div className="flex items-start gap-4">
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-red-50 text-red-600">
          <TriangleAlert className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold text-ink">{title}</h2>
          <p className="mt-1 text-sm break-words text-ink-soft">
            {error?.message ?? 'Something went wrong while planning the trip. Please try again.'}
          </p>
          {onRetry && (
            <button type="button" className="btn-secondary mt-4" onClick={onRetry}>
              <RefreshCw className="size-4" aria-hidden /> Try again
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
