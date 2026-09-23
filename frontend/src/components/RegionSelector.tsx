import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { LeadType, Regions } from '../types'

export interface RegionValue {
  continent: string
  country: string
  city: string
}

export const GLOBAL: RegionValue = { continent: '', country: '', city: '' }

export default function RegionSelector({
  leadType,
  value,
  onChange,
}: {
  leadType: LeadType
  value: RegionValue
  onChange: (value: RegionValue) => void
}) {
  const [regions, setRegions] = useState<Regions | null>(null)
  const [cityQuery, setCityQuery] = useState(value.city)
  const [citySuggestions, setCitySuggestions] = useState<string[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    api.regions().then(setRegions).catch(() => {})
  }, [])

  useEffect(() => {
    setCityQuery(value.city)
  }, [value.city])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      api
        .cities({ lead_type: leadType, continent: value.continent, country: value.country, q: cityQuery })
        .then((res) => setCitySuggestions(res.cities))
        .catch(() => setCitySuggestions([]))
    }, 200)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leadType, value.continent, value.country, cityQuery])

  const countries = value.continent ? regions?.continents[value.continent] ?? [] : []

  return (
    <div className="flex flex-wrap gap-2">
      <select
        value={value.continent}
        onChange={(e) => onChange({ continent: e.target.value, country: '', city: '' })}
        className="rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100"
      >
        <option value="">Global</option>
        {regions &&
          Object.keys(regions.continents).map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
      </select>

      <select
        value={value.country}
        disabled={!value.continent}
        onChange={(e) => onChange({ ...value, country: e.target.value, city: '' })}
        className="rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 disabled:opacity-40 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100"
      >
        <option value="">All countries</option>
        {countries.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>

      <div className="relative">
        <input
          value={cityQuery}
          placeholder="City…"
          onChange={(e) => {
            setCityQuery(e.target.value)
            setShowSuggestions(true)
          }}
          onFocus={() => setShowSuggestions(true)}
          onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
          className="w-40 rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100"
        />
        {value.city && (
          <button
            aria-label="Clear city"
            onClick={() => {
              setCityQuery('')
              onChange({ ...value, city: '' })
            }}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-700"
          >
            ×
          </button>
        )}
        {showSuggestions && citySuggestions.length > 0 && (
          <ul className="absolute z-10 mt-1 max-h-56 w-48 overflow-auto rounded-lg border border-neutral-200 bg-white py-1 text-sm shadow-lg dark:border-neutral-700 dark:bg-neutral-800">
            {citySuggestions.map((city) => (
              <li key={city}>
                <button
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    setCityQuery(city)
                    setShowSuggestions(false)
                    onChange({ ...value, city })
                  }}
                  className="block w-full px-3 py-1.5 text-left hover:bg-neutral-100 dark:hover:bg-neutral-700"
                >
                  {city}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {(value.continent || value.country || value.city) && (
        <button
          onClick={() => {
            setCityQuery('')
            onChange(GLOBAL)
          }}
          className="rounded-lg px-3 py-2 text-sm text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-300"
        >
          Reset to Global
        </button>
      )}
    </div>
  )
}
