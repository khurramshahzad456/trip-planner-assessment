import { DUTY_STATUSES } from '../../utils/eventStyles.js'
import { GRID, dutyLinePath, hourLabel, hourToX, rowCenter, rowTop, statusChangeHours } from '../../utils/logGeometry.js'
import { formatHoursClock } from '../../utils/time.js'

const FONT = 'Inter, Helvetica, Arial, sans-serif'
const INK = '#0f1b2d'
const GRID_LINE = '#c7d0dd'
const LINE_COLOR = '#1e3a8a'
const HOURS = Array.from({ length: 25 }, (_, h) => h)

/**
 * A 24-hour driver's daily log grid drawn in SVG. Every visual element is
 * computed from `log.segments` (server-generated from the trip schedule).
 * Presentation attributes are inline so the SVG can be rasterised for PDF export.
 */
export default function DailyLogGraph({ log, selectedEventId, onSelectEvent, interactive = true }) {
  const gridLeft = GRID.labelWidth
  const gridRight = GRID.labelWidth + GRID.gridWidth
  const gridTop = GRID.headerHeight
  const gridBottom = GRID.headerHeight + GRID.rowHeight * DUTY_STATUSES.length

  return (
    <svg
      viewBox={`0 0 ${GRID.width} ${GRID.height}`}
      width="100%"
      role="img"
      aria-label={`Duty status graph for ${log.date}`}
      xmlns="http://www.w3.org/2000/svg"
      fontFamily={FONT}
      style={{ display: 'block', minWidth: 720 }}
    >
      <rect x="0" y="0" width={GRID.width} height={GRID.height} fill="#ffffff" />

      {/* hour labels (top and bottom) */}
      {HOURS.map((h) => (
        <g key={`label-${h}`} fontSize="10.5" fill="#3b4a63" textAnchor="middle" fontWeight={h % 12 === 0 ? 700 : 500}>
          <text x={hourToX(h)} y={gridTop - 10}>{hourLabel(h)}</text>
          <text x={hourToX(h)} y={gridBottom + 18}>{hourLabel(h)}</text>
        </g>
      ))}

      {/* rows: label, background, quarter-hour ticks, total */}
      {DUTY_STATUSES.map((status, index) => {
        const top = rowTop(status.key)
        return (
          <g key={status.key}>
            <rect x={gridLeft} y={top} width={GRID.gridWidth} height={GRID.rowHeight} fill={index % 2 ? '#f7f9fc' : '#ffffff'} />
            <text x={10} y={rowCenter(status.key) + 4} fontSize="11.5" fontWeight="600" fill={INK}>
              {status.number}. {status.label}
            </text>
            {HOURS.slice(0, 24).flatMap((h) =>
              [1, 2, 3].map((q) => {
                const x = hourToX(h + q / 4)
                const len = q === 2 ? GRID.rowHeight * 0.45 : GRID.rowHeight * 0.25
                return <line key={`${status.key}-${h}-${q}`} x1={x} x2={x} y1={top} y2={top + len} stroke={GRID_LINE} strokeWidth="0.8" />
              }),
            )}
            <text x={gridRight + GRID.totalsWidth / 2} y={rowCenter(status.key) + 4} fontSize="12.5" fontWeight="700" fill={INK} textAnchor="middle" fontFamily="'JetBrains Mono', Menlo, monospace">
              {formatHoursClock(log.totals[status.total])}
            </text>
          </g>
        )
      })}

      {/* hour gridlines and row separators */}
      {HOURS.map((h) => (
        <line key={`hour-${h}`} x1={hourToX(h)} x2={hourToX(h)} y1={gridTop} y2={gridBottom} stroke={h % 6 === 0 ? '#8a99ad' : GRID_LINE} strokeWidth={h % 6 === 0 ? 1.1 : 0.8} />
      ))}
      {DUTY_STATUSES.map((status) => (
        <line key={`sep-${status.key}`} x1={gridLeft} x2={gridRight} y1={rowTop(status.key)} y2={rowTop(status.key)} stroke="#8a99ad" strokeWidth="1" />
      ))}
      <rect x={gridLeft} y={gridTop} width={GRID.gridWidth} height={gridBottom - gridTop} fill="none" stroke={INK} strokeWidth="1.4" />
      <text x={gridRight + GRID.totalsWidth / 2} y={gridTop - 10} fontSize="10" fontWeight="700" fill="#3b4a63" textAnchor="middle">TOTAL</text>
      <text x={gridRight + GRID.totalsWidth / 2} y={gridBottom + 18} fontSize="12" fontWeight="700" fill={INK} textAnchor="middle" fontFamily="'JetBrains Mono', Menlo, monospace">
        {/* sum whole minutes per row (as displayed) so the total never drifts to 23:59 / 24:01 */}
        {formatHoursClock(Object.values(log.totals).reduce((sum, hours) => sum + Math.round(hours * 60), 0) / 60)}
      </text>

      {/* tinted bands under each duty segment */}
      {log.segments.map((segment, index) => {
        const status = DUTY_STATUSES.find((s) => s.key === segment.status)
        const x = hourToX(segment.start_hour)
        const selected = segment.event_id && segment.event_id === selectedEventId
        return (
          <rect
            key={`band-${index}`}
            x={x}
            y={rowTop(segment.status) + 7}
            width={Math.max(0, hourToX(segment.end_hour) - x)}
            height={GRID.rowHeight - 14}
            rx="3"
            fill={status.color}
            opacity={selected ? 0.38 : 0.14}
          />
        )
      })}

      {/* status-change ticks below the grid (remarks markers) */}
      {statusChangeHours(log.segments).map((h, index) => (
        <line key={`tick-${index}`} x1={hourToX(h)} x2={hourToX(h)} y1={gridBottom} y2={gridBottom + 6} stroke={LINE_COLOR} strokeWidth="1.6" />
      ))}

      {/* the duty-status line itself */}
      <path d={dutyLinePath(log.segments)} fill="none" stroke={LINE_COLOR} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />

      {/* invisible hit areas with tooltips */}
      {interactive &&
        log.segments.map((segment, index) => {
          const x = hourToX(segment.start_hour)
          return (
            <rect
              key={`hit-${index}`}
              x={x}
              y={rowTop(segment.status)}
              width={Math.max(2, hourToX(segment.end_hour) - x)}
              height={GRID.rowHeight}
              fill="transparent"
              style={{ cursor: segment.event_id ? 'pointer' : 'default' }}
              onClick={() => segment.event_id && onSelectEvent?.(segment.event_id, 'log')}
            >
              <title>{`${segment.label}: ${segment.start.slice(11)} – ${segment.end_hour === 24 ? '24:00' : segment.end.slice(11)} (${formatHoursClock(segment.end_hour - segment.start_hour)})`}</title>
            </rect>
          )
        })}
    </svg>
  )
}
