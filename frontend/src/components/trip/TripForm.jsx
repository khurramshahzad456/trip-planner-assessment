import { useState } from 'react'
import { ChevronDown, Clock, Eraser, Flag, Gauge, MapPin, PackageOpen, RefreshCw, Route, Sparkles } from 'lucide-react'
import LocationInput from './LocationInput.jsx'
import AssumptionsPanel from './AssumptionsPanel.jsx'
import { EVENT_STYLES } from '../../utils/eventStyles.js'

const LOCATIONS = [
  { name: 'current_location', label: 'Current location', icon: MapPin, color: EVENT_STYLES.CURRENT.color, placeholder: 'e.g. Los Angeles, CA' },
  { name: 'pickup_location', label: 'Pickup location', icon: PackageOpen, color: EVENT_STYLES.PICKUP.color, placeholder: 'City, address or ZIP' },
  { name: 'dropoff_location', label: 'Dropoff location', icon: Flag, color: EVENT_STYLES.DROPOFF.color, placeholder: 'City, address or ZIP' },
]

export default function TripForm({ form, onSubmit, onDemo, onReset, loading, hasPlan, assumptions }) {
  const { values, errors, setField, selectSuggestion } = form
  const [showDetails, setShowDetails] = useState(false)
  const cycle = Number(values.current_cycle_used)
  const cycleValid = values.current_cycle_used !== '' && !Number.isNaN(cycle) && cycle >= 0 && cycle <= 70

  const submit = (event) => {
    event.preventDefault()
    onSubmit()
  }

  return (
    <form onSubmit={submit} noValidate className="card no-print p-5 sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="eyebrow">Trip details</p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight">Plan a trip</h2>
        </div>
        <button type="button" onClick={onDemo} className="btn-ghost -mr-2 text-brand-600 hover:text-brand-700" disabled={loading}>
          <Sparkles className="size-4" aria-hidden /> Load demo trip
        </button>
      </div>

      <fieldset className="mt-5 space-y-4" disabled={loading}>
        {LOCATIONS.map((loc) => (
          <LocationInput
            key={loc.name}
            name={loc.name}
            label={loc.label}
            icon={loc.icon}
            iconColor={loc.color}
            placeholder={loc.placeholder}
            value={values[loc.name]}
            resolved={Boolean(values.coords[loc.name])}
            error={errors[loc.name]}
            onChange={setField}
            onSelect={selectSuggestion}
          />
        ))}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1 2xl:grid-cols-2">
          <div>
            <label htmlFor="current_cycle_used" className="field-label">
              <Gauge className="size-3.5 text-brand-600" aria-hidden /> Current cycle used
            </label>
            <div className="relative">
              <input
                id="current_cycle_used"
                type="number"
                inputMode="decimal"
                min="0"
                max="70"
                step="0.25"
                className="field-input pr-16"
                placeholder="0 – 70"
                value={values.current_cycle_used}
                aria-invalid={Boolean(errors.current_cycle_used)}
                aria-describedby={errors.current_cycle_used ? 'cycle-error' : 'cycle-help'}
                onChange={(e) => setField('current_cycle_used', e.target.value)}
              />
              <span className="pointer-events-none absolute inset-y-0 right-3.5 flex items-center text-xs font-medium text-muted">hours</span>
            </div>
            {errors.current_cycle_used ? (
              <p id="cycle-error" className="mt-1.5 text-xs font-medium text-red-600">{errors.current_cycle_used}</p>
            ) : (
              <p id="cycle-help" className="mt-1.5 text-xs text-muted">
                {cycleValid ? `${(70 - cycle).toFixed(cycle % 1 ? 2 : 0)} of 70 hours remaining` : 'On-duty hours used in the last 8 days'}
              </p>
            )}
          </div>
          <div>
            <label htmlFor="start_time" className="field-label">
              <Clock className="size-3.5 text-brand-600" aria-hidden /> Trip start
            </label>
            <input
              id="start_time"
              type="datetime-local"
              className="field-input"
              value={values.start_time}
              aria-invalid={Boolean(errors.start_time)}
              onChange={(e) => setField('start_time', e.target.value)}
            />
            {errors.start_time ? (
              <p className="mt-1.5 text-xs font-medium text-red-600">{errors.start_time}</p>
            ) : (
              <p className="mt-1.5 text-xs text-muted">Home-terminal time</p>
            )}
          </div>
        </div>

        <div className="rounded-xl border border-line">
          <button
            type="button"
            onClick={() => setShowDetails((v) => !v)}
            className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-ink-soft hover:text-ink"
            aria-expanded={showDetails}
          >
            Log sheet details <span className="ml-1 font-normal text-muted">(optional)</span>
            <ChevronDown className={`ml-auto size-4 transition ${showDetails ? 'rotate-180' : ''}`} aria-hidden />
          </button>
          {showDetails && (
            <div className="grid gap-3 border-t border-line p-4 sm:grid-cols-3">
              {[
                ['driver_name', 'Driver name', 'Jane Doe'],
                ['carrier_name', 'Carrier', 'Acme Freight'],
                ['truck_number', 'Truck #', 'TRK-101'],
              ].map(([field, label, placeholder]) => (
                <div key={field}>
                  <label htmlFor={field} className="field-label">{label}</label>
                  <input id={field} className="field-input" value={values[field]} placeholder={placeholder} maxLength={100} onChange={(e) => setField(field, e.target.value)} />
                </div>
              ))}
            </div>
          )}
        </div>
      </fieldset>

      <div className="mt-6 flex flex-col gap-2 sm:flex-row">
        <button type="submit" className="btn-primary flex-1" disabled={loading}>
          {hasPlan ? <RefreshCw className="size-4" aria-hidden /> : <Route className="size-4" aria-hidden />}
          {loading ? 'Planning…' : hasPlan ? 'Recalculate trip' : 'Plan trip'}
        </button>
        <button type="button" className="btn-secondary" onClick={onReset} disabled={loading}>
          <Eraser className="size-4" aria-hidden /> Reset
        </button>
      </div>

      <AssumptionsPanel statements={assumptions} />
    </form>
  )
}
