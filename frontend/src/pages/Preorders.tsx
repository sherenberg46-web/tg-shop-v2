import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '@/api'
import type { Product, Region } from '@/types'
import { formatBYN } from '@/utils/price'
import { useStore } from '@/store'

const REGIONS: { value: Region; flag: string }[] = [
  { value: 'UA', flag: '🇺🇦' },
  { value: 'TR', flag: '🇹🇷' },
]

type SortKey = 'date' | 'price_asc' | 'price_desc'

const SORTS: { id: SortKey; label: string }[] = [
  { id: 'date',       label: '📅 Дата выхода' },
  { id: 'price_asc',  label: '↑ Цена' },
  { id: 'price_desc', label: '↓ Цена' },
]

function formatReleaseDate(dateStr: string | null | undefined): string | null {
  if (!dateStr) return null
  try {
    return new Date(dateStr).toLocaleDateString('ru', { day: 'numeric', month: 'long', year: 'numeric' })
  } catch {
    return null
  }
}

function PreorderCard({ product }: { product: Product }) {
  const nav = useNavigate()
  const region = useStore(s => s.region)
  const byn = region === 'TR' ? (product.price_byn_tr ?? product.price_byn) : product.price_byn
  const releaseDate = formatReleaseDate(product.release_date)

  return (
    <article
      onClick={() => nav(`/product/${product.id}`)}
      style={{
        background: 'var(--bg-card)',
        borderRadius: 12,
        overflow: 'hidden',
        boxShadow: 'var(--shadow-card)',
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        WebkitUserSelect: 'none',
        userSelect: 'none',
        border: '1px solid var(--border)',
      }}
    >
      <div style={{ position: 'relative', background: 'var(--bg-card)' }}>
        <img
          src={product.image_url ?? ''}
          alt={product.title}
          loading="lazy"
          style={{ width: '100%', height: 'auto', display: 'block' }}
          onError={e => { (e.currentTarget as HTMLImageElement).style.visibility = 'hidden' }}
        />
        <div style={{
          position: 'absolute', top: 5, left: 5,
          background: 'linear-gradient(135deg, #f59e0b, #ef4444)',
          color: '#fff', fontSize: 9, fontWeight: 900,
          padding: '2px 6px', borderRadius: 4,
        }}>ПРЕДЗАКАЗ</div>
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {byn != null ? (
            <span style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-primary)' }}>
              {formatBYN(byn)}
            </span>
          ) : (
            <span style={{ fontSize: 12, color: 'var(--text-hint)' }}>Уточнить цену</span>
          )}
          {releaseDate && (
            <span style={{ fontSize: 10, color: '#f59e0b', fontWeight: 600 }}>
              {releaseDate}
            </span>
          )}
        </div>
      </div>
    </article>
  )
}

export default function Preorders() {
  const nav       = useNavigate()
  const region    = useStore(s => s.region)
  const setRegion = useStore(s => s.setRegion)
  const [games,   setGames]   = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [sort,    setSort]    = useState<SortKey>('date')

  useEffect(() => {
    setLoading(true)
    api.get<Product[]>('/products', {
      params: { task_type: 'preorders', region, limit: 200 },
    })
      .then(r => setGames(Array.isArray(r.data) ? r.data : []))
      .finally(() => setLoading(false))
  }, [region])

  const sorted = useMemo(() => {
    if (sort === 'date') return games  // already sorted by date ASC from backend
    return [...games].sort((a, b) => {
      const pa = a.price_byn ?? 0, pb = b.price_byn ?? 0
      return sort === 'price_asc' ? pa - pb : pb - pa
    })
  }, [games, sort])

  return (
    <>
      {/* Banner */}
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 200,
        background: 'linear-gradient(135deg, #1a0035 0%, #2d006b 40%, #4a0080 70%, #1a0040 100%)',
        padding: 'max(10px, calc(var(--tg-top, 0px) + 6px)) 16px 12px',
        display: 'flex', alignItems: 'center', gap: 12,
        borderBottom: '1px solid rgba(245,158,11,.2)',
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
            PS STORE
          </p>
          <p style={{ fontSize: 18, fontWeight: 900, color: '#fff', letterSpacing: -0.3 }}>
            ⏳ Предзаказы
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
            background: 'rgba(245,158,11,.2)', border: '1px solid rgba(245,158,11,.4)',
            color: '#f59e0b', fontSize: 12, fontWeight: 700,
            padding: '3px 10px', borderRadius: 12,
          }}>{games.length} игр</span>
        )}
      </div>

      <main style={{
        paddingTop: 'calc(max(10px, var(--tg-top, 0px) + 6px) + 56px + 12px)',
        paddingLeft: 16, paddingRight: 16,
        paddingBottom: 'calc(var(--nav-h) + 16px)',
        minHeight: 'var(--app-h, 100dvh)',
      }}>
        {/* Sort tabs */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 16, overflowX: 'auto', scrollbarWidth: 'none' }}>
          {SORTS.map(s => (
            <button key={s.id} onClick={() => setSort(s.id)} style={{
              flexShrink: 0, padding: '6px 14px', borderRadius: 20,
              fontSize: 12, fontWeight: 600, border: '1.5px solid',
              borderColor: sort === s.id ? 'transparent' : 'var(--border)',
              background: sort === s.id ? 'var(--gradient)' : 'var(--bg-card)',
              color: sort === s.id ? '#fff' : 'var(--text-secondary)',
              cursor: 'pointer', transition: 'all .15s',
            }}>{s.label}</button>
          ))}
        </div>

        {loading ? (
          <div className="game-grid-3">
            {Array.from({ length: 9 }).map((_, i) => (
              <div key={i} style={{ borderRadius: 12, background: 'var(--bg-card)', aspectRatio: '3/4' }} />
            ))}
          </div>
        ) : sorted.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 60, textAlign: 'center' }}>
            <span style={{ fontSize: 48, marginBottom: 12 }}>⏳</span>
            <p style={{ fontSize: 17, fontWeight: 700, marginBottom: 6 }}>Нет предзаказов</p>
            <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>Следите за обновлениями</p>
          </div>
        ) : (
          <div className="game-grid-3">
            {sorted.map(p => <PreorderCard key={p.id} product={p} />)}
          </div>
        )}
      </main>
    </>
  )
}
