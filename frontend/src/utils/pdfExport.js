import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { jsPDF } from 'jspdf'
import DailyLogGraph from '../components/logs/DailyLogGraph.jsx'
import { GRID } from './logGeometry.js'
import { formatDay, formatDuration } from './time.js'

const SCALE = 2.5

// jsPDF's built-in Helvetica only covers WinAnsi; map common characters outside it.
const toWinAnsi = (text) => String(text).replace(/[\u2192\u21D2\u279C]/g, '\u00BB').replace(/[^\x20-\x7E\u00A0-\u00FF\u2013\u2014\u2018\u2019\u201C\u201D\u2022\u2026]/g, '?')

/** Shorten text with an ellipsis so it fits on one line of the given width. */
function fitLine(doc, text, width) {
  const value = toWinAnsi(text)
  if (doc.getTextWidth(value) <= width) return value
  let end = value.length
  while (end > 0 && doc.getTextWidth(`${value.slice(0, end).trimEnd()}…`) > width) end -= 1
  return `${value.slice(0, end).trimEnd()}…`
}

/** Rasterise the same SVG component used on screen (no separate PDF drawing code). */
async function graphToPng(log) {
  const markup = renderToStaticMarkup(createElement(DailyLogGraph, { log, interactive: false }))
    .replace('width="100%"', `width="${GRID.width}" height="${GRID.height}"`)
  const url = URL.createObjectURL(new Blob([markup], { type: 'image/svg+xml;charset=utf-8' }))
  try {
    const image = await new Promise((resolve, reject) => {
      const img = new Image()
      img.onload = () => resolve(img)
      img.onerror = reject
      img.src = url
    })
    const canvas = document.createElement('canvas')
    canvas.width = GRID.width * SCALE
    canvas.height = GRID.height * SCALE
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height)
    return canvas.toDataURL('image/jpeg', 0.9)
  } finally {
    URL.revokeObjectURL(url)
  }
}

export async function exportLogsPdf(plan) {
  const doc = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'letter' })
  const pageWidth = doc.internal.pageSize.getWidth()
  const margin = 36
  const contentWidth = pageWidth - margin * 2
  const summary = plan.trip_summary
  const logs = plan.daily_logs

  for (const [index, log] of logs.entries()) {
    if (index > 0) doc.addPage()
    const date = `${log.date}T00:00`
    let y = margin + 4

    doc.setFont('helvetica', 'bold').setFontSize(16).setTextColor(15, 27, 45)
    doc.text("Driver's Daily Log (24 hours)", margin, y)
    doc.setFont('helvetica', 'normal').setFontSize(10).setTextColor(90, 100, 120)
    doc.text(`Day ${log.day_number} of ${logs.length}  ·  ${formatDay(date, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}`, pageWidth - margin, y, { align: 'right' })

    y += 22
    const fields = [
      ['Driver', summary.driver_name || '—'],
      ['Carrier', summary.carrier_name || '—'],
      ['Truck #', summary.truck_number || '—'],
      ['Miles today', `${log.miles.toLocaleString()} mi`],
      ['From', log.start_location],
      ['To', log.end_location],
      ['Trip route', `${summary.current_location} » ${summary.pickup_location} » ${summary.dropoff_location}`],
      ['Trip miles to date', `${log.cumulative_miles.toLocaleString()} mi`],
    ]
    const colWidth = contentWidth / 4
    fields.forEach(([label, value], i) => {
      const x = margin + (i % 4) * colWidth
      const rowY = y + Math.floor(i / 4) * 30
      doc.setFont('helvetica', 'bold').setFontSize(7).setTextColor(107, 122, 144).text(label.toUpperCase(), x, rowY)
      doc.setFont('helvetica', 'normal').setFontSize(9.5).setTextColor(15, 27, 45)
      doc.text(fitLine(doc, value, colWidth - 10), x, rowY + 12)
    })

    y += 66
    const graphHeight = (contentWidth * GRID.height) / GRID.width
    doc.addImage(await graphToPng(log), 'JPEG', margin, y, contentWidth, graphHeight, undefined, 'FAST')
    doc.setDrawColor(227, 232, 240).rect(margin, y, contentWidth, graphHeight)
    y += graphHeight + 20

    doc.setFont('helvetica', 'bold').setFontSize(9).setTextColor(15, 27, 45).text('REMARKS', margin, y)
    doc.text('TOTALS & 70-HOUR RECAP', margin + contentWidth * 0.68, y)
    doc.setFont('helvetica', 'normal').setFontSize(8.5).setTextColor(59, 74, 99)
    const remarkLines = log.remarks.map((r) => `${r.time}  ${r.activity} — ${r.location}`)
    const half = Math.ceil(remarkLines.length / 2)
    remarkLines.forEach((line, i) => {
      const x = margin + (i < half ? 0 : contentWidth * 0.34)
      const lineY = y + 14 + (i % half) * 12
      doc.text(fitLine(doc, line, contentWidth * 0.33), x, lineY)
    })
    const recap = [
      ['Driving', formatDuration(log.totals.driving)],
      ['On duty (incl. driving)', formatDuration(log.total_on_duty_hours)],
      ['Off duty', formatDuration(log.totals.off_duty)],
      ['Sleeper berth', formatDuration(log.totals.sleeper_berth)],
      ['Cycle used (8 days)', `${log.cycle.used_hours.toFixed(1)} h`],
      ['Cycle remaining', `${log.cycle.remaining_hours.toFixed(1)} h`],
      ['Available tomorrow', `${log.cycle.available_tomorrow_hours.toFixed(1)} h`],
    ]
    recap.forEach(([label, value], i) => {
      const lineY = y + 14 + i * 12
      doc.text(label, margin + contentWidth * 0.68, lineY)
      doc.text(value, pageWidth - margin, lineY, { align: 'right' })
    })

    doc.setFontSize(7).setTextColor(140, 150, 165)
    doc.text('Generated by RouteLog HOS trip planner — assessment/demo tool, not legal advice. Times are home-terminal time.', margin, doc.internal.pageSize.getHeight() - 20)
  }

  const name = `eld-logs-${summary.current_location}-to-${summary.dropoff_location}`.toLowerCase().replace(/[^a-z0-9]+/g, '-')
  doc.save(`${name}.pdf`)
}
