import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '@/api'
import type { Product } from '@/types'
import { useStore } from '@/store'
import { formatBYN } from '@/utils/price'

const INTERVAL_MS = 3500

// ── API banner (from admin panel) ─────────────────────────────────
interface ApiBanner {
  id: number
  title: string
  subtitle: string
  image_url: string
  link_ua: string
  link_tr: string
  link_url: string
  gradient: string
  sort_order: number
  collection_slug: string
}

const DEFAULT_GRADIENT = 'linear-gradient(135deg, #1a0005 0%, #6b0010 35%, #c0001a 65%, #ff6b00 100%)'

// ── Main component ────────────────────────────────────────────────
export default function HeroBanner() {
  const nav = useNavigate()
  const region = useStore(s => s.region)
  const [apiBanners, setApiBanners] = useState<ApiBanner[]>([])
  const [productSlides, setProductSlides] = useState<Product[]>([])
  const [current, setCurrent] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const touchStartX = useRef(0)
  const touchStartY = useRef(0)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.get<ApiBanner[]>('/banners').then(r => {
      if (Array.isArray(r.data)) setApiBanners(r.data)
    }).catch(() => {})

    api.get<Product[]>('/products', { params: { sort: 'discount', limit: 8 } })
      .then(r => {
        const data = Array.isArray(r.data) ? r.data : []
        setProductSlides(data.filter(p => p.image_url && p.price_byn))
      }).catch(() => {})
  }, [])

  const allSlides = [...apiBanners, ...productSlides]
  const totalSlides = allSlides.length

  useEffect(() => {
    if (!totalSlides) return
    timerRef.current = setInterval(() => setCurrent(c => (c + 1) % totalSlides), INTERVAL_MS)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [totalSlides])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const onMove = (e: TouchEvent) => {
      const dx = Math.abs(e.touches[0].clientX - touchStartX.current)
      const dy = Math.abs(e.touches[0].clientY - touchStartY.current)
      if (dx > dy && dx > 6) e.preventDefault()
    }
    el.addEventListener('touchmove', onMove, { passive: false })
    return () => el.removeEventListener('touchmove', onMove)
  }, [])

  const goTo = (idx: number) => {
    setCurrent(idx)
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = setInterval(() => setCurrent(c => (c + 1) % totalSlides), INTERVAL_MS)
  }

  const onTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX
    touchStartY.current = e.touches[0].clientY
  }

  const onTouchEnd = (e: React.TouchEvent) => {
    const dx = touchStartX.current - e.changedTouches[0].clientX
    const dy = Math.abs(touchStartY.current - e.changedTouches[0].clientY)
    if (Math.abs(dx) > 40 && Math.abs(dx) > dy) {
      goTo(dx > 0 ? (current + 1) % totalSlides : (current - 1 + totalSlides) % totalSlides)
    }
  }

  if (!totalSlides) return null

  return (
    <div className="hero-banner-wrapper">
      <div
        ref={containerRef}
        style={{
          position: 'relative', width: '100%', height: 180, overflow: 'hidden',
          margin: 0, padding: 0, boxSizing: 'border-box', borderRadius: 12,
          userSelect: 'none', WebkitUserSelect: 'none', touchAction: 'pan-y',
        }}
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
      >
        {/* API banner slides */}
        {apiBanners.map((b, i) => {
          const link = b.collection_slug
            ? `/collection/${b.collection_slug}`
            : region === 'TR' ? (b.link_tr || b.link_url) : (b.link_ua || b.link_url)
          const handleTap = () => {
            if (!link) return
            if (link.startsWith('http')) window.open(link, '_blank')
            else nav(link)
          }
          return (
            <div
              key={`banner-${b.id}`}
              onClick={handleTap}
              style={{
                position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
                opacity: i === current ? 1 : 0,
                transition: 'opacity .45s ease',
                pointerEvents: i === current ? 'auto' : 'none',
                overflow: 'hidden',
                cursor: link ? 'pointer' : 'default',
                background: b.gradient || DEFAULT_GRADIENT,
              }}
            >
              {/* Background image */}
              {b.image_url && (
                <img
                  src={b.image_url}
                  alt={b.title}
                  style={{
                    position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
                    objectFit: 'cover', objectPosition: 'center',
                  }}
                />
              )}

              {/* Overlay */}
              <div style={{
                position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
                background: 'linear-gradient(to right, rgba(0,0,0,.72) 50%, rgba(0,0,0,.15) 100%)',
              }} />

              {/* Text */}
              <div style={{
                position: 'absolute', top: 0, bottom: 0, left: 0,
                display: 'flex', flexDirection: 'column', justifyContent: 'center',
                padding: '0 0 20px 16px', maxWidth: '70%',
              }}>
                {b.title && (
                  <p style={{
                    fontSize: 17, fontWeight: 900, color: '#fff', lineHeight: 1.15,
                    letterSpacing: -0.3, marginBottom: 8,
                    textShadow: '0 2px 10px rgba(0,0,0,.7)',
                    whiteSpace: 'pre-line',
                  }}>{b.title}</p>
                )}
                {b.subtitle && (
                  <p style={{ fontSize: 11, color: 'rgba(255,255,255,.8)', fontWeight: 500, marginBottom: 10 }}>
                    {b.subtitle}
                  </p>
                )}
                {link && (
                  <div style={{
                    display: 'inline-flex', alignItems: 'center',
                    background: 'rgba(255,255,255,.15)',
                    backdropFilter: 'blur(6px)',
                    border: '1px solid rgba(255,255,255,.3)',
                    borderRadius: 20, padding: '5px 12px', width: 'fit-content',
                  }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#fff' }}>Смотреть →</span>
                  </div>
                )}
              </div>
            </div>
          )
        })}

        {/* Product slides */}
        {productSlides.map((s, i) => {
          const idx = i + apiBanners.length
          const isVisible = idx === current
          const pct = s.discount_pct ?? 0
          const byn = s.price_byn ?? 0
          const oldByn = pct > 0 && byn > 0 ? Math.round(byn / (1 - pct / 100)) : 0
          return (
            <div
              key={`prod-${s.id}`}
              onClick={() => nav(`/product/${s.id}`)}
              style={{
                position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
                opacity: isVisible ? 1 : 0, transition: 'opacity .45s ease',
                pointerEvents: isVisible ? 'auto' : 'none', cursor: 'pointer',
              }}
            >
              <img
                src={s.image_url!}
                alt={s.title}
                style={{ display: 'block', width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center top' }}
                onError={e => { e.currentTarget.onerror = null; setProductSlides(prev => prev.filter(p => p.id !== s.id)) }}
              />
              <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'linear-gradient(to bottom, rgba(0,0,0,.05) 30%, rgba(0,0,0,.78) 100%)' }} />
              <div style={{ position: 'absolute', bottom: 34, left: 14, right: 14 }}>
                <p style={{ fontSize: 15, fontWeight: 900, color: '#fff', textShadow: '0 1px 6px rgba(0,0,0,.5)', marginBottom: 5, lineHeight: 1.25, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>{s.title}</p>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {pct > 0 && <span style={{ background: '#00b37a', color: '#fff', fontSize: 11, fontWeight: 800, padding: '2px 7px', borderRadius: 5 }}>-{pct}%</span>}
                  {oldByn > 0 && <span style={{ fontSize: 12, color: 'rgba(255,255,255,.55)', textDecoration: 'line-through' }}>{formatBYN(oldByn)}</span>}
                  {byn > 0 && <span style={{ fontSize: 16, fontWeight: 900, color: '#00d4aa' }}>{formatBYN(byn)}</span>}
                </div>
              </div>
            </div>
          )
        })}

        {/* Dots */}
        <div style={{ position: 'absolute', bottom: 10, left: 0, right: 0, display: 'flex', justifyContent: 'center', gap: 5 }} onClick={e => e.stopPropagation()}>
          {allSlides.map((_, i) => (
            <button key={i} onClick={() => goTo(i)} style={{
              width: i === current ? 20 : 6, height: 6, borderRadius: 3, border: 'none', padding: 0,
              background: i === current ? '#00d4aa' : 'rgba(255,255,255,.35)', transition: 'all .3s', cursor: 'pointer',
            }} />
          ))}
        </div>
      </div>
    </div>
  )
}
