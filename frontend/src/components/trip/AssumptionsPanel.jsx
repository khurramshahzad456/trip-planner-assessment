import { useState } from 'react'
import { ChevronDown, Info } from 'lucide-react'

export default function AssumptionsPanel({ statements }) {
  const [open, setOpen] = useState(false)
  const visible = open ? statements : statements.slice(0, 4)
  return (
    <section className="mt-6 rounded-xl bg-brand-50/70 p-4" aria-labelledby="assumptions-title">
      <h3 id="assumptions-title" className="flex items-center gap-2 text-[13px] font-semibold text-brand-700">
        <Info className="size-4" aria-hidden /> Planning assumptions
      </h3>
      <ul className="mt-2 space-y-1.5 text-[13px] leading-snug text-ink-soft">
        {visible.map((statement) => (
          <li key={statement} className="flex gap-2">
            <span className="mt-[7px] size-1 shrink-0 rounded-full bg-brand-500" aria-hidden />
            {statement}
          </li>
        ))}
      </ul>
      {statements.length > 4 && (
        <button type="button" onClick={() => setOpen((v) => !v)} className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700">
          {open ? 'Show less' : `Show all ${statements.length}`}
          <ChevronDown className={`size-3.5 transition ${open ? 'rotate-180' : ''}`} aria-hidden />
        </button>
      )}
      <p className="mt-3 text-[11px] text-muted">Demo planning tool based on the stated assumptions — not legal advice.</p>
    </section>
  )
}
