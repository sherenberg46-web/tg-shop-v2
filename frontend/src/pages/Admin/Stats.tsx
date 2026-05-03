import { useEffect, useState } from 'react'
import { adminApi } from './api'

interface Stats {
  orders: { today: number; week: number; month: number }
  revenue_byn: { today: number; week: number; month: number }
  revenue_stars: { today: number; week: number; month: number }
  top_products: Array<{ title: string; cnt: number; revenue_byn: number; region: string }>
  by_region: Array<{ region: string; orders_count: number; revenue_byn: number }>
}

const REGION_FLAGS: Record<string, string> = { UA: '🇺🇦', TR: '🇹🇷', IN: '🇮🇳', PL: '🇵🇱' }

export default function Stats() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    adminApi.get('/stats')
      .then(r => setStats(r.data))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={s.loading}>Загрузка статистики…</div>
  if (!stats) return <div style={s.loading}>Ошибка загрузки</div>

  const periods: Array<{ key: keyof Stats['orders']; label: string }> = [
    { key: 'today', label: 'Сегодня' },
    { key: 'week', label: '7 дней' },
    { key: 'month', label: '30 дней' },
  ]

  return (
    <div>
      {/* Period metrics */}
      <h3 style={s.sectionTitle}>Продажи по периодам</h3>
      <div style={s.metricsGrid}>
        {periods.map(({ key, label }) => (
          <div key={key} style={s.metricCard}>
            <div style={s.metricPeriod}>{label}</div>
            <div style={s.metricRow}>
              <span style={s.metricIcon}>🛒</span>
              <div>
                <div style={s.metricVal}>{stats.orders[key]}</div>
                <div style={s.metricLabel}>заказов</div>
              </div>
            </div>
            <div style={s.metricRow}>
              <span style={s.metricIcon}>💰</span>
              <div>
                <div style={s.metricVal}>{stats.revenue_byn[key]} BYN</div>
                <div style={s.metricLabel}>{stats.revenue_stars[key]} ⭐</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Revenue by region */}
      <h3 style={s.sectionTitle}>Выручка по регионам (30 дней)</h3>
      {stats.by_region.length === 0 ? (
        <div style={s.empty}>Нет данных</div>
      ) : (
        <div style={s.regionGrid}>
          {stats.by_region.map(r => (
            <div key={r.region} style={s.regionCard}>
              <div style={s.regionFlag}>{REGION_FLAGS[r.region] || '🌍'} {r.region}</div>
              <div style={s.regionStat}>
                <span style={s.regionVal}>{r.orders_count}</span>
                <span style={s.regionLabel}>заказов</span>
              </div>
              <div style={s.regionStat}>
                <span style={s.regionVal}>{r.revenue_byn} BYN</span>
                <span style={s.regionLabel}>выручка</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Top products */}
      <h3 style={s.sectionTitle}>Топ товаров (30 дней)</h3>
      {stats.top_products.length === 0 ? (
        <div style={s.empty}>Нет данных</div>
      ) : (
        <div style={s.tableWrap}>
          <table style={s.table}>
            <thead>
              <tr style={s.thead}>
                <th style={s.th}>#</th>
                <th style={s.th}>Товар</th>
                <th style={s.th}>Регион</th>
                <th style={s.th}>Продано</th>
                <th style={s.th}>Выручка</th>
              </tr>
            </thead>
            <tbody>
              {stats.top_products.map((p, i) => (
                <tr key={i} style={s.tr}>
                  <td style={{ ...s.td, color: i < 3 ? '#f59e0b' : '#94a3b8', fontWeight: 700 }}>
                    {i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1}
                  </td>
                  <td style={{ ...s.td, maxWidth: 280 }}>
                    <span style={s.productTitle}>{p.title}</span>
                  </td>
                  <td style={s.td}>{REGION_FLAGS[p.region] || ''} {p.region}</td>
                  <td style={{ ...s.td, fontWeight: 600 }}>{p.cnt} шт.</td>
                  <td style={{ ...s.td, fontWeight: 600, color: '#059669' }}>{p.revenue_byn} BYN</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

const s: Record<string, React.CSSProperties> = {
  loading: { textAlign: 'center', color: '#94a3b8', padding: 60, fontSize: 16 },
  empty: { color: '#94a3b8', padding: '20px 0', fontSize: 14 },
  sectionTitle: { fontSize: 16, fontWeight: 700, color: '#1e293b', margin: '24px 0 14px' },
  metricsGrid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 8 },
  metricCard: { background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: '18px 20px', boxShadow: '0 1px 4px rgba(0,0,0,0.05)' },
  metricPeriod: { fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 },
  metricRow: { display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 },
  metricIcon: { fontSize: 20 },
  metricVal: { fontSize: 20, fontWeight: 700, color: '#1e293b', lineHeight: 1 },
  metricLabel: { fontSize: 12, color: '#64748b', marginTop: 2 },
  regionGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12, marginBottom: 8 },
  regionCard: { background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10, padding: '14px 16px' },
  regionFlag: { fontSize: 15, fontWeight: 700, color: '#1e293b', marginBottom: 10 },
  regionStat: { display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 4 },
  regionVal: { fontSize: 17, fontWeight: 700, color: '#1e293b' },
  regionLabel: { fontSize: 12, color: '#64748b' },
  tableWrap: { overflowX: 'auto' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 13 },
  thead: { background: '#f8fafc' },
  th: { padding: '10px 12px', textAlign: 'left', fontWeight: 600, color: '#374151', borderBottom: '2px solid #e2e8f0', whiteSpace: 'nowrap' },
  tr: { borderBottom: '1px solid #f1f5f9' },
  td: { padding: '10px 12px', verticalAlign: 'middle', color: '#1e293b' },
  productTitle: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' },
}
