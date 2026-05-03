import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '@/api'
import { useStore } from '@/store'
import { formatBYN } from '@/utils/price'

export default function Cart() {
  const { cartItems, setCartItems, region, userId } = useStore()
  const navigate = useNavigate()
  const [loading,    setLoading]    = useState(false)
  const [hasAccount, setHasAccount] = useState<boolean | null>(null)
  const [email,      setEmail]      = useState('')
  const [password,   setPassword]   = useState('')
  const [promo,      setPromo]      = useState('')
  const [agreed,     setAgreed]     = useState(false)

  const fetchCart = async () => {
    if (!userId) return
    const res = await api.get('/cart')
    setCartItems(res.data)
  }

  useEffect(() => { fetchCart() }, [userId])

  // price from API is already in BYN (converted server-side)
  const itemByn = (price: number | null, qty: number) =>
    price != null ? price * qty : 0

  const totalByn = cartItems.reduce(
    (sum, i) => sum + itemByn(i.price, i.quantity),
    0
  )

  const update = async (itemId: number, qty: number) => {
    await api.put(`/cart/${itemId}`, null, { params: { quantity: qty } })
    fetchCart()
  }

  const remove = async (itemId: number) => {
    await api.delete(`/cart/${itemId}`)
    fetchCart()
  }

  const checkout = async () => {
    if (!userId || !cartItems.length || !agreed) return
    if (hasAccount === null) {
      alert('Выберите тип аккаунта PlayStation')
      return
    }
    if (hasAccount === true && !email.trim()) {
      alert('Введите email от PS аккаунта')
      return
    }
    setLoading(true)
    try {
      const tgUser = window.Telegram?.WebApp?.initDataUnsafe?.user
      const res = await api.post('/orders', {
        user_id: userId,
        username:   tgUser?.username   ?? null,
        first_name: tgUser?.first_name ?? null,
        region,
        items: cartItems.map(i => ({ product_id: i.product_id, quantity: i.quantity, region })),
        account_type: hasAccount ? 'my_account' : 'no_account',
        ps_email: hasAccount ? email.trim() : null,
        ps_password: hasAccount ? password : null,
      })
      await api.delete('/cart')
      setCartItems([])
      navigate('/order-success', {
        replace: true,
        state: { orderId: res.data.id, totalByn: res.data.total_byn },
      })
    } finally {
      setLoading(false)
    }
  }

  if (!cartItems.length) {
    return (
      <main className="page">
        <div className="empty-state">
          <div className="empty-state__icon">🛒</div>
          <p className="empty-state__title">Корзина пуста</p>
          <p className="empty-state__sub">Добавьте товары<br/>из каталога магазина</p>
        </div>
      </main>
    )
  }

  return (
    <main className="page">
      {/* Header */}
      <div className="cart-header">
        <h1 style={{ fontSize: 22, fontWeight: 900 }}>Корзина</h1>
        <span className="cart-total-badge">{formatBYN(totalByn)}</span>
      </div>

      {/* Items */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 24 }}>
        {cartItems.map(item => {
          const lineByn = itemByn(item.price, item.quantity)
          return (
            <div key={item.id} className="cart-item">
              <img
                className="cart-item__img"
                src={item.image_url ?? 'https://placehold.co/60x80/1a1d24/fff?text=?'}
                alt={item.title}
              />
              <div className="cart-item__info">
                <p className="cart-item__title">{item.title}</p>
                <p className="cart-item__platform">{item.region} · {item.quantity} шт.</p>
                <p className="cart-item__price">{formatBYN(lineByn)}</p>
                {/* Qty controls */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 6 }}>
                  <button
                    onClick={() => update(item.id, item.quantity - 1)}
                    style={{
                      width: 26, height: 26, borderRadius: '50%',
                      background: 'var(--bg-input)', border: '1.5px solid var(--border)',
                      fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}
                  >−</button>
                  <span style={{ fontSize: 14, fontWeight: 700, minWidth: 16, textAlign: 'center' }}>
                    {item.quantity}
                  </span>
                  <button
                    onClick={() => update(item.id, item.quantity + 1)}
                    style={{
                      width: 26, height: 26, borderRadius: '50%',
                      background: 'var(--bg-input)', border: '1.5px solid var(--border)',
                      fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}
                  >+</button>
                </div>
              </div>
              <button className="cart-item__delete" onClick={() => remove(item.id)}>
                <IconTrash />
              </button>
            </div>
          )
        })}
      </div>

      {/* Account section */}
      <p className="section-divider"><span>🎮</span> Аккаунт PlayStation</p>

      <div className="account-tabs">
        <button
          className={`account-tab ${hasAccount === true ? 'active' : ''}`}
          onClick={() => setHasAccount(true)}
        >
          На мой аккаунт
        </button>
        <button
          className={`account-tab ${hasAccount === false ? 'active' : ''}`}
          onClick={() => setHasAccount(false)}
        >
          У меня нет аккаунта
        </button>
      </div>

      {hasAccount === true && (
        <>
          <div className="form-group">
            <label className="form-label">E-mail от PS аккаунта</label>
            <input
              className="form-input"
              type="email"
              placeholder="example@mail.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              autoComplete="email"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Пароль от аккаунта PS</label>
            <input
              className="form-input"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>
        </>
      )}

      {hasAccount === false && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '14px 16px',
          background: 'rgba(0,212,170,.08)',
          border: '1.5px solid rgba(0,212,170,.25)',
          borderRadius: 'var(--radius-md)',
          marginBottom: 16,
          fontSize: 14,
          fontWeight: 500,
          color: 'var(--text-primary)',
        }}>
          <span style={{ fontSize: 22, flexShrink: 0 }}>✅</span>
          <span>Менеджер создаст для вас аккаунт <b>бесплатно</b></span>
        </div>
      )}

      {/* Promo */}
      <p className="section-divider"><span>🏷️</span> Промокод</p>
      <div className="promo-wrap">
        <input
          className="form-input"
          style={{ flex: 1 }}
          type="text"
          placeholder="Введите промокод"
          value={promo}
          onChange={e => setPromo(e.target.value)}
        />
        <button className="promo-btn">Применить</button>
      </div>

      {/* Order summary */}
      <div style={{
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius-md)',
        padding: '14px 16px',
        marginBottom: 16,
        boxShadow: 'var(--shadow-card)',
      }}>
        {cartItems.map(item => (
          <div key={item.id} style={{
            display: 'flex', justifyContent: 'space-between',
            fontSize: 13, marginBottom: 8, color: 'var(--text-secondary)',
          }}>
            <span style={{
              flex: 1, overflow: 'hidden',
              textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginRight: 8,
            }}>
              {item.title}
            </span>
            <span style={{ fontWeight: 600, flexShrink: 0 }}>
              {formatBYN(itemByn(item.price, item.quantity))}
            </span>
          </div>
        ))}
        <div style={{
          borderTop: '1px solid var(--border)',
          paddingTop: 10, marginTop: 4,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ fontWeight: 800, fontSize: 15 }}>Итого</span>
          <span style={{ fontWeight: 900, fontSize: 18 }}>{formatBYN(totalByn)}</span>
        </div>
      </div>

      {/* Agreement */}
      <div className="checkbox-row">
        <input
          type="checkbox"
          id="agree"
          checked={agreed}
          onChange={e => setAgreed(e.target.checked)}
        />
        <label htmlFor="agree">
          Я согласен с условиями <a href="#">публичной оферты</a> и политикой
          конфиденциальности
        </label>
      </div>

      {/* Pay button */}
      <button
        className="btn-grad"
        onClick={checkout}
        disabled={loading || !agreed || !cartItems.length || hasAccount === null}
      >
        {loading ? 'Обработка…' : 'Оформить заказ'}
      </button>
    </main>
  )
}

function IconTrash() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="3 6 5 6 21 6"/>
      <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>
      <path d="M10 11v6M14 11v6"/>
      <path d="M9 6V4h6v2"/>
    </svg>
  )
}
