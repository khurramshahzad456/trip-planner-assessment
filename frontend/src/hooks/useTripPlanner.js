import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../services/api.js'

export const PLANNING_STEPS = [
  { key: 'geocode', label: 'Geocoding locations…' },
  { key: 'route', label: 'Calculating route…' },
  { key: 'schedule', label: 'Building HOS schedule…' },
  { key: 'logs', label: 'Generating ELD logs…' },
]

// The API does all four steps in a single request; the indicator advances on a
// timer so the user sees progress, and completes when the response arrives.
const STEP_INTERVAL_MS = [1800, 3500, 2500]

export function useTripPlanner() {
  const [state, setState] = useState({ status: 'idle', plan: null, error: null, step: 0, slow: false })
  const controllerRef = useRef(null)
  const timersRef = useRef([])

  const clearTimers = () => {
    timersRef.current.forEach(clearTimeout)
    timersRef.current = []
  }

  const startProgress = () => {
    clearTimers()
    let elapsed = 0
    STEP_INTERVAL_MS.forEach((interval, index) => {
      elapsed += interval
      timersRef.current.push(setTimeout(() => setState((s) => (s.status === 'loading' ? { ...s, step: index + 1 } : s)), elapsed))
    })
    // Free hosting tiers sleep when idle; tell the user if the first request is slow.
    timersRef.current.push(setTimeout(() => setState((s) => (s.status === 'loading' ? { ...s, slow: true } : s)), 15000))
  }

  const run = useCallback(async (requestFn) => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    setState((s) => ({ ...s, status: 'loading', error: null, step: 0, slow: false }))
    startProgress()
    try {
      const plan = await requestFn(controller.signal)
      if (controller.signal.aborted) return null
      setState({ status: 'success', plan, error: null, step: PLANNING_STEPS.length, slow: false })
      return plan
    } catch (error) {
      if (controller.signal.aborted) return null
      setState((s) => ({ ...s, status: 'error', error, slow: false }))
      return null
    } finally {
      clearTimers()
    }
  }, [])

  const planTrip = useCallback((payload) => run((signal) => api.planTrip(payload, { signal })), [run])
  const loadTrip = useCallback((id) => run((signal) => api.getTrip(id, { signal })), [run])

  const reset = useCallback(() => {
    controllerRef.current?.abort()
    clearTimers()
    setState({ status: 'idle', plan: null, error: null, step: 0, slow: false })
  }, [])

  useEffect(() => () => {
    controllerRef.current?.abort()
    clearTimers()
  }, [])

  return { ...state, planTrip, loadTrip, reset }
}
