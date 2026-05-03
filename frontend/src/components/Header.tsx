import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '@/store'
import type { Region } from '@/types'

const REGIONS: { value: Region; flag: string; label: string }[] = [
  { value: 'UA', flag: '🇺🇦', label: 'UA · Украина' },
  { value: 'TR', flag: '🇹🇷', label: 'TR · Турция' },]
export default function Header() {
  const navigate = useNavigate()
  const { region, setRegion } = useStore()
  const [open,  setOpen]  = useState(false)
  const [input, setInput] = useState('')
  const dropRef  = useRef<HTMLDivElement>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const current = REGIONS.find(r => r.value === region) ?? REGIONS[0]

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropRef.current && !dropRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleChange = (val: string) => {
    setInput(val)
    if (timerRef.current) clearTimeout(timerRef.current)
    const trimmed = val.trim()
    if (trimmed.length >= 2) {
      timerRef.current = setTimeout(() => {
        navigate(`/all-games?q=${encodeURIComponent(trimmed)}`)
        setInput('')
      }, 500)
    }
  }

  const handleClear = () => {
    setInput('')
    if (timerRef.current) clearTimeout(timerRef.current)
  }

  return (
    <header className="header">
      <div className="header__top">
        {/* Logo */}
        <a className="logo" href="/" onClick={e => { e.preventDefault(); navigate('/') }}>
          <img src="/my-logo.jpg" alt="GAME STORE" style={{ height: 64, width: 64, borderRadius: 6, objectFit: 'contain' }} />
          <span className="logo__text">GAME STORE</span>
        </a>

        {/* Region selector */}
        <div style={{ position: 'relative' }} ref={dropRef}>
          <button className="region-btn" onClick={() => setOpen(v => !v)}>
            <span className="region-btn__flag">{current.flag}</span>
            <span>{current.value}</span>
            <span className="region-btn__arrow">{open ? '▲' : '▼'}</span>
          </button>

          {open && (
            <>
              <div className="overlay" onClick={() => setOpen(false)} />
              <div className="region-dropdown">
                {REGIONS.map(r => (
                  <button
                    key={r.value}
                    className={`region-option ${r.value === region ? 'active' : ''}`}
                    onClick={() => { setRegion(r.value); setOpen(false) }}
                  >
                    <span className="region-option__flag">{r.flag}</span>
                    {r.label}
                    {r.value === region && <span style={{ marginLeft: 'auto', fontSize: 12 }}>✓</span>}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Search */}
      <div className="search-wrap" style={{ position: 'relative' }}>
        <svg className="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2.5">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
        <input
          className="search-input"
          type="text"
          placeholder="Найти игру, подписку, кошелёк"
          value={input}
          onChange={e => handleChange(e.target.value)}
        />
        {input && (
          <button
            onClick={handleClear}
            style={{
              position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--text-hint)', fontSize: 16, lineHeight: 1,
              padding: '0 2px', display: 'flex', alignItems: 'center',
            }}
          >✕</button>
        )}
      </div>
    </header>
  )
}




