import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import { CircleCheck, CircleX, Info, X } from 'lucide-react'

const ToastContext = createContext(null)

const TONES = {
  success: { icon: CircleCheck, className: 'text-emerald-600' },
  error: { icon: CircleX, className: 'text-red-600' },
  info: { icon: Info, className: 'text-brand-600' },
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const nextId = useRef(1)

  const dismiss = useCallback((id) => setToasts((list) => list.filter((t) => t.id !== id)), [])

  const notify = useCallback(
    (message, tone = 'info', duration = 4500) => {
      const id = nextId.current++
      setToasts((list) => [...list.slice(-3), { id, message, tone }])
      setTimeout(() => dismiss(id), duration)
    },
    [dismiss],
  )

  const value = useMemo(() => ({ notify }), [notify])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="no-print pointer-events-none fixed inset-x-0 bottom-0 z-[1000] flex flex-col items-center gap-2 px-4 pb-[calc(env(safe-area-inset-bottom,0px)+1rem)] sm:items-end sm:pr-6"
        aria-live="polite"
      >
        {toasts.map((toast) => {
          const { icon: Icon, className } = TONES[toast.tone] ?? TONES.info
          return (
            <div
              key={toast.id}
              role="status"
              className="pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border border-line bg-white px-4 py-3 text-sm shadow-lg"
            >
              <Icon className={`mt-0.5 size-4 shrink-0 ${className}`} aria-hidden />
              <p className="flex-1 text-ink">{toast.message}</p>
              <button type="button" onClick={() => dismiss(toast.id)} className="text-muted hover:text-ink" aria-label="Dismiss">
                <X className="size-4" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used inside <ToastProvider>')
  return context
}
