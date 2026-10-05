import { useEffect, useMemo, useRef } from 'react'
import { MapPin } from 'lucide-react'
import TimelineItem from './TimelineItem.jsx'
import { EVENT_STYLES } from '../../utils/eventStyles.js'
import { formatClock, formatDay, tripDayNumber } from '../../utils/time.js'

/** Groups events under the trip day on which they start. */
function groupByDay(events) {
  const firstDate = events[0]?.start
  const groups = []
  for (const event of events) {
    const day = tripDayNumber(event.start, firstDate)
    if (!groups.length || groups[groups.length - 1].day !== day) groups.push({ day, date: event.start, events: [] })
    groups[groups.length - 1].events.push(event)
  }
  return groups
}

export default function TripTimeline({ plan, selectedEventId, selectionSource, onSelectEvent }) {
  const itemRefs = useRef({})
  const scrollRef = useRef(null)
  const groups = useMemo(() => groupByDay(plan.events), [plan.events])
  const lastId = plan.events.at(-1)?.id

  // Keep the selected item visible when it was chosen on the map or log sheet.
  useEffect(() => {
    if (!selectedEventId || selectionSource === 'timeline') return
    const item = itemRefs.current[selectedEventId]
    const container = scrollRef.current
    if (!item || !container) return
    const offset = item.getBoundingClientRect().top - container.getBoundingClientRect().top
    container.scrollTo({ top: container.scrollTop + offset - 12, behavior: 'smooth' })
  }, [selectedEventId, selectionSource])

  return (
    <section className="card flex h-full max-h-[640px] flex-col overflow-hidden lg:max-h-none" aria-labelledby="timeline-title">
      <div className="border-b border-line px-5 pt-4 pb-3">
        <p className="eyebrow">Trip timeline</p>
        <h2 id="timeline-title" className="section-title">
          {plan.events.length} events · {plan.trip_summary.log_days} day{plan.trip_summary.log_days === 1 ? '' : 's'}
        </h2>
      </div>
      <div ref={scrollRef} className="relative min-h-0 flex-1 overflow-y-auto px-4 py-4 lg:h-0">
        <div className="relative mb-3 flex items-center gap-3 pl-0.5">
          <span className="grid size-8 place-items-center rounded-full text-white shadow-sm" style={{ background: EVENT_STYLES.CURRENT.color }}>
            <MapPin className="size-4" aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold">Current location</p>
            <p className="truncate text-xs text-muted">
              {plan.trip_summary.current_location} · departs {formatClock(plan.trip_summary.trip_start)}
            </p>
          </div>
        </div>
        {groups.map((group) => (
          <div key={group.day} className="mt-4 first:mt-2">
            <p className="sticky top-[-16px] z-10 -mx-4 mb-3 bg-white/95 px-4 py-1.5 text-xs font-semibold text-ink-soft backdrop-blur">
              Day {group.day} · {formatDay(group.date)}
            </p>
            <ol className="space-y-3">
              {group.events.map((event) => (
                <TimelineItem
                  key={event.id}
                  ref={(node) => { itemRefs.current[event.id] = node }}
                  event={event}
                  selected={event.id === selectedEventId}
                  onSelect={onSelectEvent}
                  isLast={event.id === lastId}
                />
              ))}
            </ol>
          </div>
        ))}
      </div>
    </section>
  )
}
