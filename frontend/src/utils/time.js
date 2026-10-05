// All trip times are the driver's home-terminal wall-clock time, sent by the API
// as naive ISO strings ("2026-10-02T08:00"). They are parsed as UTC and always
// formatted in UTC, so the browser's own time zone (and its DST gaps) never shifts them.

export function parseLocal(iso) {
  if (!iso) return null
  const [datePart, timePart = '00:00'] = iso.split('T')
  const [y, m, d] = datePart.split('-').map(Number)
  const [hh, mm] = timePart.split(':').map(Number)
  return new Date(Date.UTC(y, m - 1, d, hh, mm))
}

export function formatClock(iso) {
  const date = parseLocal(iso)
  if (!date) return '—'
  return `${String(date.getUTCHours()).padStart(2, '0')}:${String(date.getUTCMinutes()).padStart(2, '0')}`
}

export function formatDay(iso, options = { weekday: 'short', month: 'short', day: 'numeric' }) {
  const date = parseLocal(iso)
  return date ? date.toLocaleDateString('en-US', { ...options, timeZone: 'UTC' }) : '—'
}

export function formatDateTime(iso) {
  return iso ? `${formatDay(iso)} · ${formatClock(iso)}` : '—'
}

/** 4.5 -> "4h 30m", 0.5 -> "30m", 10 -> "10h" */
export function formatDuration(hours) {
  if (hours == null || Number.isNaN(hours)) return '—'
  const totalMinutes = Math.round(hours * 60)
  const h = Math.floor(totalMinutes / 60)
  const m = totalMinutes % 60
  if (h === 0) return `${m}m`
  return m === 0 ? `${h}h` : `${h}h ${m}m`
}

/** 4.5 -> "04:30" (log-sheet style totals) */
export function formatHoursClock(hours) {
  const totalMinutes = Math.round((hours ?? 0) * 60)
  return `${String(Math.floor(totalMinutes / 60)).padStart(2, '0')}:${String(totalMinutes % 60).padStart(2, '0')}`
}

/** Value for <input type="datetime-local"> at today 08:00 local time. */
export function defaultStartTime(now = new Date()) {
  const date = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 8, 0)
  return toDateTimeInput(date)
}

export function toDateTimeInput(date) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** 1-based trip day for an event, relative to the first log date. */
export function tripDayNumber(iso, firstDateIso) {
  const a = parseLocal(firstDateIso)
  const b = parseLocal(iso)
  if (!a || !b) return 1
  const startA = Date.UTC(a.getUTCFullYear(), a.getUTCMonth(), a.getUTCDate())
  const startB = Date.UTC(b.getUTCFullYear(), b.getUTCMonth(), b.getUTCDate())
  return Math.round((startB - startA) / 86_400_000) + 1
}
