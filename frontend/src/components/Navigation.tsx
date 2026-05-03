import { useLocation, useNavigate } from 'react-router-dom'
import { useStore } from '@/store'

export default function Navigation() {
  const { pathname } = useLocation()
  const nav = useNavigate()
  const cartItems = useStore(s => s.cartItems)

  const items = [
    { path: '/',           label: 'Главная',  icon: <IconHome /> },
    { path: '/favourites', label: 'Избранное', icon: <IconHeart /> },
    { path: '/cart',       label: 'Корзина',  icon: <IconCart />, badge: cartItems.length },
    { path: '/profile',    label: 'Профиль',  icon: <IconUser /> },
  ]

  return (
    <nav className="nav-bar">
      {items.map(({ path, label, icon, badge }) => (
        <button
          key={path}
          className={`nav-item ${pathname === path ? 'active' : ''}`}
          onClick={() => nav(path)}
        >
          <div style={{ position: 'relative' }}>
            {icon}
            {badge != null && badge > 0 && (
              <span className="nav-badge">{badge > 99 ? '99+' : badge}</span>
            )}
          </div>
          {label}
        </button>
      ))}
    </nav>
  )
}

function IconHome() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1H5a1 1 0 01-1-1V9.5z"/>
      <path d="M9 21V12h6v9"/>
    </svg>
  )
}

function IconHeart() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/>
    </svg>
  )
}

function IconCart() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <circle cx="9" cy="21" r="1"/>
      <circle cx="20" cy="21" r="1"/>
      <path d="M1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6"/>
    </svg>
  )
}

function IconUser() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/>
      <circle cx="12" cy="7" r="4"/>
    </svg>
  )
}
