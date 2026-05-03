import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '@/api'
import type { Product, Region } from '@/types'
import { useStore } from '@/store'
import { formatBYN } from '@/utils/price'

const REGIONS: { value: Region; flag: string }[] = [
  { value: 'UA', flag: '🇺🇦' },
  { value: 'TR', flag: '🇹🇷' },
]

function SaleCard({ product }: { product: Product }) {
  const nav    = useNavigate()
  const region = useStore(s => s.region)

  const byn    = region === 'TR'
    ? (product.price_byn_tr ?? product.price_byn)
    : product.price_byn
  const pct    = product.discount_pct ?? 0
  const oldByn = byn != null && pct > 0 ? Math.round(byn / (1 - pct / 100)) : null

  return (
    <article
      onClick={() => nav(`/product/${product.id}`)}
      style={{
        background: 'var(--bg-card)', borderRadius: 12, overflow: 'hidden',
        boxShadow: 'var(--shadow-card)', cursor: 'pointer',
        display: 'flex', flexDirection: 'column',
        WebkitUserSelect: 'none', userSelect: 'none',
        border: '1px solid var(--border)',
      }}
    >
      <div style={{ position: 'relative' }}>
        <img
          src={product.image_url ?? ''} alt={product.title} loading="lazy"
          style={{ width: '100%', height: 'auto', display: 'block' }}
          onError={e => { (e.currentTarget as HTMLImageElement).style.visibility = 'hidden' }}
        />
        {pct > 0 && (
          <div style={{
            position: 'absolute', top: 5, right: 5,
            background: 'linear-gradient(135deg, #0088ff, #0055cc)',
            color: '#fff', fontSize: 9, fontWeight: 900,
            padding: '2px 6px', borderRadius: 4,
          }}>-{pct}%</div>
        )}
        {product.platform && (
          <div style={{
            position: 'absolute', bottom: 5, right: 5,
            background: 'rgba(0,0,0,.6)', color: '#fff',
            fontSize: 9, fontWeight: 700, padding: '2px 5px',
            borderRadius: 4, backdropFilter: 'blur(4px)',
          }}>{product.platform}</div>
        )}
      </div>
      <div style={{ padding: '8px 8px 10px', flex: 1, display: 'flex', flexDirection: 'column' }}>
        <p style={{
          fontSize: 12, fontWeight: 500, lineHeight: 1.35,
          color: 'var(--text-primary)', flex: 1, overflow: 'hidden',
          display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
          marginBottom: 6,
        }}>{product.title}</p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {byn != null && (
            <span style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-primary)' }}>
              {formatBYN(byn)}
            </span>
          )}
          {oldByn != null && (
            <span style={{ fontSize: 10, color: 'var(--text-old)', textDecoration: 'line-through' }}>
              {formatBYN(oldByn)}
            </span>
          )}
        </div>
      </div>
    </article>
  )
}

type SortKey = 'discount' | 'price_asc' | 'price_desc'

const SORTS: { id: SortKey; label: string }[] = [
  { id: 'discount',   label: '🔥 По скидке' },
  { id: 'price_asc',  label: '↑ Цена' },
  { id: 'price_desc', label: '↓ Цена' },
]

