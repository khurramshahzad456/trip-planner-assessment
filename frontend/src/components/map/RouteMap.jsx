import { useEffect, useMemo, useRef } from 'react'
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import { Maximize } from 'lucide-react'
import MapLegend from './MapLegend.jsx'
import StopCard from './StopCard.jsx'
import { markerIcon } from './markerIcon.js'

const LEG_COLORS = ['#0ea5e9', '#1d4ed8']

function MapController({ bounds, fitSignal, focus }) {
  const map = useMap()

  useEffect(() => {
    map.fitBounds(bounds, { padding: [36, 36] })
  }, [map, bounds, fitSignal])

  useEffect(() => {
    if (!focus) return
    if (focus.bounds) map.flyToBounds(focus.bounds, { padding: [60, 60], duration: 0.6, maxZoom: 9 })
    else map.flyTo(focus.center, Math.max(map.getZoom(), 9), { duration: 0.6 })
  }, [map, focus])

  // Leaflet needs a nudge when its container changes size (responsive layouts).
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize())
    observer.observe(map.getContainer())
    return () => observer.disconnect()
  }, [map])

  return null
}

export default function RouteMap({ plan, selectedEventId, onSelectEvent, fitSignal, onFitRoute }) {
  const markerRefs = useRef({})
  const bounds = useMemo(() => L.latLngBounds(plan.route.bounds), [plan])
  const selectedStop = plan.stops.find((s) => s.event_id && s.event_id === selectedEventId)
  const selectedEvent = plan.events.find((e) => e.id === selectedEventId)

  const focus = useMemo(() => {
    if (!selectedEvent) return null
    if (selectedEvent.duty_status === 'DRIVING') {
      const { start_location: a, end_location: b } = selectedEvent
      return { bounds: L.latLngBounds([a.lat, a.lng], [b.lat, b.lng]) }
    }
    return { center: [selectedEvent.location.lat, selectedEvent.location.lng] }
  }, [selectedEvent])

  useEffect(() => {
    if (selectedStop) markerRefs.current[selectedStop.id]?.openPopup()
  }, [selectedStop])

  return (
    <section className="card no-print flex h-full flex-col overflow-hidden" aria-labelledby="map-title">
      <div className="flex items-center justify-between gap-3 px-5 pt-4 pb-3">
        <div>
          <p className="eyebrow">Interactive map</p>
          <h2 id="map-title" className="section-title">Route &amp; planned stops</h2>
        </div>
        <button type="button" className="btn-secondary px-3 py-2 text-xs" onClick={onFitRoute}>
          <Maximize className="size-3.5" aria-hidden /> Zoom to route
        </button>
      </div>
      <div className="relative isolate h-[380px] flex-none sm:h-[460px] lg:h-auto lg:min-h-[520px] lg:flex-1">
        <MapContainer bounds={bounds} scrollWheelZoom={false} className="absolute inset-0 h-full w-full" attributionControl>
          <TileLayer
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            maxZoom={19}
          />
          {plan.route.legs.map((leg, index) => (
            <Polyline key={`casing-${index}`} positions={leg.geometry} pathOptions={{ color: '#ffffff', weight: 8, opacity: 0.9 }} />
          ))}
          {plan.route.legs.map((leg, index) => (
            <Polyline key={`leg-${index}`} positions={leg.geometry} pathOptions={{ color: LEG_COLORS[index], weight: 4.5, opacity: 0.95 }} />
          ))}
          {plan.stops.map((stop) => (
            <Marker
              key={stop.id}
              position={[stop.lat, stop.lng]}
              icon={markerIcon(stop.type, { selected: stop.event_id != null && stop.event_id === selectedEventId })}
              zIndexOffset={['PICKUP', 'DROPOFF', 'CURRENT'].includes(stop.type) ? 1000 : 0}
              ref={(ref) => { markerRefs.current[stop.id] = ref }}
              eventHandlers={{ click: () => stop.event_id && onSelectEvent(stop.event_id, 'map') }}
            >
              <Popup>
                <StopCard stop={stop} />
              </Popup>
            </Marker>
          ))}
          <MapController bounds={bounds} fitSignal={fitSignal} focus={focus} />
        </MapContainer>
      </div>
      <div className="border-t border-line px-5 py-3">
        <MapLegend stops={plan.stops} />
      </div>
    </section>
  )
}
