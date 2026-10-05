import { Plus, Truck } from 'lucide-react'

export default function AppHeader({ onNewTrip, hasPlan }) {
  return (
    <header className="no-print sticky top-[env(safe-area-inset-top,0px)] z-[500] border-b border-line bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <a href="/" className="flex min-w-0 items-center gap-3" aria-label="RouteLog home">
          <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-brand-600 text-white shadow-sm">
            <Truck className="size-5" aria-hidden />
          </span>
          <span className="min-w-0">
            <span className="block text-[15px] leading-tight font-bold tracking-tight">RouteLog</span>
            <span className="block truncate text-xs text-muted">HOS trip planner &amp; ELD logs</span>
          </span>
        </a>
        <button type="button" onClick={onNewTrip} className="btn-primary" disabled={!hasPlan} title={hasPlan ? 'Start a new trip' : 'Plan a trip first'}>
          <Plus className="size-4" aria-hidden />
          <span>New trip</span>
        </button>
      </div>
    </header>
  )
}
