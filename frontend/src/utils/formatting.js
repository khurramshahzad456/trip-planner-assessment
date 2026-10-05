const numberFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const decimalFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 })

export function formatMiles(miles, { decimals = false } = {}) {
  if (miles == null) return '—'
  return `${(decimals ? decimalFormat : numberFormat).format(miles)} mi`
}

export function formatHours(hours) {
  if (hours == null) return '—'
  return `${decimalFormat.format(hours)} h`
}

export function pluralize(count, singular, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`
}
