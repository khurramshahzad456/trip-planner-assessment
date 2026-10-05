import { useId, useState } from 'react'
import { LoaderCircle, MapPin } from 'lucide-react'
import { useAutocomplete } from '../../hooks/useAutocomplete.js'

export default function LocationInput({ name, label, icon: Icon = MapPin, iconColor, value, placeholder, error, resolved, onChange, onSelect, disabled }) {
  const id = useId()
  const listId = `${id}-list`
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(-1)
  const { results, loading, query } = useAutocomplete(value, open && !resolved)
  // Only offer suggestions for exactly what is typed, never for an earlier query.
  const showList = open && !resolved && results.length > 0 && query === value.trim()
  const optionId = (index) => `${listId}-${index}`

  const choose = (suggestion) => {
    onSelect(name, suggestion)
    setOpen(false)
    setHighlight(-1)
  }

  const onKeyDown = (event) => {
    if (!showList) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setHighlight((h) => (h + 1) % results.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setHighlight((h) => (h <= 0 ? results.length - 1 : h - 1))
    } else if (event.key === 'Enter' && highlight >= 0) {
      event.preventDefault()
      choose(results[highlight])
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="relative">
      <label htmlFor={id} className="field-label">
        <Icon className="size-3.5" style={{ color: iconColor }} aria-hidden />
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          name={name}
          type="text"
          autoComplete="off"
          className="field-input pr-9"
          placeholder={placeholder}
          value={value}
          disabled={disabled}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && highlight >= 0 ? optionId(highlight) : undefined}
          onChange={(e) => {
            onChange(name, e.target.value)
            setOpen(true)
            setHighlight(-1)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() =>
            setTimeout(() => {
              setOpen(false)
              setHighlight(-1)
            }, 150)
          }
          onKeyDown={onKeyDown}
        />
        <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center">
          {loading ? (
            <LoaderCircle className="size-4 animate-spin text-muted" aria-hidden />
          ) : resolved ? (
            <span className="size-2 rounded-full bg-emerald-500" title="Location confirmed" />
          ) : null}
        </span>
      </div>
      {showList && (
        <ul id={listId} role="listbox" className="absolute z-[600] mt-1 max-h-72 w-full overflow-auto rounded-xl border border-line bg-white py-1 shadow-lg">
          {results.map((suggestion, index) => (
            <li
              key={`${suggestion.display_name}-${index}`}
              id={optionId(index)}
              role="option"
              aria-selected={index === highlight}
              className={`cursor-pointer px-3.5 py-2 ${index === highlight ? 'bg-brand-50' : 'hover:bg-slate-50'}`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => choose(suggestion)}
              onMouseEnter={() => setHighlight(index)}
            >
              <p className="truncate text-sm font-medium text-ink">{suggestion.label}</p>
              <p className="truncate text-xs text-muted">{suggestion.display_name}</p>
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p id={`${id}-error`} className="mt-1.5 text-xs font-medium text-red-600">
          {error}
        </p>
      )}
    </div>
  )
}
