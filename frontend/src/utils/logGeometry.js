import { DUTY_STATUSES } from './eventStyles.js'

// Layout of the daily-log grid (SVG user units).
export const GRID = {
  labelWidth: 132,
  hourWidth: 32,
  totalsWidth: 76,
  headerHeight: 30,
  rowHeight: 38,
  footerHeight: 30,
}
GRID.gridWidth = GRID.hourWidth * 24
GRID.width = GRID.labelWidth + GRID.gridWidth + GRID.totalsWidth
GRID.height = GRID.headerHeight + GRID.rowHeight * DUTY_STATUSES.length + GRID.footerHeight

const ROW_INDEX = Object.fromEntries(DUTY_STATUSES.map((s, i) => [s.key, i]))

/** x = hour / 24 * gridWidth, offset by the label column. */
export function hourToX(hour) {
  const clamped = Math.min(24, Math.max(0, hour))
  return GRID.labelWidth + (clamped / 24) * GRID.gridWidth
}

export function rowTop(status) {
  return GRID.headerHeight + ROW_INDEX[status] * GRID.rowHeight
}

export function rowCenter(status) {
  return rowTop(status) + GRID.rowHeight / 2
}

/**
 * The continuous duty-status line: horizontal runs inside each status row,
 * joined by vertical strokes wherever the status changes.
 */
export function dutyLinePath(segments) {
  if (!segments.length) return ''
  const parts = []
  segments.forEach((segment, index) => {
    const x1 = hourToX(segment.start_hour)
    const x2 = hourToX(segment.end_hour)
    const y = rowCenter(segment.status)
    if (index === 0) parts.push(`M ${x1} ${y}`)
    else parts.push(`V ${y}`)
    parts.push(`H ${x2}`)
  })
  return parts.join(' ')
}

/** x positions where the duty status changes (used for remark ticks). */
export function statusChangeHours(segments) {
  const hours = []
  segments.forEach((segment, index) => {
    if (index > 0 && segment.status !== segments[index - 1].status) hours.push(segment.start_hour)
  })
  return hours
}

export function hourLabel(hour) {
  if (hour === 0 || hour === 24) return 'Mid'
  if (hour === 12) return 'Noon'
  return String(hour > 12 ? hour - 12 : hour)
}
