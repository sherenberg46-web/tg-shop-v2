import { useLocation, useNavigate } from 'react-router-dom'
import { formatBYN } from '@/utils/price'

interface OrderState {
  orderId: number
  totalByn: number
}

export default function OrderSuccess() {
  const location = useLocation()
  const navigate = useNavigate()
  const state = location.state as OrderState | null

  return (
    <main className="page page--no-header" style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', minHeight: '100vh', textAlign: 'center', padding: '0 24px',
    }}>
      <div style={{
        width: 88, height: 88, borderRadius: '50%',
        background: 'linear-gradient(135deg, #00d4aa 0%, #00a8ff 100%)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 44, marginBottom: 24,
        boxShadow: '0 8px 32px rgba(0,212,170,.35)',
      }}>
        ✅
      </div>

      <h1 style={{ fontSize: 24, fontWeight: 900, marginBottom: 12 }}>
        Заказ принят!
      </h1>

      {state?.orderId && (
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 8 }}>
          Заказ <b style={{ color: 'var(--text-primary)' }}>#{state.orderId}</b>
        </p>
      )}

      <p style={{
        fontSize: 15, color: 'var(--text-secondary)',
        lineHeight: 1.6, marginBottom: 32, maxWidth: 280,
      }}>
        Менеджер свяжется с вами в ближайшее время для подтверждения и оплаты.
      </p>

      {state?.totalByn != null && state.totalByn > 0 && (
        <div style={{
          background: 'var(--bg-card)', borderRadius: 'var(--radius-md)',
          padding: '14px 24px', marginBottom: 32, boxShadow: 'var(--shadow-card)',
          fontSize: 15, fontWeight: 700,
        }}>
          Сумма заказа: <b style={{ color: '#00d4aa' }}>{formatBYN(state.totalByn)}</b>
        </div>
      )}

      <button
        className="btn-grad"
        style={{ width: '100%', maxWidth: 300 }}
        onClick={() => navigate('/', { replace: true })}
      >
        Вернуться в магазин
      </button>
    </main>
  )
}
