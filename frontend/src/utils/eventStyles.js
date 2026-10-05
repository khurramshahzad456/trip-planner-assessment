import { BedDouble, Coffee, Flag, Fuel, MapPin, PackageOpen, RotateCcw, Truck } from 'lucide-react'

// One place that decides how each stop / event type looks across the map,
// timeline, legend and log sheets.
export const EVENT_STYLES = {
  CURRENT: { label: 'Current location', short: 'Start', color: '#2563eb', icon: MapPin },
  PICKUP: { label: 'Pickup', short: 'Pickup', color: '#ea580c', icon: PackageOpen },
  DROPOFF: { label: 'Dropoff', short: 'Dropoff', color: '#dc2626', icon: Flag },
  FUEL: { label: 'Fuel stop', short: 'Fuel', color: '#16a34a', icon: Fuel },
  REST: { label: '10-hr rest', short: 'Rest', color: '#7c3aed', icon: BedDouble },
  RESTART: { label: '34-hr restart', short: 'Restart', color: '#5b21b6', icon: RotateCcw },
  BREAK: { label: '30-min break', short: 'Break', color: '#d97706', icon: Coffee },
  DRIVING: { label: 'Driving', short: 'Drive', color: '#1e40af', icon: Truck },
}

export const MAP_LEGEND = ['CURRENT', 'PICKUP', 'DROPOFF', 'FUEL', 'REST', 'BREAK', 'RESTART']

export function styleFor(type) {
  return EVENT_STYLES[type] ?? EVENT_STYLES.DRIVING
}

export function eventTitle(event) {
  if (event.type === 'REST' && event.trigger === 'CYCLE') {
    return event.recovery === 'recap' ? 'Off duty · cycle recap' : 'Rest · cycle recap'
  }
  return styleFor(event.type).label
}

// The four duty-status rows of a standard driver's daily log, top to bottom.
export const DUTY_STATUSES = [
  { key: 'OFF_DUTY', total: 'off_duty', label: 'Off Duty', number: 1, color: '#64748b' },
  { key: 'SLEEPER_BERTH', total: 'sleeper_berth', label: 'Sleeper Berth', number: 2, color: '#7c3aed' },
  { key: 'DRIVING', total: 'driving', label: 'Driving', number: 3, color: '#1d4ed8' },
  { key: 'ON_DUTY', total: 'on_duty', label: 'On Duty (not driving)', number: 4, color: '#ea580c' },
]

export const DUTY_STATUS_LABEL = Object.fromEntries(DUTY_STATUSES.map((s) => [s.key, s.label]))
