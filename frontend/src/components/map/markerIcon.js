import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import L from 'leaflet'
import { styleFor } from '../../utils/eventStyles.js'

const cache = new Map()

/** Leaflet divIcon with the stop type's colour and Lucide icon. */
export function markerIcon(type, { selected = false } = {}) {
  const key = `${type}:${selected}`
  if (cache.has(key)) return cache.get(key)
  const style = styleFor(type)
  const endpoint = ['CURRENT', 'PICKUP', 'DROPOFF'].includes(type)
  const size = endpoint ? 36 : 30
  const svg = renderToStaticMarkup(createElement(style.icon, { size: endpoint ? 18 : 15, strokeWidth: 2.4, 'aria-hidden': true }))
  const icon = L.divIcon({
    className: '',
    html: `<div class="stop-marker${endpoint ? ' is-endpoint' : ''}${selected ? ' is-selected' : ''}" style="--marker-color:${style.color}">${svg}</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
  })
  cache.set(key, icon)
  return icon
}
