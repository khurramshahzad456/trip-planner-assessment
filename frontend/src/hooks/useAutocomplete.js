import { useEffect, useState } from 'react'
import { api } from '../services/api.js'
import { useDebouncedValue } from './useDebouncedValue.js'

/** Debounced address suggestions; silently returns [] if the service is unavailable. */
export function useAutocomplete(query, enabled) {
  const debounced = useDebouncedValue(query.trim(), 300)
  const [state, setState] = useState({ results: [], loading: false, query: '' })

  useEffect(() => {
    if (!enabled || debounced.length < 3) {
      setState({ results: [], loading: false, query: debounced })
      return undefined
    }
    const controller = new AbortController()
    setState((s) => ({ ...s, loading: true }))
    api
      .autocomplete(debounced, { signal: controller.signal })
      .then((data) => setState({ results: data.results ?? [], loading: false, query: debounced }))
      .catch(() => {
        if (!controller.signal.aborted) setState({ results: [], loading: false, query: debounced })
      })
    return () => controller.abort()
  }, [debounced, enabled])

  return state
}
