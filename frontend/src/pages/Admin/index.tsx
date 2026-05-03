import { useState, useLayoutEffect } from 'react'
import { clearToken, getToken } from './api'
import Login from './Login'
import Products from './Products'
import Orders from './Orders'
import Stats from './Stats'
import Categories from './Categories'
import Banners from './Banners'
import Settings from './Settings'
import Collections from './Collections'

type Tab = 'products' | 'orders' | 'stats' | 'categories' | 'banners' | 'settings' | 'collections'

export default function AdminApp() {
  const [authed, setAuthed] = useState(() => !!getToken())
  const [tab, setTab] = useState<Tab>('orders')

  // Reset dark Mini App theme synchronously before first paint.
  // telegram-web-app.js may set inline body styles that override CSS,
  // so we must clear them via JS as well.
  useLayoutEffect(() => {
    const html = document.documentElement
    const body = document.body
    html.classList.add('admin')
    body.style.setProperty('background', '#f1f5f9', 'important')
    body.style.setProperty('color', '#1e293b', 'important')
    body.style.setProperty('height', 'auto', 'important')
    body.style.setProperty('overflow', 'auto', 'important')
    return () => {
      html.classList.remove('admin')
      body.style.removeProperty('background')
      body.style.removeProperty('color')
      body.style.removeProperty('height')
      body.style.removeProperty('overflow')
    }
  }, [])

  if (!authed) {
    return (
      <div style={{ minHeight: '100vh', background: '#f1f5f9' }}>
        <Login onLogin={() => setAuthed(true)} />
      </div>
    )
  }

  const handleLogout = () => {
    clearToken()
    setAuthed(false)
  }

  return (
    <div style={s.app}>
      {/* Sidebar */}
      <aside style={s.sidebar}>
        <div style={s.logo}>🛒 TG-Shop</div>
        <div style={s.logoSub}>Admin Panel</div>

        <nav style={s.nav}>
          <div style={s.navGroup}>ОСНОВНОЕ</div>
          {(
            [
              { key: 'orders' as Tab, icon: '📦', label: 'Заказы' },
              { key: 'products' as Tab, icon: '🎮', label: 'Товары' },
              { key: 'stats' as Tab, icon: '📊', label: 'Статистика' },
            ] as const
          ).map(({ key, icon, label }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              style={{ ...s.navItem, ...(tab === key ? s.navItemActive : {}) }}
            >
              <span style={s.navIcon}>{icon}</span>
              {label}
            </button>
          ))}
          <div style={s.navGroup}>КОНТЕНТ</div>
          {(
            [
              { key: 'categories' as Tab, icon: '🏷️', label: 'Категории' },
              { key: 'banners' as Tab, icon: '🎯', label: 'Баннеры' },
              { key: 'collections' as Tab, icon: '📚', label: 'Коллекции' },
            ] as const
          ).map(({ key, icon, label }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              style={{ ...s.navItem, ...(tab === key ? s.navItemActive : {}) }}
            >
              <span style={s.navIcon}>{icon}</span>
              {label}
            </button>
          ))}
          <div style={s.navGroup}>СИСТЕМА</div>
          <button
            onClick={() => setTab('settings')}
            style={{ ...s.navItem, ...(tab === 'settings' ? s.navItemActive : {}) }}
          >
            <span style={s.navIcon}>⚙️</span>
            Настройки
          </button>
        </nav>

        <button onClick={handleLogout} style={s.logoutBtn}>
          ← Выйти
        </button>
      </aside>

      {/* Main content */}
      <main style={s.main}>
        <div style={s.header}>
          <h1 style={s.pageTitle}>
            {tab === 'orders' ? '📦 Заказы'
              : tab === 'products' ? '🎮 Товары'
              : tab === 'stats' ? '📊 Статистика'
              : tab === 'categories' ? '🏷️ Категории'
              : tab === 'banners' ? '🎯 Баннеры'
              : tab === 'collections' ? '📚 Коллекции'
              : '⚙️ Настройки'}
          </h1>
        </div>
        <div style={s.content}>
          {tab === 'orders' && <Orders />}
          {tab === 'products' && <Products />}
          {tab === 'stats' && <Stats />}
          {tab === 'categories' && <Categories />}
          {tab === 'banners' && <Banners />}
          {tab === 'collections' && <Collections />}
          {tab === 'settings' && <Settings />}
        </div>
      </main>
    </div>
  )
}

const s: Record<string, React.CSSProperties> = {
  app: {
    display: 'flex',
    minHeight: '100vh',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    background: '#f1f5f9',
  },
  sidebar: {
    width: 220,
    background: '#1e293b',
    color: '#fff',
    display: 'flex',
    flexDirection: 'column',
    padding: '24px 0',
    flexShrink: 0,
    minHeight: '100vh',
  },
  logo: {
    fontSize: 18,
    fontWeight: 800,
    padding: '0 20px',
    color: '#fff',
    letterSpacing: '-0.02em',
  },
  logoSub: {
    fontSize: 11,
    color: '#64748b',
    padding: '2px 20px 28px',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
  },
  nav: {
    display: 'flex',
    flexDirection: 'column',
    flex: 1,
    gap: 2,
    padding: '0 10px',
  },
  navGroup: {
    fontSize: 10,
    fontWeight: 700,
    color: '#475569',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.1em',
    padding: '12px 12px 4px',
  },
  navItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '10px 12px',
    background: 'none',
    border: 'none',
    color: '#94a3b8',
    fontSize: 14,
    fontWeight: 500,
    cursor: 'pointer',
    borderRadius: 8,
    textAlign: 'left',
    transition: 'background 0.15s',
  },
  navItemActive: {
    background: '#2563eb',
    color: '#fff',
  },
  navIcon: {
    fontSize: 16,
    width: 20,
    textAlign: 'center',
  },
  logoutBtn: {
    margin: '16px 10px 0',
    padding: '8px 12px',
    background: 'none',
    border: '1px solid #334155',
    color: '#64748b',
    fontSize: 13,
    borderRadius: 7,
    cursor: 'pointer',
  },
  main: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    minWidth: 0,
  },
  header: {
    background: '#fff',
    borderBottom: '1px solid #e2e8f0',
    padding: '16px 28px',
  },
  pageTitle: {
    margin: 0,
    fontSize: 20,
    fontWeight: 700,
    color: '#1e293b',
  },
  content: {
    flex: 1,
    padding: 28,
    overflowY: 'auto',
  },
}
