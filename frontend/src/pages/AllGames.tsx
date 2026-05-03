import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import api from '@/api'
import type { Product, Region } from '@/types'
import ProductCard from '@/components/ProductCard'
import { useStore } from '@/store'

const REGIONS: { value: Region; flag: string }[] = [
  { value: 'UA', flag: '🇺🇦' },
  { value: 'TR', flag: '🇹🇷' },
]

type SortKey = 'rating' | 'discount' | 'price_asc' | 'price_desc'

const SORTS: { id: SortKey; label: string }[] = [
  { id: 'rating',     label: '⭐ Рейтинг' },
  { id: 'discount',   label: '🔥 Скидка' },
  { id: 'price_asc',  label: '↑ Цена' },
  { id: 'price_desc', label: '↓ Цена' },
]

const LIMIT = 40

export default function AllGames() {
  const nav       = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const region    = useStore(s => s.region)
  const setRegion = useStore(s => s.setRegion)

  const [games,    setGames]    = useState<Product[]>([])
  const [loading,  setLoading]  = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore,  setHasMore]  = useState(true)
  const [offset,   setOffset]   = useState(0)

  const [sort,     setSort]     = useState<SortKey>('rating')
  const [search,   setSearch]   = useState(() => searchParams.get('q') ?? '')
  const [onlyDiscount, setOnlyDiscount] = useState(false)

  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [debouncedSearch, setDebouncedSearch] = useState(() => searchParams.get('q') ?? '')

  // Sync URL ?q= param into search state when navigating from Header
  useEffect(() => {
    const q = searchParams.get('q') ?? ''
    if (q && q !== search) {
      setSearch(q)
      setDebouncedSearch(q)
    }
  }, [searchParams]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => {
      setDebouncedSearch(search)
      // keep URL in sync
      if (search) setSearchParams({ q: search }, { replace: true })
      else setSearchParams({}, { replace: true })
    }, 400)
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current) }
  }, [search]) // eslint-disable-line react-hooks/exhaustive-deps

  const fetchGames = useCallback((newOffset: number, replace: boolean) => {
    if (replace) setLoading(true)
    else setLoadingMore(true)

    const params: Record<string, string | number> = {
      limit: LIMIT,
      offset: newOffset,
      region,
      product_type: 'game',
    }
    if (debouncedSearch.length >= 2) params.search = debouncedSearch
    // No sort param — sorting done client-side

    api.get<Product[]>('/products', { params })
      .then(r => {
        let data = Array.isArray(r.data) ? r.data : []
        // client-side filters
        if (onlyDiscount) data = data.filter(p => (p.discount_pct ?? 0) > 0)

        if (replace) {
          setGames(data)
        } else {
          setGames(prev => {
            const next = [...prev, ...data]
            return next
          })
        }
        setHasMore(data.length === LIMIT)
        setOffset(newOffset + data.length)
      })
      .finally(() => { setLoading(false); setLoadingMore(false) })
  }, [debouncedSearch, sort, onlyDiscount, region])

  // Reset + reload when filters change
  useEffect(() => {
    setOffset(0)
    setGames([])
    setHasMore(true)
    fetchGames(0, true)
  }, [debouncedSearch, sort, onlyDiscount, region]) // eslint-disable-line react-hooks/exhaustive-deps

  const sortedGames = [...games].sort((a, b) => {
    const getPrice = (p: Product) =>
      (region === 'TR' ? (p.price_byn_tr ?? p.price_byn) : p.price_byn) ?? 0
    if (sort === 'price_asc') return getPrice(a) - getPrice(b)
    if (sort === 'price_desc') return getPrice(b) - getPrice(a)
    if (sort === 'discount') return (b.discount_pct ?? 0) - (a.discount_pct ?? 0)
    return (b.rating ?? 0) - (a.rating ?? 0)
  })

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
            🎮 Все игры
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
        paddingTop: 'calc(max(10px, var(--tg-top, 0px) + 6px) + 56px + 12px)',
        paddingLeft: 16, paddingRight: 16,
        paddingBottom: 'calc(var(--nav-h) + 16px)',
        minHeight: 'var(--app-h, 100dvh)',
      }}>

        {/* Search */}
        <div style={{ position: 'relative', marginBottom: 12 }}>
          <span style={{
            position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)',
            fontSize: 16, pointerEvents: 'none', color: 'var(--text-hint)',
          }}>🔍</span>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Поиск по названию..."
            style={{
              width: '100%', boxSizing: 'border-box',
              padding: '10px 36px 10px 36px',
              borderRadius: 12, border: '1.5px solid var(--border)',
              background: 'var(--bg-card)', color: 'var(--text-primary)',
              fontSize: 14, outline: 'none',
            }}
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              style={{
                position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
                background: 'none', border: 'none', color: 'var(--text-hint)',
                fontSize: 18, cursor: 'pointer', padding: 0, lineHeight: 1,
              }}
            >×</button>
          )}
        </div>

        {/* Sort + discount filter */}
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
          <button onClick={() => setOnlyDiscount(v => !v)} style={{
            flexShrink: 0, padding: '6px 14px', borderRadius: 20,
            fontSize: 12, fontWeight: 600, border: '1.5px solid',
            borderColor: onlyDiscount ? 'transparent' : 'var(--border)',
            background: onlyDiscount ? 'linear-gradient(135deg,#c0001a,#ff6b00)' : 'var(--bg-card)',
            color: onlyDiscount ? '#fff' : 'var(--text-secondary)',
            cursor: 'pointer', transition: 'all .15s',
          }}>🏷 Скидки</button>
        </div>

        {/* Count */}
        {!loading && (
          <p style={{ fontSize: 12, color: 'var(--text-hint)', marginBottom: 12 }}>
            {sortedGames.length} {sortedGames.length === 1 ? 'игра' : 'игр'}
            {hasMore ? '+' : ''}
          </p>
        )}

        {/* Grid */}
        {loading ? (
          <div className="game-grid-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} style={{ borderRadius: 12, background: 'var(--bg-card)', aspectRatio: '3/4' }} />
            ))}
          </div>
        ) : sortedGames.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 60, textAlign: 'center' }}>
            <span style={{ fontSize: 48, marginBottom: 12 }}>🎮</span>
            <p style={{ fontSize: 17, fontWeight: 700, marginBottom: 6 }}>Ничего не найдено</p>
            <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>Попробуйте изменить фильтры</p>
          </div>
        ) : (
          <>
            <div className="game-grid-2">
              {sortedGames.map(p => <ProductCard key={p.id} product={p} />)}
            </div>
            {hasMore && (
              <button
                onClick={() => fetchGames(offset, false)}
                disabled={loadingMore}
                style={{
                  width: '100%', marginTop: 16, padding: '12px 0',
                  borderRadius: 12, border: '1.5px solid var(--border)',
                  background: 'var(--bg-card)', color: 'var(--text-primary)',
                  fontSize: 14, fontWeight: 700, cursor: loadingMore ? 'default' : 'pointer',
                  opacity: loadingMore ? 0.6 : 1,
                }}
              >
                {loadingMore ? 'Загрузка...' : 'Показать ещё'}
              </button>
            )}
          </>
        )}
      </main>
    </>
  )
}
