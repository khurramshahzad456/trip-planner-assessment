import { useCallback, useState } from 'react'
import { defaultStartTime } from '../utils/time.js'

const LOCATION_FIELDS = ['current_location', 'pickup_location', 'dropoff_location']

export const DEMO_TRIP = {
  current_location: 'Los Angeles, CA',
  pickup_location: 'Phoenix, AZ',
  dropoff_location: 'Dallas, TX',
  current_cycle_used: '20',
  driver_name: 'Alex Rivera',
  carrier_name: 'Demo Freight Lines',
  truck_number: 'TRK-1042',
}

function emptyForm() {
  return {
    current_location: '',
    pickup_location: '',
    dropoff_location: '',
    current_cycle_used: '',
    start_time: defaultStartTime(),
    driver_name: '',
    carrier_name: '',
    truck_number: '',
    coords: {},
  }
}

const REQUIRED_MESSAGES = {
  current_location: 'Please enter your current location.',
  pickup_location: 'Please enter a pickup location.',
  dropoff_location: 'Please enter a dropoff location.',
}

export function validateTripForm(values) {
  const errors = {}
  for (const field of LOCATION_FIELDS) {
    if (!values[field]?.trim()) errors[field] = REQUIRED_MESSAGES[field]
  }
  const cycle = values.current_cycle_used
  if (cycle === '' || cycle == null) {
    errors.current_cycle_used = 'Please enter current cycle used (hours).'
  } else if (Number.isNaN(Number(cycle)) || Number(cycle) < 0 || Number(cycle) > 70) {
    errors.current_cycle_used = 'Current cycle used must be between 0 and 70 hours.'
  }
  if (!errors.dropoff_location && !errors.pickup_location &&
      values.pickup_location.trim().toLowerCase() === values.dropoff_location.trim().toLowerCase()) {
    errors.dropoff_location = 'Pickup and dropoff must be different locations.'
  }
  if (!values.start_time) errors.start_time = 'Please choose when the trip starts.'
  return errors
}

export function toPlanPayload(values) {
  const payload = {
    current_location: values.current_location.trim(),
    pickup_location: values.pickup_location.trim(),
    dropoff_location: values.dropoff_location.trim(),
    current_cycle_used: Number(values.current_cycle_used),
    start_time: values.start_time,
    driver_name: values.driver_name.trim(),
    carrier_name: values.carrier_name.trim(),
    truck_number: values.truck_number.trim(),
  }
  for (const field of LOCATION_FIELDS) {
    if (values.coords[field]) payload[`${field}_coords`] = values.coords[field]
  }
  return payload
}

export function fromPlanInputs(inputs, locations) {
  return {
    ...emptyForm(),
    ...Object.fromEntries(Object.entries(inputs).map(([k, v]) => [k, v == null ? '' : String(v)])),
    coords: Object.fromEntries(
      LOCATION_FIELDS.filter((f) => locations?.[f]).map((f) => [
        f,
        { lat: locations[f].lat, lng: locations[f].lng, label: locations[f].label, display_name: locations[f].display_name },
      ]),
    ),
  }
}

export function useTripForm() {
  const [values, setValues] = useState(emptyForm)
  const [errors, setErrors] = useState({})

  const setField = useCallback((field, value) => {
    setValues((current) => {
      const next = { ...current, [field]: value }
      // Typing in a location after choosing a suggestion invalidates its coordinates.
      if (LOCATION_FIELDS.includes(field) && current.coords[field]) {
        next.coords = { ...current.coords }
        delete next.coords[field]
      }
      return next
    })
    setErrors((current) => (current[field] ? { ...current, [field]: undefined } : current))
  }, [])

  const selectSuggestion = useCallback((field, suggestion) => {
    setValues((current) => ({
      ...current,
      [field]: suggestion.label,
      coords: { ...current.coords, [field]: { lat: suggestion.lat, lng: suggestion.lng, label: suggestion.label, display_name: suggestion.display_name } },
    }))
    setErrors((current) => ({ ...current, [field]: undefined }))
  }, [])

  const validate = useCallback(() => {
    const found = validateTripForm(values)
    setErrors(found)
    return Object.keys(found).length === 0
  }, [values])

  const reset = useCallback(() => {
    setValues(emptyForm())
    setErrors({})
  }, [])

  const loadValues = useCallback((next) => {
    setValues(next)
    setErrors({})
  }, [])

  const demoValues = useCallback(() => ({ ...emptyForm(), ...DEMO_TRIP }), [])

  return { values, errors, setErrors, setField, selectSuggestion, validate, reset, loadValues, demoValues }
}
