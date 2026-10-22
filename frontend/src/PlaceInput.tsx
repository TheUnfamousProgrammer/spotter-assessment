import { useEffect, useId, useState, type KeyboardEvent } from 'react'

const PHOTON_URL = 'https://photon.komoot.io/api/'

interface PhotonFeature {
  properties: { name?: string; street?: string; city?: string; state?: string; countrycode?: string }
}

function label({ properties: p }: PhotonFeature) {
  return [...new Set([p.name ?? p.street, p.city, p.state, p.countrycode].filter(Boolean))].join(', ')
}

/** Text input with place suggestions as you type (ARIA combobox). */
export function PlaceInput({ label: name, placeholder, value, onChange }: {
  label: string
  placeholder: string
  value: string
  onChange: (value: string) => void
}) {
  const id = useId()
  const [open, setOpen] = useState(false)
  const [options, setOptions] = useState<string[]>([])
  const [active, setActive] = useState(-1)

  useEffect(() => {
    if (!open || value.trim().length < 3) return setOptions([])
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      try {
        // Biased toward the continental US, like the backend geocoder.
        const params = new URLSearchParams({ q: value, limit: '5', lat: '39.8', lon: '-98.6' })
        const res = await fetch(`${PHOTON_URL}?${params}`, { signal: controller.signal })
        const { features } = (await res.json()) as { features: PhotonFeature[] }
        setOptions([...new Set(features.map(label))])
        setActive(-1)
      } catch {
        // Aborted or offline: typing still works, just without suggestions.
      }
    }, 250)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [value, open])

  function choose(option: string) {
    onChange(option)
    setOpen(false)
  }

  function onKeyDown(e: KeyboardEvent) {
    // Escape first: it must also stop suggestions that are still loading from opening later.
    if (e.key === 'Escape') return setOpen(false)
    if (!open || !options.length) return
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      const step = e.key === 'ArrowDown' ? 1 : -1
      setActive((i) => (i + step + options.length) % options.length)
    } else if (e.key === 'Enter' && active >= 0) {
      e.preventDefault()
      choose(options[active])
    }
  }

  const showList = open && options.length > 0
  return (
    <div className="place">
      <input
        className="input"
        aria-label={name}
        placeholder={placeholder}
        value={value}
        required
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={showList}
        aria-controls={`${id}-list`}
        aria-activedescendant={active >= 0 ? `${id}-${active}` : undefined}
        onChange={(e) => {
          onChange(e.target.value)
          setOpen(true)
        }}
        onKeyDown={onKeyDown}
        onBlur={() => setOpen(false)}
      />
      {showList && (
        <ul className="suggestions card" id={`${id}-list`} role="listbox">
          {options.map((option, i) => (
            <li
              key={option}
              id={`${id}-${i}`}
              role="option"
              aria-selected={i === active}
              // mousedown, not click: it fires before the input's blur closes the list.
              onMouseDown={(e) => {
                e.preventDefault()
                choose(option)
              }}
            >
              {option}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
