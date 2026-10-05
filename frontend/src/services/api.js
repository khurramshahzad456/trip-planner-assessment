// Thin HTTP client for the Django API. In development VITE_API_URL is empty and
// Vite proxies /api to Django; in production it points at the deployed backend.
const API_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
const PLAN_TIMEOUT_MS = 120_000

if (import.meta.env.PROD && !API_URL) {
  console.warn('VITE_API_URL is not set; API requests will go to this site instead of the Django backend.')
}

export class ApiError extends Error {
  constructor(message, { status = 0, code = 'error', fields = {} } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.fields = fields
  }
}

async function request(path, { method = 'GET', body, signal, timeout = 30_000 } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(new DOMException('timeout', 'TimeoutError')), timeout)
  signal?.addEventListener('abort', () => controller.abort(signal.reason), { once: true })

  let response
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    if (controller.signal.reason?.name === 'TimeoutError') {
      throw new ApiError('The planning service took too long to respond. Please try again.', { code: 'timeout' })
    }
    throw new ApiError('Unable to reach the planning service. Check your connection and try again.', { code: 'network' })
  } finally {
    clearTimeout(timer)
  }

  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const error = data?.error
    throw new ApiError(error?.message ?? 'Something went wrong while planning the trip. Please try again.', {
      status: response.status,
      code: error?.code,
      fields: error?.fields ?? {},
    })
  }
  if (data == null) {
    // e.g. the SPA's index.html came back because VITE_API_URL is not configured.
    throw new ApiError('Something went wrong while planning the trip. Please try again.', { status: response.status, code: 'invalid_response' })
  }
  return data
}

export const api = {
  planTrip: (payload, { signal } = {}) =>
    request('/api/trips/plan/', { method: 'POST', body: payload, signal, timeout: PLAN_TIMEOUT_MS }),
  getTrip: (id, { signal } = {}) => request(`/api/trips/${id}/`, { signal }),
  autocomplete: (query, { signal } = {}) =>
    request(`/api/geocode/autocomplete/?q=${encodeURIComponent(query)}`, { signal, timeout: 10_000 }),
  assumptions: ({ signal } = {}) => request('/api/hos/assumptions/', { signal }),
}
