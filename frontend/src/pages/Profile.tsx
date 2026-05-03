import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '@/store'
import type { Region } from '@/types'

const REGIONS: { value: Region; flag: string; name: string; currency: string }[] = [
  { value: 'UA', flag: '🇺🇦', name: 'Украина',  currency: '₴ UAH' },
  { value: 'TR', flag: '🇹🇷', name: 'Турция',   currency: '₺ TRY' },
]

const ABOUT_TEXT = `🎮 GAME STORE

Мы — магазин, специализирующийся на продаже игр, подписок, пополнении кошельков и DLC для PlayStation.

✅ Более 3 лет на рынке
✅ Самые выгодные цены
✅ Быстрая доставка ключей
✅ Поддержка 24/7
✅ Тысячи довольных покупателей

По всем вопросам: @gamestore_by`

export default function Profile() {
  const nav = useNavigate()
  const { userId, region, setRegion } = useStore()
  const [showAbout, setShowAbout] = useState(false)

  const MENU = [
    { icon: '📦', bg: '#e8f5e9', label: 'Мои заказы',  sub: 'История покупок',               onClick: () => nav('/orders') },
    { icon: '🔑', bg: '#e3f2fd', label: 'Мои ключи',   sub: 'Купленные активационные коды',  onClick: () => nav('/keys') },
    { icon: '💬', bg: '#fff3e0', label: 'Поддержка',   sub: 'Написать в чат',                onClick: () => window.open('https://t.me/gamestore_by', '_blank') },
    { icon: 'ℹ️', bg: '#f3e5f5', label: 'О магазине',  sub: 'Условия и правила',             onClick: () => setShowAbout(true) },
  ]

  return (
    <main className="page">
      {/* User card */}
      <div style={{
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius-lg)',
        padding: 16,
        marginBottom: 20,
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        boxShadow: 'var(--shadow-card)',
      }}>
        <div className="profile-avatar">
          {userId ? String(userId)[0] : '?'}
        </div>
        <div>
          <p style={{ fontWeight: 800, fontSize: 17 }}>Telegram User</p>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>ID: {userId ?? '—'}</p>
          <span className="stars-badge" style={{ marginTop: 6, display: 'inline-flex' }}>⭐ 0 Stars</span>
        </div>
      </div>

      {/* Region */}
      <h2 style={{ fontSize: 15, fontWeight: 700, marginBottom: 10, color: 'var(--text-secondary)' }}>
        РЕГИОН ЦЕН
      </h2>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 24 }}>
        {REGIONS.map(r => (
          <button
            key={r.value}
            onClick={() => setRegion(r.value)}
            style={{
              padding: '12px 14px',
              borderRadius: 'var(--radius-md)',
              border: `2px solid ${r.value === region ? 'var(--grad-start)' : 'var(--border)'}`,
              background: r.value === region
                ? 'linear-gradient(135deg, rgba(0,212,170,.08), rgba(0,136,255,.08))'
                : 'var(--bg-card)',
              display: 'flex', alignItems: 'center', gap: 8,
              transition: 'all .15s',
              boxShadow: 'var(--shadow-card)',
            }}
          >
            <span style={{ fontSize: 24 }}>{r.flag}</span>
            <div style={{ textAlign: 'left' }}>
              <div style={{
                fontSize: 13, fontWeight: 700,
                color: r.value === region ? 'var(--grad-start)' : 'var(--text-primary)',
              }}>{r.name}</div>
              <div style={{ fontSize: 11, color: 'var(--text-hint)' }}>{r.currency}</div>
            </div>
            {r.value === region && (
              <span style={{
                marginLeft: 'auto', fontSize: 14,
                background: 'var(--gradient)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                fontWeight: 900,
              }}>✓</span>
            )}
          </button>
        ))}
      </div>

      {/* Menu */}
      <h2 style={{ fontSize: 15, fontWeight: 700, marginBottom: 10, color: 'var(--text-secondary)' }}>
        МЕНЮ
      </h2>
      <div className="settings-list">
        {MENU.map(item => (
          <button key={item.label} className="settings-item" onClick={item.onClick}>
            <div className="settings-item__icon" style={{ background: item.bg }}>
              {item.icon}
            </div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{item.label}</div>
              <div style={{ fontSize: 12, color: 'var(--text-hint)', marginTop: 1 }}>{item.sub}</div>
            </div>
            <span className="settings-item__arrow">›</span>
          </button>
        ))}
      </div>

      <p style={{ textAlign: 'center', fontSize: 12, color: 'var(--text-hint)', marginTop: 24 }}>
        TG-Shop v1.0 · Powered by Telegram Stars ⭐
      </p>

      {/* About modal */}
      {showAbout && (
        <div
          onClick={() => setShowAbout(false)}
          style={{
            position: 'fixed', inset: 0, zIndex: 1000,
            background: 'rgba(0,0,0,.6)',
            display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
            backdropFilter: 'blur(4px)',
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              background: 'var(--bg-card)',
              borderRadius: '20px 20px 0 0',
              padding: '24px 20px 40px',
              width: '100%',
              maxWidth: 480,
            }}
          >
            {/* Handle */}
            <div style={{
              width: 36, height: 4, borderRadius: 2,
              background: 'var(--border)',
              margin: '0 auto 20px',
            }} />

            <pre style={{
              whiteSpace: 'pre-wrap',
              fontFamily: 'inherit',
              fontSize: 14,
              lineHeight: 1.7,
              color: 'var(--text-primary)',
              margin: 0,
            }}>
              {ABOUT_TEXT}
            </pre>

            <button
              onClick={() => setShowAbout(false)}
              style={{
                marginTop: 24,
                width: '100%',
                padding: '14px 0',
                borderRadius: 14,
                border: 'none',
                background: 'var(--gradient)',
                color: '#fff',
                fontWeight: 700,
                fontSize: 15,
                cursor: 'pointer',
              }}
            >
              Закрыть
            </button>
          </div>
        </div>
      )}
    </main>
  )
}
