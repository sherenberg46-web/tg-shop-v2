import { useNavigate } from 'react-router-dom'
import type { Product } from '@/types'
import { formatBYN } from '@/utils/price'
import { useStore } from '@/store'

interface Props { product: Product }

export default function ProductCard({ product }: Props) {
  const nav = useNavigate()
  const region = useStore(s => s.region)
  const byn = region === 'TR'
    ? (product.price_byn_tr ?? product.price_byn)
    : product.price_byn
  const isSubscription = product.product_type === 'subscription'
  const isTopup = product.product_type === 'topup'

  const pct = product.discount_pct ?? 0
  const oldByn = (byn != null && !isSubscription && !isTopup && pct > 0)
    ? Math.round(byn / (1 - pct / 100))
    : null

  const discountLabel = oldByn != null && oldByn > byn!
    ? `-${Math.round((1 - byn! / oldByn) * 100)}%`
    : null

  return (
    <article
      className="product-card"
      onClick={() => nav(`/product/${product.id}`)}
      role="button"
      tabIndex={0}
    >
      <div className="product-card__img-wrap">
        <img
          className="product-card__img"
          src={product.image_url ?? ''}
          alt={product.title}
          loading="lazy"
          onError={e => { (e.currentTarget as HTMLImageElement).style.visibility = 'hidden' }}
        />
        {discountLabel && !isSubscription && !isTopup && (
          <span className="product-card__discount">{discountLabel}</span>
        )}
        {product.is_preorder && (
          <span className="product-card__discount" style={{ background: '#f59e0b' }}>⏳ Pre</span>
        )}
        {product.platform && !isSubscription && !isTopup && (
          <span className="product-card__platform">{product.platform}</span>
        )}
      </div>

      <div className="product-card__body">
        {product.genre && !isSubscription && !isTopup && (
          <p style={{
            fontSize: 10, fontWeight: 600, color: 'var(--text-hint)',
            textTransform: 'uppercase', letterSpacing: 0.5,
            marginBottom: 2, lineHeight: 1,
          }}>{product.genre.split(',')[0]}</p>
        )}
        <p className="product-card__title">{product.title}</p>
        <div className="product-card__prices">
          {byn != null ? (
            <>
              <span className="product-card__price">{formatBYN(byn)}</span>
              {oldByn != null && oldByn > byn && (
                <span className="product-card__old">{formatBYN(oldByn)}</span>
              )}
            </>
          ) : (
            <span className="product-card__price" style={{ color: 'var(--text-hint)' }}>—</span>
          )}
        </div>
        {pct > 0 && product.discount_until && (
          <p style={{ fontSize: 10, color: '#ef4444', fontWeight: 600, marginTop: 2 }}>
            до {new Date(product.discount_until).toLocaleDateString('ru', { day: 'numeric', month: 'short' })}
          </p>
        )}
      </div>
    </article>
  )
}
