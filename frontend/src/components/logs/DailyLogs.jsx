import { useEffect, useState } from 'react'
import { FileDown, LoaderCircle, Printer } from 'lucide-react'
import DailyLog from './DailyLog.jsx'
import { useToast } from '../../hooks/useToast.jsx'

export default function DailyLogs({ plan, selectedEventId, onSelectEvent }) {
  const logs = plan.daily_logs
  const [expanded, setExpanded] = useState(() => new Set(logs.slice(0, 1).map((l) => l.date)))
  const [exporting, setExporting] = useState(false)
  const { notify } = useToast()

  useEffect(() => {
    setExpanded(new Set(logs.slice(0, 1).map((l) => l.date)))
  }, [logs])

  // Selecting an event elsewhere opens the log sheet(s) it appears on.
  useEffect(() => {
    if (!selectedEventId) return
    const dates = logs.filter((log) => log.event_ids.includes(selectedEventId)).map((l) => l.date)
    if (dates.length) setExpanded((current) => new Set([...current, ...dates]))
  }, [selectedEventId, logs])

  const allOpen = expanded.size === logs.length
  const toggle = (date) =>
    setExpanded((current) => {
      const next = new Set(current)
      next.has(date) ? next.delete(date) : next.add(date)
      return next
    })

  const downloadPdf = async () => {
    setExporting(true)
    try {
      const { exportLogsPdf } = await import('../../utils/pdfExport.js')
      await exportLogsPdf(plan)
      notify('ELD log PDF downloaded.', 'success')
    } catch (error) {
      console.error(error)
      notify('Could not create the PDF. Try Print → Save as PDF instead.', 'error')
    } finally {
      setExporting(false)
    }
  }

  return (
    <section id="daily-logs" className="print-area" aria-labelledby="logs-title">
      <div className="no-print mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Driver&apos;s daily logs</p>
          <h2 id="logs-title" className="text-lg font-semibold tracking-tight">
            {logs.length} ELD log sheet{logs.length === 1 ? '' : 's'}
          </h2>
          <p className="text-sm text-ink-soft">Generated from the same schedule as the map and timeline; events are split at midnight.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-ghost" onClick={() => setExpanded(allOpen ? new Set() : new Set(logs.map((l) => l.date)))}>
            {allOpen ? 'Collapse all' : 'Expand all'}
          </button>
          <button type="button" className="btn-secondary" onClick={() => window.print()}>
            <Printer className="size-4" aria-hidden /> Print
          </button>
          <button type="button" className="btn-primary" onClick={downloadPdf} disabled={exporting}>
            {exporting ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : <FileDown className="size-4" aria-hidden />}
            Download PDF
          </button>
        </div>
      </div>
      <div className="space-y-4">
        {logs.map((log) => (
          <DailyLog
            key={log.date}
            log={log}
            totalDays={logs.length}
            summary={plan.trip_summary}
            expanded={expanded.has(log.date)}
            onToggle={() => toggle(log.date)}
            selectedEventId={selectedEventId}
            onSelectEvent={onSelectEvent}
          />
        ))}
      </div>
    </section>
  )
}
