import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '@/api'
import type { Order } from '@/types'

const STATUS_LABEL: Record<string, { label: string; color: string }> = {
  pending:    { label: 'Ожидает оплаты', color: '#f59e0b' },
  paid:       { label: 'Оплачен',        color: '#3b82f6' },
  processing: { label: 'В обработке',    color: '#8b5cf6' },
  completed:  { label: 'Выполнен',       color: '#10b981' },
  cancelled:  { label: 'Отменён',        color: '#ef4444' },
}

function formatDate(str: string): string {
  if (!str) return '—'
  try {
    return new Date(str).toLocaleString('ru', {
      day: 'numeric', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return str
  }
}

export default function Orders() {
  const nav = useNavigate()
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get<Order[]>('/orders/my')
      .then(r => setOrders(Array.isArray(r.data) ? r.data : []))
      .catch(() => setOrders([]))
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      {/* Header */}
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 200,
        background: 'var(--bg-card)',
        padding: 'max(10px, calc(var(--tg-top, 0px) + 6px)) 16px 12px',
        display: 'flex', alignItems: 'center', gap: 12,
        borderBottom: '1px solid var(--border)',
      }}>
        <button
          onClick={() => nav(-1)}
          style={{
            width: 36, height: 36, borderRadius: '50%',
            background: 'var(--bg-main)', border: 'none',
            color: 'var(--text-primary)', fontSize: 20,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', flexShrink: 0,
          }}
        >‹</button>
        <p style={{ fontSize: 18, fontWeight: 800 }}>Мои заказы</p>
      </div>

      <main style={{
        paddingTop: 'calc(max(10px, var(--tg-top, 0px) + 6px) + 48px + 12px)',
        paddingLeft: 16, paddingRight: 16,
        paddingBottom: 'calc(var(--nav-h) + 16px)',
        minHeight: 'var(--app-h, 100dvh)',
      }}>
        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} style={{
                height: 100, borderRadius: 14,
                background: 'var(--bg-card)',
              }} />
            ))}
          </div>
        ) : orders.length === 0 ? (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            paddingTop: 80, textAlign: 'center',
          }}>
            <span style={{ fontSize: 52, marginBottom: 14 }}>📦</span>
            <p style={{ fontSize: 17, fontWeight: 700, marginBottom: 6 }}>У вас пока нет заказов</p>
            <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
              Перейдите в каталог и сделайте первый заказ
            </p>
            <button
              onClick={() => nav('/')}
              style={{
                marginTop: 20, padding: '12px 28px',
                borderRadius: 14, border: 'none',
                background: 'var(--gradient)',
                color: '#fff', fontWeight: 700, fontSize: 14,
                cursor: 'pointer',
              }}
            >В каталог</button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {orders.map(order => {
              const st = STATUS_LABEL[order.status] ?? { label: order.status, color: '#888' }
              return (
                <div key={order.id} style={{
                  background: 'var(--bg-card)',
                  borderRadius: 14,
                  padding: '14px 16px',
                  border: '1px solid var(--border)',
                }}>
                  {/* Top row */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                      Заказ #{order.id}
                    </span>
                    <span style={{
                      fontSize: 11, fontWeight: 700,
                      color: st.color,
                      background: st.color + '22',
                      padding: '3px 9px', borderRadius: 8,
                    }}>{st.label}</span>
                  </div>

                  {/* Items */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 10 }}>
                    {order.items.map((item, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: 13, fontWeight: 600, flex: 1, marginRight: 8 }}>
                          {item.title}
                          {item.quantity > 1 && (
                            <span style={{ color: 'var(--text-secondary)', fontWeight: 400 }}> ×{item.quantity}</span>
                          )}
                        </span>
                        <span style={{ fontSize: 13, fontWeight: 700, color: '#00e0c6', whiteSpace: 'nowrap' }}>
                          {item.price_paid} BYN
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* Bottom row */}
                  <div style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    paddingTop: 10, borderTop: '1px solid var(--border)',
                  }}>
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{formatDate(order.created_at)}</span>
                    <span style={{ fontSize: 15, fontWeight: 800 }}>{order.total_byn} BYN</span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </main>
    </>
  )
}
