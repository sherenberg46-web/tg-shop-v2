import { useEffect, useState } from 'react'
import api from '@/api'
import type { Product } from '@/types'
import ProductCard from '@/components/ProductCard'
import { useStore } from '@/store'

export default function Favourites() {
  const userId = useStore(s => s.userId)
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading]   = useState(true)

  useEffect(() => {
    if (!userId) { setLoading(false); return }
    api.get<Product[]>('/favourites')
      .then(r => setProducts(Array.isArray(r.data) ? r.data : []))
      .finally(() => setLoading(false))
  }, [userId])

  if (loading) return <main className="page"><p style={{ color: 'var(--text-hint)' }}>Загрузка…</p></main>

  if (!products.length) {
    return (
      <main className="page">
        <div className="empty-state">
          <div className="empty-state__icon">♡</div>
          <p className="empty-state__title">Избранное пусто</p>
          <p className="empty-state__sub">Нажмите ♡ на странице товара,<br/>чтобы добавить в избранное</p>
        </div>
      </main>
    )
  }

  return (
    <main className="page">
      <h1 style={{ fontSize: 22, fontWeight: 900, marginBottom: 16 }}>
        Избранное <span style={{ color: 'var(--text-hint)', fontSize: 16, fontWeight: 500 }}>({products.length})</span>
      </h1>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {products.map(p => <ProductCard key={p.id} product={p} />)}
      </div>
    </main>
  )
}
