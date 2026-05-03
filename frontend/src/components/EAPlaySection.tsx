import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '@/api'
import type { Product } from '@/types'
import { formatBYN } from '@/utils/price'

export default function EAPlaySection() {
  const nav = useNavigate()
  const [items, setItems] = useState<Product[]>([])

  useEffect(() => {
    api.get<Product[]>('/products', {
      params: { product_type: 'subscription', limit: 100 },
    }).then(res => {
      const data = Array.isArray(res.data) ? res.data : []
      setItems(data.filter(item => item.title.toLowerCase().includes('ea play')))
    })
  }, [])

  if (!items.length) return null

  return (
    <section className="section">
      <h2 className="section__title">🎯 EA Play</h2>

      <div className="h-scroll">
        {items.map(item => (
          <div
            key={item.id}
            onClick={() => nav(`/product/${item.id}`)}
            className="product-card"
          >
            <img src={item.image_url ?? undefined} alt={item.title} />
            <h4>{item.title}</h4>
            <p>{formatBYN(item.price_byn!)}</p>
          </div>
        ))}
      </div>
    </section>
  )
}