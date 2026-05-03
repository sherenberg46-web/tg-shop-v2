import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '@/api'
import type { Product } from '@/types'
import ProductCard from '@/components/ProductCard'
import { useStore } from '@/store'
import type { Region } from '@/types'

const REGIONS: { value: Region; flag: string }[] = [
  { value: 'UA', flag: '🇺🇦' },
  { value: 'TR', flag: '🇹🇷' },
]

const SALES = [
  {
    id: 'big-games',
    title: 'Большие Игры,\nБольшие Скидки',
    subtitle: 'Скидки до 80% в PS Store',
    image: '/images/banners/big-games.jpg',
    gradient: 'linear-gradient(135deg, #1a0005 0%, #6b0010 35%, #c0001a 65%, #ff6b00 100%)',
    accent: '#ff6b00',
    path: '/sale/big-games',
  },
  {
    id: 'hot-deals',
    title: 'Жаркие\nПредложения 🔥',
    subtitle: 'Лучшие цены прямо сейчас',
    image: '/images/banners/hot-deals.jpg',
    gradient: 'linear-gradient(135deg, #001a3a 0%, #003380 40%, #0055cc 70%, #0088ff 100%)',
    accent: '#0088ff',
    path: '/sale/hot-deals',
  },
]

export default function SalesHub() {
  const nav       = useNavigate()
  const region    = useStore(s => s.region)
  const setRegion = useStore(s => s.setRegion)
  const [allDeals,  setAllDeals]  = useState<Product[]>([])
  const [loading,   setLoading]   = useState(true)

  useEffect(() => {
    api.get<Product[]>('/products', { params: { sort: 'discount', limit: 200 } })
      .then(r => {
        const data = Array.isArray(r.data) ? r.data : []
        setAllDeals(data.filter(p => (p.discount_pct ?? 0) > 0))
      })
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      {/* Header */}
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 200,
        background: 'var(--bg-main)',
        borderBottom: '1px solid var(--border)',
        padding: 'max(10px, calc(var(--tg-top, 0px) + 6px)) 16px 12px',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <button
          onClick={() => nav(-1)}
          style={{
            width: 36, height: 36, borderRadius: '50%',
            background: 'var(--bg-card)', border: 'none',
            color: 'var(--text-primary)', fontSize: 18,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', flexShrink: 0,
          }}
        >‹</button>
        <div style={{ flex: 1 }}>
          <p style={{ fontSize: 11, color: 'var(--text-secondary)', fontWeight: 600, letterSpacing: 0.8 }}>
            PS STORE
          </p>
          <p style={{ fontSize: 18, fontWeight: 900, color: 'var(--text-primary)' }}>
            Распродажи
          </p>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {REGIONS.map(r => (
            <button key={r.value} onClick={() => setRegion(r.value)} style={{
              padding: '4px 8px', borderRadius: 8, border: '1.5px solid',
              borderColor: region === r.value ? 'var(--accent)' : 'var(--border)',
              background: region === r.value ? 'var(--accent)' : 'transparent',
              color: region === r.value ? '#fff' : 'var(--text-secondary)',
              fontSize: 13, cursor: 'pointer', lineHeight: 1,
            }}>{r.flag}</button>
          ))}
        </div>
      </div>

      {/* Content */}
      <main style={{
        paddingTop: 'calc(max(10px, var(--tg-top, 0px) + 6px) + 56px + 16px)',
        paddingLeft: 16, paddingRight: 16,
        paddingBottom: 'calc(var(--nav-h) + 16px)',
        minHeight: 'var(--app-h, 100dvh)',
      }}>

        {/* Sale cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 24 }}>
          {SALES.map(sale => (
            <div
              key={sale.id}
              onClick={() => nav(sale.path)}
              style={{
                position: 'relative', height: 140, borderRadius: 16,
                overflow: 'hidden', cursor: 'pointer',
                background: sale.gradient,
              }}
            >
              <img
                src={sale.image} alt={sale.title}
                style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
              />
              <div style={{
                position: 'absolute', inset: 0,
                background: 'linear-gradient(to right, rgba(0,0,0,.75) 55%, rgba(0,0,0,.1) 100%)',
              }} />
              <div style={{
                position: 'absolute', top: 0, bottom: 0, left: 0,
                display: 'flex', flexDirection: 'column', justifyContent: 'center',
                padding: '0 0 0 18px', maxWidth: '65%',
              }}>
                <p style={{ fontSize: 10, fontWeight: 700, color: 'rgba(255,255,255,.65)', letterSpacing: 1.2, marginBottom: 6, textTransform: 'uppercase' }}>
                  🔥 PS STORE
                </p>
                <p style={{
                  fontSize: 16, fontWeight: 900, color: '#fff', lineHeight: 1.2,
                  marginBottom: 10, whiteSpace: 'pre-line',
                  textShadow: '0 2px 8px rgba(0,0,0,.6)',
                }}>{sale.title}</p>
                <div style={{
                  display: 'inline-flex', alignItems: 'center',
                  background: `${sale.accent}44`, backdropFilter: 'blur(6px)',
                  border: `1px solid ${sale.accent}88`,
                  borderRadius: 20, padding: '4px 12px', width: 'fit-content',
                }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#fff' }}>Смотреть →</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* All deals button + section */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          marginBottom: 12,
        }}>
          <h2 style={{ fontSize: 16, fontWeight: 900, color: 'var(--text-primary)', margin: 0 }}>
            🏷️ Все скидки
          </h2>
          {!loading && (
            <button
              onClick={() => nav('/sale/all')}
              style={{
                padding: '5px 14px', borderRadius: 20,
                background: 'var(--gradient)', border: 'none',
                color: '#fff', fontSize: 12, fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              {allDeals.length} игр →
            </button>
          )}
        </div>

        {/* Preview grid */}
        {loading ? (
          <div className="game-grid-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} style={{ borderRadius: 12, background: 'var(--bg-card)', aspectRatio: '3/4' }} />
            ))}
          </div>
        ) : (
          <>
            <div className="game-grid-3">
              {allDeals.slice(0, 9).map(p => (
                <ProductCard key={p.id} product={p} />
              ))}
            </div>
            {allDeals.length > 9 && (
              <button
                onClick={() => nav('/sale/all')}
                style={{
                  width: '100%', marginTop: 16, padding: '12px 0',
                  borderRadius: 12, border: '1.5px solid var(--border)',
                  background: 'var(--bg-card)', color: 'var(--text-primary)',
                  fontSize: 14, fontWeight: 700, cursor: 'pointer',
                }}
              >
                Показать все {allDeals.length} игр со скидкой
              </button>
            )}
          </>
        )}
      </main>
    </>
  )
}
