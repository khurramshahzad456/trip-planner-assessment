import { describe, expect, it } from 'vitest'
import { GRID, dutyLinePath, hourToX, rowCenter, statusChangeHours } from './logGeometry.js'
import { formatClock, formatDay, formatDuration, formatHoursClock, tripDayNumber } from './time.js'
import { validateTripForm } from '../hooks/useTripForm.js'

describe('log geometry', () => {
  it('maps hours linearly onto the grid width', () => {
    expect(hourToX(0)).toBe(GRID.labelWidth)
    expect(hourToX(12)).toBe(GRID.labelWidth + GRID.gridWidth / 2)
    expect(hourToX(24)).toBe(GRID.labelWidth + GRID.gridWidth)
    expect(hourToX(30)).toBe(hourToX(24))
  })

  it('draws horizontal runs joined by vertical status changes', () => {
    const segments = [
      { status: 'OFF_DUTY', start_hour: 0, end_hour: 8 },
      { status: 'DRIVING', start_hour: 8, end_hour: 12.5 },
      { status: 'ON_DUTY', start_hour: 12.5, end_hour: 24 },
    ]
    expect(dutyLinePath(segments)).toBe(
      `M ${hourToX(0)} ${rowCenter('OFF_DUTY')} H ${hourToX(8)} V ${rowCenter('DRIVING')} H ${hourToX(12.5)} V ${rowCenter('ON_DUTY')} H ${hourToX(24)}`,
    )
    expect(statusChangeHours(segments)).toEqual([8, 12.5])
  })
})

describe('time formatting', () => {
  it('formats durations and log-style totals', () => {
    expect(formatDuration(4.5)).toBe('4h 30m')
    expect(formatDuration(0.5)).toBe('30m')
    expect(formatDuration(10)).toBe('10h')
    expect(formatHoursClock(11)).toBe('11:00')
    expect(formatHoursClock(0.25)).toBe('00:15')
  })

  it('computes trip day numbers across midnight', () => {
    expect(tripDayNumber('2026-10-03T01:00', '2026-10-02T08:00')).toBe(2)
  })
})

describe('trip form validation', () => {
  const valid = { current_location: 'A', pickup_location: 'B', dropoff_location: 'C', current_cycle_used: '45', start_time: '2026-10-02T08:00' }

  it('accepts a complete form', () => {
    expect(validateTripForm(valid)).toEqual({})
  })

  it('requires locations and a 0-70 cycle value', () => {
    expect(validateTripForm({ ...valid, pickup_location: ' ' }).pickup_location).toBe('Please enter a pickup location.')
    expect(validateTripForm({ ...valid, current_cycle_used: '71' }).current_cycle_used).toBe('Current cycle used must be between 0 and 70 hours.')
    expect(validateTripForm({ ...valid, current_cycle_used: '70' })).toEqual({})
  })
})

describe('time formatting', () => {
  it('shows home-terminal times exactly as sent, even inside a DST gap', () => {
    expect(formatClock('2026-03-08T02:30')).toBe('02:30')
    expect(formatClock('2026-11-01T01:30')).toBe('01:30')
    expect(formatDay('2026-03-08T00:00')).toBe('Sun, Mar 8')
    expect(tripDayNumber('2026-03-09T00:30', '2026-03-08T23:00')).toBe(2)
  })
})
