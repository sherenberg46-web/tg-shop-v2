import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '@/api'
import type { Product, Edition, GameEdition } from '@/types'
import { useStore } from '@/store'
import { toBYN, formatBYN } from '@/utils/price'

const EDITION_PRICE_KEY = {
  UA: 'price_uah', TR: 'price_try', IN: 'price_inr', PL: 'price_pln',
} as const

// ── Fullscreen viewer ─────────────────────────────────────────────
function Lightbox({ src, onClose }: { src: string; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 999,
        background: 'rgba(0,0,0,.92)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 16,
      }}
    >
      <img
        src={src}
        alt=""
        style={{ maxWidth: '100%', maxHeight: '100%', borderRadius: 8, objectFit: 'contain' }}
        onClick={e => e.stopPropagation()}
      />
      <button
        onClick={onClose}
        style={{
          position: 'absolute', top: 16, right: 16,
          width: 36, height: 36, borderRadius: '50%',
          background: 'rgba(255,255,255,.15)', border: 'none',
          color: '#fff', fontSize: 18, cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >✕</button>
    </div>
  )
}

// ── Skeleton ──────────────────────────────────────────────────────
function Skeleton() {
  return (
    <div>
      <div style={{ width: '100%', aspectRatio: '3/4', background: 'var(--bg-card)' }} />
      <div style={{ padding: '16px 16px 100px' }}>
        <div style={{ height: 28, width: '75%', background: 'var(--bg-card)', borderRadius: 6, marginBottom: 10 }} />
        <div style={{ height: 20, width: '40%', background: 'var(--bg-card)', borderRadius: 6, marginBottom: 20 }} />
        <div style={{ height: 36, width: '50%', background: 'var(--bg-card)', borderRadius: 6, marginBottom: 8 }} />
        <div style={{ height: 14, width: '30%', background: 'var(--bg-card)', borderRadius: 6 }} />
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────
export default function ProductPage() {
  const { id }  = useParams<{ id: string }>()
  const nav     = useNavigate()
  const { region, userId, favouriteIds, toggleFavourite, setCartItems, priceSettings } = useStore()

  const [product,      setProduct]      = useState<Product | null>(null)
  const [gameEditions, setGameEditions] = useState<GameEdition[]>([])
  const [edIdx,        setEdIdx]        = useState(0)
  const [added,        setAdded]        = useState(false)
  const [lightbox,     setLightbox]     = useState<string | null>(null)
  const [descOpen,     setDescOpen]     = useState(false)

  useEffect(() => {
    if (!id) return
    setProduct(null)
    setGameEditions([])
    setEdIdx(0)
    api.get<Product>(`/products/${id}`).then(r => {
      setProduct(r.data)
      const defIdx = r.data.editions.findIndex(e => e.is_default)
      setEdIdx(defIdx >= 0 ? defIdx : 0)
    })
    // Load game_editions (parser-sourced, with direct BYN prices)
    api.get<GameEdition[]>(`/products/${id}/editions`, { params: { region } })
      .then(r => { setGameEditions(r.data) })
      .catch(() => {})
  }, [id, region]) // re-fetch when region changes

  const addToCart = useCallback(async () => {
    if (!product || !userId) return
    const activeEd = gameEditions.length > 1 ? gameEditions[edIdx] : null
    const selectedProductId = activeEd?.linked_product_id ?? product.id
    await api.post('/cart', { product_id: selectedProductId, quantity: 1, region })
    const res = await api.get('/cart')
    setCartItems(res.data)
    setAdded(true)
    setTimeout(() => setAdded(false), 2500)
  }, [product, userId, region, setCartItems, gameEditions, edIdx])

  const handleFav = useCallback(async () => {
    if (!product || !userId) return
    favouriteIds.has(product.id)
      ? await api.delete(`/favourites/${product.id}`)
      : await api.post(`/favourites/${product.id}`)
    toggleFavourite(product.id)
  }, [product, userId, favouriteIds, toggleFavourite])

  if (!product) return <Skeleton />

  const isSubscription = product.product_type === 'subscription'
  const isTopup        = product.product_type === 'topup'
  const isSimple       = isSubscription || isTopup

  // ── Pricing ──────────────────────────────────────────
  // Prefer game_editions (parser-sourced, direct BYN) over legacy editions
  const useGameEditions = gameEditions.length > 1
  const hasEditions     = useGameEditions ? true : product.editions.length > 1

  const getEdByn = (ed: Edition) => {
    const raw = ed[EDITION_PRICE_KEY[region]] as number | null
    return raw != null ? toBYN(raw, region, priceSettings) : 0
  }

  const getGameEdByn = (ed: GameEdition): number =>
    region === 'TR' ? (ed.price_byn_tr ?? ed.price_byn ?? 0) : (ed.price_byn ?? 0)

  const getGameEdOldByn = (ed: GameEdition): number | null => {
    if (ed.is_free || ed.discount_pct <= 0) return null
    const cur = getGameEdByn(ed)
    return cur > 0 ? Math.round(cur / (1 - ed.discount_pct / 100)) : null
  }

  const baseByn = region === 'TR'
    ? (product.price_byn_tr ?? product.price_byn ?? 0)
    : (product.price_byn ?? 0)

  const currentGameEd = useGameEditions ? gameEditions[edIdx] : null
  const currentEd     = !useGameEditions && hasEditions ? product.editions[edIdx] : null

  const isFreeProduct = currentGameEd?.is_free ?? false
  const currentByn    = isFreeProduct ? 0
    : currentGameEd ? getGameEdByn(currentGameEd)
    : currentEd     ? getEdByn(currentEd)
    : baseByn

  const pct    = currentGameEd ? currentGameEd.discount_pct : (product.discount_pct ?? 0)
  const oldByn = currentGameEd
    ? getGameEdOldByn(currentGameEd)
    : pct > 0 ? Math.round(currentByn / (1 - pct / 100)) : null

  const isFav = favouriteIds.has(product.id)

  // ── Screenshots (use cover image for now) ────────────
  const screenshots = product.image_url ? [product.image_url] : []

  // ── Release date ──────────────────────────────────────
  const releaseDate = product.release_date
    ? new Date(product.release_date).toLocaleDateString('ru', { day: 'numeric', month: 'long', year: 'numeric' })
    : null

  return (
    <div style={{ background: 'var(--bg-main)', minHeight: 'var(--app-h, 100dvh)', paddingBottom: 'calc(var(--nav-h) + 72px)' }}>

      {/* ── Overlaid top buttons ── */}
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 200,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: 'max(12px, calc(var(--tg-top, 0px) + 8px)) 16px 0',
        pointerEvents: 'none',
      }}>
        <button
          onClick={() => nav(-1)}
          style={{
            pointerEvents: 'all',
            width: 38, height: 38, borderRadius: '50%',
            background: 'rgba(0,0,0,.45)', backdropFilter: 'blur(10px)',
            border: '1px solid rgba(255,255,255,.15)',
            color: '#fff', fontSize: 20,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer',
          }}
        >‹</button>
        {!isSimple && (
          <button
            onClick={handleFav}
            style={{
              pointerEvents: 'all',
              width: 38, height: 38, borderRadius: '50%',
              background: 'rgba(0,0,0,.45)', backdropFilter: 'blur(10px)',
              border: '1px solid rgba(255,255,255,.15)',
              color: isFav ? '#ff4d6d' : '#fff', fontSize: 20,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', transition: 'color .2s',
            }}
          >{isFav ? '♥' : '♡'}</button>
        )}
      </div>

      {/* ── Hero cover ── */}
      <div style={{
        width: '100%', background: 'var(--bg-card)',
        position: 'relative', overflow: 'hidden',
      }}>
        <img
          src={product.image_url ?? ''}
          alt={product.title}
          style={{ width: '100%', height: 'auto', display: 'block' }}
          onError={e => { (e.currentTarget as HTMLImageElement).style.visibility = 'hidden' }}
        />
        {/* Bottom gradient fade */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          height: 80,
          background: 'linear-gradient(to bottom, transparent, var(--bg-main))',
          pointerEvents: 'none',
        }} />
      </div>

      {/* ── Content ── */}
      <div style={{ padding: '0 16px' }}>

        {/* Title */}
        <h1 style={{
          fontSize: 22, fontWeight: 900, lineHeight: 1.2,
          color: 'var(--text-primary)', marginTop: 12, marginBottom: 8,
        }}>{product.title}</h1>

        {/* Badges row */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
          {product.platform && !isSimple && (
            <span style={{
              background: '#1a1d24', color: '#cdd3de',
              fontSize: 11, fontWeight: 700, padding: '3px 9px', borderRadius: 6,
              border: '1px solid rgba(255,255,255,.12)',
            }}>{product.platform}</span>
          )}
          {product.is_preorder && (
            <span style={{
              background: 'linear-gradient(135deg, #f59e0b, #ef4444)',
              color: '#fff', fontSize: 11, fontWeight: 800,
              padding: '3px 9px', borderRadius: 6,
            }}>⏳ ПРЕДЗАКАЗ</span>
          )}
          {pct > 0 && (
            <span style={{
              background: 'rgba(0,179,122,.15)', border: '1px solid rgba(0,179,122,.35)',
              color: '#00b37a', fontSize: 11, fontWeight: 800,
              padding: '3px 9px', borderRadius: 6,
            }}>-{pct}%</span>
          )}
        </div>

        {/* Price */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: product.discount_until && pct > 0 ? 6 : 20, flexWrap: 'wrap' }}>
          <span style={{
            fontSize: 30, fontWeight: 900, letterSpacing: -0.5,
            color: '#00b37a',
          }}>{formatBYN(currentByn)}</span>
          {oldByn != null && (
            <span style={{ fontSize: 16, color: 'var(--text-old)', textDecoration: 'line-through', fontWeight: 500 }}>
              {formatBYN(oldByn)}
            </span>
          )}
        </div>

        {/* Sale end date */}
        {pct > 0 && product.discount_until && (
          <p style={{ fontSize: 12, color: '#ef4444', fontWeight: 600, marginBottom: 14 }}>
            🕐 Скидка до:{' '}
            {new Date(product.discount_until).toLocaleDateString('ru', { day: 'numeric', month: 'long', year: 'numeric' })}
          </p>
        )}

        {/* PS Plus badge */}
        {product.requires_ps_plus && !isSimple && (
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            background: 'rgba(0,100,200,.15)', border: '1px solid rgba(0,100,200,.3)',
            color: '#60a5fa', borderRadius: 8, padding: '4px 10px',
            fontSize: 12, fontWeight: 600, marginBottom: 14,
          }}>
            🎮 Требуется PS Plus для онлайн-игры
          </div>
        )}

        {/* Editions */}
        {hasEditions && !isSimple && (
          <div style={{ marginBottom: 20 }}>
            <p style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>
              Издание
            </p>
            <div style={{ display: 'flex', gap: 10, overflowX: 'auto', scrollbarWidth: 'none', paddingBottom: 4 }}>
              {useGameEditions
                ? gameEditions.map((ed, i) => {
                    const edByn = ed.is_free ? 0 : getGameEdByn(ed)
                    const edOld = getGameEdOldByn(ed)
                    return (
                      <div
                        key={ed.id}
                        onClick={() => {
                          if (ed.linked_product_id && ed.linked_product_id !== product.id) {
                            nav(`/product/${ed.linked_product_id}`)
                          } else {
                            setEdIdx(i)
                          }
                        }}
                        style={{
                          minWidth: 130, flexShrink: 0,
                          padding: '12px 14px',
                          background: i === edIdx
                            ? 'linear-gradient(135deg, rgba(0,212,170,.12), rgba(0,136,255,.12))'
                            : 'var(--bg-card)',
                          borderRadius: 12,
                          border: `2px solid ${i === edIdx ? 'var(--grad-start)' : 'var(--border)'}`,
                          cursor: 'pointer', transition: 'all .15s',
                        }}
                      >
                        <p style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>
                          {ed.edition_name}
                        </p>
                        {ed.is_free
                          ? <p style={{ fontSize: 15, fontWeight: 900, color: '#22c55e' }}>Бесплатно</p>
                          : <p style={{ fontSize: 16, fontWeight: 900 }}>{formatBYN(edByn)}</p>
                        }
                        {edOld && (
                          <p style={{ fontSize: 11, color: 'var(--text-old)', textDecoration: 'line-through' }}>
                            {formatBYN(edOld)}
                          </p>
                        )}
                        {ed.discount_pct > 0 && (
                          <p style={{ fontSize: 10, fontWeight: 800, color: '#00b37a', marginTop: 3 }}>
                            -{ed.discount_pct}%
                          </p>
                        )}
                      </div>
                    )
                  })
                : product.editions.map((ed, i) => {
                    const edByn = getEdByn(ed)
                    const edOld = pct > 0 ? Math.round(edByn / (1 - pct / 100)) : null
                    return (
                      <div
                        key={ed.id}
                        onClick={() => setEdIdx(i)}
                        style={{
                          minWidth: 130, flexShrink: 0,
                          padding: '12px 14px',
                          background: i === edIdx
                            ? 'linear-gradient(135deg, rgba(0,212,170,.12), rgba(0,136,255,.12))'
                            : 'var(--bg-card)',
                          borderRadius: 12,
                          border: `2px solid ${i === edIdx ? 'var(--grad-start)' : 'var(--border)'}`,
                          cursor: 'pointer', transition: 'all .15s',
                        }}
                      >
                        <p style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>
                          {ed.name}
                        </p>
                        <p style={{ fontSize: 16, fontWeight: 900 }}>{formatBYN(edByn)}</p>
                        {edOld && (
                          <p style={{ fontSize: 11, color: 'var(--text-old)', textDecoration: 'line-through' }}>
                            {formatBYN(edOld)}
                          </p>
                        )}
                      </div>
                    )
                  })
              }
            </div>
          </div>
        )}

        {/* Screenshots strip */}
        {!isSimple && screenshots.length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <p style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>
              Медиа
            </p>
            <div style={{
              display: 'flex', gap: 8, overflowX: 'auto', scrollbarWidth: 'none',
              margin: '0 -16px', padding: '0 16px 6px',
            }}>
              {screenshots.map((url, i) => (
                <div
                  key={i}
                  onClick={() => setLightbox(url)}
                  style={{
                    flexShrink: 0, width: 120, height: 80,
                    borderRadius: 8, overflow: 'hidden',
                    background: 'var(--bg-card)',
                    cursor: 'zoom-in', border: '1px solid var(--border)',
                  }}
                >
                  <img
                    src={url}
                    alt=""
                    loading="lazy"
                    style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Description */}
        {product.description && (
          <div style={{ marginBottom: 20 }}>
            <p style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>
              Описание
            </p>
            <div
              style={{
                fontSize: 14, lineHeight: 1.7, color: 'var(--text-secondary)',
                overflow: descOpen ? 'visible' : 'hidden',
                display: descOpen ? 'block' : '-webkit-box',
                WebkitLineClamp: descOpen ? undefined : 4,
                WebkitBoxOrient: 'vertical' as const,
              }}
            >
              {product.description}
            </div>
            {product.description.length > 200 && (
              <button
                onClick={() => setDescOpen(v => !v)}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--grad-start)', fontSize: 13, fontWeight: 600,
                  padding: '6px 0 0', display: 'block',
                }}
              >
                {descOpen ? 'Свернуть ↑' : 'Читать далее ↓'}
              </button>
            )}
          </div>
        )}

        {/* Specs */}
        {!isSimple && (
          <div style={{ marginBottom: 20 }}>
            <p style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>
              Характеристики
            </p>
            <div style={{ background: 'var(--bg-card)', borderRadius: 12, overflow: 'hidden', boxShadow: 'var(--shadow-card)' }}>
              {[
                product.platform && { label: 'Платформа', value: product.platform },
                product.genre && { label: 'Жанр', value: product.genre },
                { label: 'Язык', value: 'RU / EN' },
                { label: 'Издатель', value: 'PlayStation' },
                releaseDate && { label: 'Дата релиза', value: releaseDate },
                product.is_preorder && { label: 'Статус', value: '⏳ Предзаказ', accent: '#f59e0b' },
                product.rating > 0 && { label: 'Рейтинг', value: `★ ${product.rating.toFixed(1)}`, accent: '#f59e0b' },
              ].filter(Boolean).map((row: any, i, arr) => (
                <div key={row.label} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '11px 16px',
                  borderBottom: i < arr.length - 1 ? '1px solid var(--border)' : 'none',
                }}>
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{row.label}</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: row.accent ?? 'var(--text-primary)' }}>
                    {row.value}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Sticky CTA ── */}
      <div style={{
        position: 'fixed',
        bottom: 'var(--nav-h)', left: 0, right: 0,
        padding: '10px 16px 12px',
        background: 'rgba(15,17,22,.95)',
        backdropFilter: 'blur(12px)',
        borderTop: '1px solid var(--border)',
        zIndex: 100,
      }}>
        <button
          className="btn-grad"
          onClick={addToCart}
          disabled={!userId}
          style={{ position: 'relative', overflow: 'hidden' }}
        >
          {added ? (
            <>✓ Добавлено в корзину</>
          ) : isFreeProduct ? (
            <><span>🎁</span> Получить бесплатно</>
          ) : (
            <>
              <span>🛒</span>
              {product.is_preorder
                ? ` Предзаказ — ${formatBYN(currentByn)}`
                : ` Добавить в корзину — ${formatBYN(currentByn)}`}
            </>
          )}
        </button>
      </div>

      {/* Lightbox */}
      {lightbox && <Lightbox src={lightbox} onClose={() => setLightbox(null)} />}
    </div>
  )
}
