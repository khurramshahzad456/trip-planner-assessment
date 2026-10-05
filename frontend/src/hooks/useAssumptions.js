import { useEffect, useState } from 'react'
import { api } from '../services/api.js'

// Shown before the API answers (or if it is unreachable); the API's list is authoritative.
const FALLBACK = [
  'Property-carrying driver on the 70-hour / 8-day cycle.',
  'No adverse driving conditions.',
  '11 hours driving within a 14-hour window after 10 hours off duty.',
  '30-minute break before 8 cumulative hours of driving.',
  'Fuel at least every 1,000 miles; 1 hour each for pickup and dropoff.',
]

export function useAssumptions(planAssumptions) {
  const [statements, setStatements] = useState(planAssumptions?.statements ?? FALLBACK)

  useEffect(() => {
    if (planAssumptions?.statements) {
      setStatements(planAssumptions.statements)
      return undefined
    }
    const controller = new AbortController()
    api
      .assumptions({ signal: controller.signal })
      .then((data) => data?.statements && setStatements(data.statements))
      .catch(() => {})
    return () => controller.abort()
  }, [planAssumptions])

  return statements
}
