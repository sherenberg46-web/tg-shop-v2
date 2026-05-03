import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '@/api'
import type { Product } from '@/types'
import ProductCard from '@/components/ProductCard'

interface CollectionData {
  id: number
  title: string
  slug: string
  description: string | null
  products: Product[]
}

export default function Collection() {
  const { slug } = useParams<{ slug: string }>()
  const nav = useNavigate()
  const [data, setData] = useState<CollectionData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!slug) return
    setLoading(true)
    api.get<CollectionData>(`/collections/${slug}`)
      .then(r => setData(r.data))
      .catch(() => setError('Коллекция не найдена'))
      .finally(() => setLoading(false))
  }, [slug])

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={s.header}>
        <button onClick={() => nav(-1)} style={s.back}>← Назад</button>
        {data && (
          <div>
            <h1 style={s.title}>{data.title}</h1>
            {data.description && <p style={s.desc}>{data.description}</p>}
            <p style={s.meta}>{data.products.length} товаров</p>
          </div>
        )}
      </div>

      {/* Body */}
      {loading && <div style={s.loader}>Загрузка...</div>}
      {error && <div style={s.error}>{error}</div>}
      {data && data.products.length === 0 && (
        <div style={s.empty}>В этой коллекции пока нет товаров</div>
      )}
      {data && data.products.length > 0 && (
        <div style={s.grid}>
          {data.products.map(p => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      )}
    </div>
  )
}

const s: Record<string, React.CSSProperties> = {
  page: { minHeight: '100vh', background: 'var(--bg)', paddingBottom: 100 },
  header: {
    background: 'var(--card)',
    padding: '16px 16px 12px',
    borderBottom: '1px solid var(--border, #23232a)',
    position: 'sticky', top: 0, zIndex: 10,
  },
  back: {
    background: 'none', border: 'none', color: 'var(--accent, #00d4aa)',
    fontSize: 14, fontWeight: 600, cursor: 'pointer', padding: '0 0 10px 0',
  },
  title: { fontSize: 20, fontWeight: 800, color: 'var(--text)', margin: '0 0 4px' },
  desc: { fontSize: 13, color: 'var(--text-secondary, #aaa)', margin: '0 0 4px' },
  meta: { fontSize: 12, color: 'var(--text-secondary, #aaa)', margin: 0 },
  loader: { padding: 40, textAlign: 'center', color: '#aaa' },
  error: { padding: 40, textAlign: 'center', color: '#ef4444' },
  empty: { padding: 40, textAlign: 'center', color: '#aaa', fontSize: 14 },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: 10,
    padding: '12px 10px',
  },
}