export default function HotDealsSale() {
  const nav       = useNavigate()
  const region    = useStore(s => s.region)
  const setRegion = useStore(s => s.setRegion)
  const [games,   setGames]   = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [sort,    setSort]    = useState<SortKey>('discount')

  useEffect(() => {
    api.get<Product[]>('/products', { params: { sort: 'discount', limit: 200, featured: true } })
      .then(r => {
        const data = Array.isArray(r.data) ? r.data : []
        // Hot deals: featured games with any discount, plus top-rated discounted games
        const withDiscount = data.filter(p => (p.discount_pct ?? 0) > 0)
        setGames(withDiscount)
      })
      .finally(() => setLoading(false))
  }, [])

  const deals = useMemo(() => {
    if (sort === 'discount') return games
    return [...games].sort((a, b) => {
      const getPrice = (p: Product) =>
        (region === 'TR' ? (p.price_byn_tr ?? p.price_byn) : p.price_byn) ?? 0
      return sort === 'price_asc' ? getPrice(a) - getPrice(b) : getPrice(b) - getPrice(a)
    })
  }, [games, sort, region])

  return (
    <>
      {/* Banner */}
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 200,
        background: 'linear-gradient(135deg, #001a3a 0%, #003380 40%, #0055cc 70%, #0088ff 100%)',
        padding: 'max(10px, calc(var(--tg-top, 0px) + 6px)) 16px 12px',
        display: 'flex', alignItems: 'center', gap: 12,
        borderBottom: '1px solid rgba(0,136,255,.3)',
      }}>
        <button
          onClick={() => nav(-1)}
          style={{
            width: 36, height: 36, borderRadius: '50%',
            background: 'rgba(255,255,255,.12)', border: 'none',
            color: '#fff', fontSize: 18,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', flexShrink: 0,
          }}
        >‹</button>
        <div style={{ flex: 1 }}>
          <p style={{ fontSize: 11, color: 'rgba(255,255,255,.6)', fontWeight: 600, letterSpacing: 0.8 }}>
            💥 PS STORE
          </p>
          <p style={{ fontSize: 18, fontWeight: 900, color: '#fff', letterSpacing: -0.3 }}>
            Жаркие Предложения 🔥
          </p>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {REGIONS.map(r => (
            <button key={r.value} onClick={() => setRegion(r.value)} style={{
              padding: '4px 8px', borderRadius: 8, border: '1.5px solid',
              borderColor: region === r.value ? '#fff' : 'rgba(255,255,255,.25)',
              background: region === r.value ? 'rgba(255,255,255,.2)' : 'transparent',
              color: '#fff', fontSize: 13, cursor: 'pointer', lineHeight: 1,
            }}>{r.flag}</button>
          ))}
        </div>
        {!loading && (
          <span style={{
            background: 'rgba(0,136,255,.2)', border: '1px solid rgba(0,136,255,.4)',
            color: '#66bbff', fontSize: 12, fontWeight: 700,
            padding: '3px 10px', borderRadius: 12,
          }}>{deals.length} игр</span>
        )}
      </div>

      {/* Content */}
      <main style={{
        paddingTop: 'calc(max(10px, var(--tg-top, 0px) + 6px) + 56px + 12px)',
        paddingLeft: 16, paddingRight: 16,
        paddingBottom: 'calc(var(--nav-h) + 16px)',
        minHeight: 'var(--app-h, 100dvh)',
      }}>
        <div style={{ display: 'flex', gap: 6, marginBottom: 16, overflowX: 'auto', scrollbarWidth: 'none' }}>
          {SORTS.map(s => (
            <button
              key={s.id} onClick={() => setSort(s.id)}
              style={{
                flexShrink: 0, padding: '6px 14px', borderRadius: 20,
                fontSize: 12, fontWeight: 600, border: '1.5px solid',
                borderColor: sort === s.id ? 'transparent' : 'var(--border)',
                background: sort === s.id
                  ? 'linear-gradient(135deg, #003380, #0088ff)'
                  : 'var(--bg-card)',
                color: sort === s.id ? '#fff' : 'var(--text-secondary)',
                cursor: 'pointer', transition: 'all .15s',
              }}
            >{s.label}</button>
          ))}
        </div>

        {loading ? (
          <div className="game-grid-3">
            {Array.from({ length: 9 }).map((_, i) => (
              <div key={i} style={{ borderRadius: 12, background: 'var(--bg-card)', aspectRatio: '3/4' }} />
            ))}
          </div>
        ) : deals.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 60, textAlign: 'center' }}>
            <span style={{ fontSize: 48, marginBottom: 12 }}>💥</span>
            <p style={{ fontSize: 17, fontWeight: 700, marginBottom: 6 }}>Горячие предложения скоро</p>
            <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>Пока нет специальных предложений</p>
          </div>
        ) : (
          <div className="game-grid-3">
            {deals.map(p => <SaleCard key={p.id} product={p} />)}
          </div>
        )}
      </main>
    </>
  )
}
