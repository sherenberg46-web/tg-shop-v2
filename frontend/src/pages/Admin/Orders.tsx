import { useEffect, useState } from 'react'
import { adminApi } from './api'

interface Order {
  id: number
  created_at: string
  status: string
  total_stars: number
  total_byn: number
  username: string | null
  first_name: string | null
  items_title: string | null
  region: string | null
}

const STATUS_LABELS: Record<string, string> = {
  pending: 'Ожидает',
  paid: 'Оплачен',
  processing: 'В обработке',
  completed: 'Выполнен',
  cancelled: 'Отменён',
}

const STATUS_COLORS: Record<string, string> = {
  pending: '#fef9c3',
  paid: '#dbeafe',
  processing: '#e0e7ff',
  completed: '#dcfce7',
  cancelled: '#fee2e2',
}

const STATUS_TEXT: Record<string, string> = {
  pending: '#854d0e',
  paid: '#1d4ed8',
  processing: '#4338ca',
  completed: '#15803d',
  cancelled: '#b91c1c',
}

export default function Orders() {
  const [orders, setOrders] = useState<Order[]>([])
  const [total, setTotal] = useState(0)
  const [totalByn, setTotalByn] = useState(0)
  const [totalStars, setTotalStars] = useState(0)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const { data } = await adminApi.get('/orders', {
        params: {
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          status: statusFilter || undefined,
          limit: 200,
        },
      })
      setOrders(data.items)
      setTotal(data.total)
      setTotalByn(data.total_byn)
      setTotalStars(data.total_stars)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleExport = async () => {
    setExporting(true)
    try {
      const params = new URLSearchParams()
      if (dateFrom) params.set('date_from', dateFrom)
      if (dateTo) params.set('date_to', dateTo)
      if (statusFilter) params.set('status', statusFilter)
      const token = localStorage.getItem('admin_token') || ''
      const resp = await fetch(`/api/v1/admin/orders/export?${params}`, {
        headers: { 'X-Admin-Token': token },
      })
      if (!resp.ok) throw new Error('Export failed')
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `orders_${dateFrom || 'all'}_${dateTo || 'all'}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(false)
    }
  }

  const handleStatusChange = async (orderId: number, status: string) => {
    await adminApi.put(`/orders/${orderId}/status`, { status })
    load()
  }

  const fmtDate = (s: string) => {
    if (!s) return '—'
    try { return new Date(s).toLocaleString('ru-RU') } catch { return s }
  }

  return (
    <div>
      {/* Filters */}
      <div style={st.filterRow}>
        <div style={st.filterGroup}>
          <label style={st.filterLabel}>С</label>
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} style={st.dateInput} />
        </div>
        <div style={st.filterGroup}>
          <label style={st.filterLabel}>По</label>
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} style={st.dateInput} />
        </div>
        <div style={st.filterGroup}>
          <label style={st.filterLabel}>Статус</label>
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={st.dateInput}>
            <option value="">Все</option>
            {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <button onClick={load} style={st.btnPrimary}>Применить</button>
        <button onClick={handleExport} disabled={exporting} style={st.btnExport}>
          {exporting ? '…' : '⬇ Excel'}
        </button>
      </div>

      {/* Summary */}
      <div style={st.summary}>
        <div style={st.summaryCard}>
          <div style={st.summaryVal}>{total}</div>
          <div style={st.summaryLabel}>Заказов</div>
        </div>
        <div style={st.summaryCard}>
          <div style={st.summaryVal}>{Math.round(totalByn)} BYN</div>
          <div style={st.summaryLabel}>Выручка</div>
        </div>
        <div style={st.summaryCard}>
          <div style={st.summaryVal}>{totalStars} ⭐</div>
          <div style={st.summaryLabel}>Звёзды</div>
        </div>
      </div>

      {loading ? <div style={st.loading}>Загрузка…</div> : (
        <div style={st.tableWrap}>
          <table style={st.table}>
            <thead>
              <tr style={st.thead}>
                <th style={st.th}>ID</th>
                <th style={st.th}>Дата</th>
                <th style={st.th}>Покупатель</th>
                <th style={st.th}>Товары</th>
                <th style={st.th}>Регион</th>
                <th style={st.th}>BYN</th>
                <th style={st.th}>⭐</th>
                <th style={st.th}>Статус</th>
              </tr>
            </thead>
            <tbody>
              {orders.length === 0 && (
                <tr><td colSpan={8} style={{ textAlign: 'center', padding: 32, color: '#94a3b8' }}>Нет заказов</td></tr>
              )}
              {orders.map(o => (
                <tr key={o.id} style={st.tr}>
                  <td style={st.td}>#{o.id}</td>
                  <td style={st.td}>{fmtDate(o.created_at)}</td>
                  <td style={st.td}>
                    <div style={{ fontWeight: 600 }}>{o.first_name || '—'}</div>
                    <div style={{ color: '#64748b', fontSize: 12 }}>{o.username ? `@${o.username}` : ''}</div>
                  </td>
                  <td style={{ ...st.td, maxWidth: 220 }}>
                    <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {o.items_title || '—'}
                    </div>
                  </td>
                  <td style={st.td}>
                    <span style={{ ...st.regionBadge, ...regionStyle(o.region) }}>{o.region || '—'}</span>
                  </td>
                  <td style={{ ...st.td, fontWeight: 600 }}>{o.total_byn} BYN</td>
                  <td style={st.td}>{o.total_stars}</td>
                  <td style={st.td}>
                    <select
                      value={o.status}
                      onChange={e => handleStatusChange(o.id, e.target.value)}
                      style={{
                        background: STATUS_COLORS[o.status] || '#f1f5f9',
                        color: STATUS_TEXT[o.status] || '#374151',
                        border: 'none',
                        borderRadius: 12,
                        padding: '3px 8px',
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function regionStyle(region: string | null): React.CSSProperties {
  const map: Record<string, string> = { UA: '#fef9c3', TR: '#dbeafe', IN: '#fce7f3', PL: '#dcfce7' }
  return { background: map[region || ''] || '#f1f5f9' }
}

const st: Record<string, React.CSSProperties> = {
  filterRow: { display: 'flex', alignItems: 'flex-end', gap: 10, marginBottom: 18, flexWrap: 'wrap' },
  filterGroup: { display: 'flex', flexDirection: 'column', gap: 4 },
  filterLabel: { fontSize: 11, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.04em' },
  dateInput: { padding: '7px 10px', border: '1px solid #cbd5e1', borderRadius: 7, fontSize: 13 },
  btnPrimary: { padding: '8px 18px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 7, fontSize: 14, fontWeight: 600, cursor: 'pointer', alignSelf: 'flex-end' },
  btnExport: { padding: '8px 14px', background: '#059669', color: '#fff', border: 'none', borderRadius: 7, fontSize: 14, fontWeight: 600, cursor: 'pointer', alignSelf: 'flex-end' },
  summary: { display: 'flex', gap: 14, marginBottom: 18, flexWrap: 'wrap' },
  summaryCard: { background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10, padding: '14px 24px', minWidth: 120 },
  summaryVal: { fontSize: 22, fontWeight: 700, color: '#1e293b' },
  summaryLabel: { fontSize: 12, color: '#64748b', marginTop: 2 },
  loading: { textAlign: 'center', color: '#94a3b8', padding: 40 },
  tableWrap: { overflowX: 'auto' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 13 },
  thead: { background: '#f8fafc' },
  th: { padding: '10px 12px', textAlign: 'left', fontWeight: 600, color: '#374151', borderBottom: '2px solid #e2e8f0', whiteSpace: 'nowrap' },
  tr: { borderBottom: '1px solid #f1f5f9' },
  td: { padding: '10px 12px', verticalAlign: 'middle', color: '#1e293b' },
  regionBadge: { padding: '2px 8px', borderRadius: 10, fontSize: 12, fontWeight: 600 },
}
