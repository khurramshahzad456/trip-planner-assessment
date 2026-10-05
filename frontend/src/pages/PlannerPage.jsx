import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import AppHeader from '../components/layout/AppHeader.jsx'
import TripForm from '../components/trip/TripForm.jsx'
import RouteSummary from '../components/summary/RouteSummary.jsx'
import RouteMap from '../components/map/RouteMap.jsx'
import TripTimeline from '../components/timeline/TripTimeline.jsx'
import DailyLogs from '../components/logs/DailyLogs.jsx'
import LoadingState from '../components/common/LoadingState.jsx'
import ErrorState from '../components/common/ErrorState.jsx'
import EmptyState from '../components/common/EmptyState.jsx'
import { fromPlanInputs, toPlanPayload, useTripForm, validateTripForm } from '../hooks/useTripForm.js'
import { useTripPlanner } from '../hooks/useTripPlanner.js'
import { useAssumptions } from '../hooks/useAssumptions.js'
import { useToast } from '../hooks/useToast.jsx'

export default function PlannerPage() {
  const { tripId } = useParams()
  const navigate = useNavigate()
  const form = useTripForm()
  const planner = useTripPlanner()
  const { notify } = useToast()
  const assumptions = useAssumptions(planner.plan?.assumptions)
  const [selection, setSelection] = useState({ id: null, source: null })
  const [fitSignal, setFitSignal] = useState(0)
  const resultsRef = useRef(null)
  const loadedTripRef = useRef(null)
  const lastActionRef = useRef('plan')

  const { plan, status, planTrip, loadTrip } = planner
  const { loadValues, setErrors } = form

  const handleResult = useCallback(
    (result) => {
      if (!result) return
      setSelection({ id: null, source: null })
      notify(`Trip planned — ${result.daily_logs.length} daily log${result.daily_logs.length === 1 ? '' : 's'} generated.`, 'success')
      if (result.id) {
        loadedTripRef.current = result.id
        navigate(`/trips/${result.id}`, { replace: true })
      }
      requestAnimationFrame(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    },
    [navigate, notify],
  )

  const submitValues = useCallback(
    async (values) => {
      const errors = validateTripForm(values)
      if (Object.keys(errors).length) {
        setErrors(errors)
        return
      }
      lastActionRef.current = 'plan'
      handleResult(await planTrip(toPlanPayload(values)))
    },
    [handleResult, planTrip, setErrors],
  )

  // Surface server-side field errors next to the matching inputs.
  useEffect(() => {
    if (status === 'error' && planner.error?.fields) setErrors((current) => ({ ...current, ...planner.error.fields }))
    if (status === 'error') notify(planner.error?.message ?? 'Something went wrong while planning the trip.', 'error')
  }, [status, planner.error, setErrors, notify])

  // Open a shared link: /trips/:id. Failures are toasted by the error effect above.
  const openSavedTrip = useCallback(
    (id, isCancelled = () => false) => {
      lastActionRef.current = 'load'
      return loadTrip(id).then((result) => {
        if (result && !isCancelled()) loadValues(fromPlanInputs(result.inputs, result.locations))
      })
    },
    [loadTrip, loadValues],
  )

  useEffect(() => {
    if (!tripId || loadedTripRef.current === tripId) return undefined
    let cancelled = false
    loadedTripRef.current = tripId
    openSavedTrip(tripId, () => cancelled)
    return () => {
      // If this load is aborted (e.g. StrictMode re-mount), allow the next run to retry it.
      cancelled = true
      if (loadedTripRef.current === tripId) loadedTripRef.current = null
    }
  }, [tripId, openSavedTrip])

  const onRetry = () => {
    if (lastActionRef.current === 'load' && tripId) openSavedTrip(tripId)
    else submitValues(form.values)
  }

  const onDemo = () => {
    const demo = form.demoValues()
    loadValues(demo)
    submitValues(demo)
  }

  const onNewTrip = () => {
    planner.reset()
    form.reset()
    loadedTripRef.current = null
    navigate('/', { replace: true })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const onCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href)
      notify('Shareable link copied to clipboard.', 'success')
    } catch {
      notify(window.location.href, 'info', 8000)
    }
  }

  const onSelectEvent = useCallback((id, source) => {
    setSelection((current) => (current.id === id && source === 'timeline' ? { id: null, source } : { id, source }))
  }, [])

  const loading = status === 'loading'
  // Hide the previous plan's map/timeline/logs while loading or after a failed recalculation.
  const showResults = Boolean(plan) && status === 'success'

  return (
    <div className="min-h-screen">
      <AppHeader onNewTrip={onNewTrip} hasPlan={Boolean(plan) || status === 'error'} />
      <main className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="lg:col-span-5 xl:col-span-4">
            <TripForm
              form={form}
              onSubmit={() => submitValues(form.values)}
              onDemo={onDemo}
              onReset={form.reset}
              loading={loading}
              hasPlan={Boolean(plan)}
              assumptions={assumptions}
            />
          </div>
          <div className="no-print min-w-0 lg:col-span-7 xl:col-span-8">
            {loading ? (
              <LoadingState step={planner.step} slow={planner.slow} />
            ) : status === 'error' ? (
              <ErrorState error={planner.error} onRetry={onRetry} />
            ) : plan ? (
              <RouteSummary plan={plan} onCopyLink={onCopyLink} />
            ) : (
              <EmptyState onDemo={onDemo} disabled={loading} />
            )}
          </div>
        </div>

        {showResults && (
          <div ref={resultsRef} className="scroll-mt-24 space-y-6">
            <div className="no-print grid gap-6 lg:grid-cols-3">
              <div className="min-w-0 lg:col-span-2">
                <RouteMap
                  plan={plan}
                  selectedEventId={selection.id}
                  onSelectEvent={onSelectEvent}
                  fitSignal={fitSignal}
                  onFitRoute={() => {
                    setSelection({ id: null, source: null })
                    setFitSignal((n) => n + 1)
                  }}
                />
              </div>
              <div className="min-w-0">
                <TripTimeline plan={plan} selectedEventId={selection.id} selectionSource={selection.source} onSelectEvent={onSelectEvent} />
              </div>
            </div>
            <DailyLogs plan={plan} selectedEventId={selection.id} onSelectEvent={onSelectEvent} />
          </div>
        )}
      </main>
      <footer className="no-print mx-auto max-w-7xl px-4 pb-10 text-xs text-muted sm:px-6 lg:px-8">
        Map data © OpenStreetMap contributors · Routing by OSRM · Assessment/demo tool based on stated HOS assumptions — not legal advice.
      </footer>
    </div>
  )
}
