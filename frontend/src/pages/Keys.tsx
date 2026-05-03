import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '@/api'
import type { Order, OrderItem } from '@/types'

interface KeyEntry {
  orderId: number
  title: string
  quantity: number
  region: string
}

export default function Keys() {
  const nav = useNavigate()
  const [keys, setKeys] = useState<KeyEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState<number | null>(null)

  useEffect(() => {
    api.get<Order[]>('/orders/my')
      .then(r => {
        const orders = Array.isArray(r.data) ? r.data : []
        // Show items from completed orders as "purchased keys"
        const entries: KeyEntry[] = []
        for (const order of orders) {
          if (order.status === 'completed') {
            for (const item of order.items) {
              entries.push({
                orderId: order.id,
                title: item.title,
                quantity: item.quantity,
                region: item.region,
              })
            }
          }
        }
        setKeys(entries)
      })
      .catch(() => setKeys([]))
      .finally(() => setLoading(false))
  }, [])

  const copyKey = (text: string, idx: number) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(idx)
      setTimeout(() => setCopied(null), 2000)
    })
  }

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
        <p style={{ fontSize: 18, fontWeight: 800 }}>Мои ключи</p>
      </div>

      <main style={{
        paddingTop: 'calc(max(10px, var(--tg-top, 0px) + 6px) + 48px + 12px)',
        paddingLeft: 16, paddingRight: 16,
        paddingBottom: 'calc(var(--nav-h) + 16px)',
        minHeight: 'var(--app-h, 100dvh)',
      }}>
        {/* Info banner */}
        <div style={{
          background: 'rgba(0,212,170,.1)',
          border: '1px solid rgba(0,212,170,.3)',
          borderRadius: 12,
          padding: '10px 14px',
          marginBottom: 16,
          fontSize: 13,
          color: 'var(--text-secondary)',
          lineHeight: 1.5,
        }}>
          🔑 Ключи активации отправляются в Telegram-бот после выполнения заказа.
          Свяжитесь с <a
            href="https://t.me/Sherenberg"
            target="_blank"
            rel="noreferrer"
            style={{ color: '#00e0c6', fontWeight: 600 }}
          >@Sherenberg</a> если ключ не получен.
        </div>

        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} style={{ height: 80, borderRadius: 14, background: 'var(--bg-card)' }} />
            ))}
          </div>
        ) : keys.length === 0 ? (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            paddingTop: 60, textAlign: 'center',
          }}>
            <span style={{ fontSize: 52, marginBottom: 14 }}>🔑</span>
            <p style={{ fontSize: 17, fontWeight: 700, marginBottom: 6 }}>У вас пока нет ключей</p>
            <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
              Ключи появятся здесь после выполнения заказа
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
            {keys.map((entry, idx) => (
              <div key={idx} style={{
                background: 'var(--bg-card)',
                borderRadius: 14,
                padding: '14px 16px',
                border: '1px solid var(--border)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                  <div style={{ flex: 1 }}>
                    <p style={{ fontSize: 14, fontWeight: 700, marginBottom: 4, lineHeight: 1.3 }}>
                      {entry.title}
                    </p>
                    <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                      Заказ #{entry.orderId} · {entry.region}
                      {entry.quantity > 1 && ` · ×${entry.quantity}`}
                    </p>
                  </div>
                  <button
                    onClick={() => copyKey(entry.title, idx)}
                    style={{
                      flexShrink: 0,
                      padding: '8px 12px',
                      borderRadius: 10,
                      border: 'none',
                      background: copied === idx ? '#10b981' : 'var(--bg-main)',
                      color: copied === idx ? '#fff' : 'var(--text-secondary)',
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: 'pointer',
                      transition: 'all .2s',
                      display: 'flex', alignItems: 'center', gap: 5,
                    }}
                  >
                    {copied === idx ? '✓ Скопировано' : '📋 Копировать'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </>
  )
}
