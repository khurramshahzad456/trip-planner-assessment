import { MAP_LEGEND, styleFor } from '../../utils/eventStyles.js'

export default function MapLegend({ stops }) {
  const present = new Set(stops.map((s) => s.type))
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-ink-soft">
      {MAP_LEGEND.filter((type) => type !== 'RESTART' || present.has(type)).map((type) => {
        const style = styleFor(type)
        return (
          <span key={type} className="inline-flex items-center gap-1.5">
            <span className="size-3 rounded-full ring-2 ring-white" style={{ background: style.color, boxShadow: '0 0 0 1px rgb(0 0 0 / 0.1)' }} />
            {style.label}
          </span>
        )
      })}
      <span className="inline-flex items-center gap-1.5">
        <span className="h-1 w-5 rounded-full bg-sky-500" /> To pickup
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-1 w-5 rounded-full bg-brand-600" /> To dropoff
      </span>
    </div>
  )
}
