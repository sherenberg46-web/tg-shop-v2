import { useState, useEffect } from 'react'
import { adminApi } from './api'

interface Settings {
  uah_rate: string
  try_rate: string
  uah_markup_500: string
  uah_markup_1000: string
  uah_markup_1500: string
  uah_markup_2000: string
  uah_markup_max: string
  try_markup_500: string
  try_markup_1000: string
  try_markup_1500: string
  try_markup_2000: string
  try_markup_max: string
}

const DEFAULTS: Settings = {
  uah_rate: '0.069',
  try_rate: '0.07',
  uah_markup_500: '70',
  uah_markup_1000: '60',
  uah_markup_1500: '50',
  uah_markup_2000: '40',
  uah_markup_max: '30',
  try_markup_500: '70',
  try_markup_1000: '60',
  try_markup_1500: '50',
  try_markup_2000: '40',
  try_markup_max: '30',
}

const MARKUP_TIERS = [
  { key: '_500',  label: 'до 500',       range: '≤ 500' },
  { key: '_1000', label: '500 – 1 000',  range: '≤ 1000' },
  { key: '_1500', label: '1 000 – 1 500',range: '≤ 1500' },
  { key: '_2000', label: '1 500 – 2 000',range: '≤ 2000' },
  { key: '_max',  label: 'свыше 2 000',  range: '> 2000' },
]

function calcByn(price: number, rate: number, markupPct: number): string {
  if (!price || !rate) return '—'
  return Math.ceil(price * rate * (1 + markupPct / 100)).toLocaleString('ru-RU') + ' BYN'
}

export default function Settings() {
  const [form, setForm] = useState<Settings>(DEFAULTS)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    setLoading(true)
    adminApi.get('/settings')
      .then(({ data }) => {
        setForm(prev => ({ ...prev, ...Object.fromEntries(
          Object.entries(data).map(([k, v]) => [k, String(v)])
        )}))
      })
      .catch(() => setErr('Не удалось загрузить настройки'))
      .finally(() => setLoading(false))
  }, [])

  const set = (key: keyof Settings, val: string) => setForm(f => ({ ...f, [key]: val }))

  const handleSave = async () => {
    setSaving(true); setErr(''); setSaved(false)
    try {
      await adminApi.put('/settings', Object.fromEntries(
        Object.entries(form).map(([k, v]) => [k, v])
      ))
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch {
      setErr('Ошибка при сохранении')
    } finally {
      setSaving(false)
    }
  }

  const uahRate = parseFloat(form.uah_rate) || 0.069
  const tryRate = parseFloat(form.try_rate) || 0.07

  if (loading) return <div style={s.loader}>Загрузка настроек...</div>

  return (
    <div style={s.wrap}>
      {err && <div style={s.error}>{err}</div>}
      {saved && <div style={s.success}>✓ Настройки сохранены! Новые цены применятся сразу.</div>}

      {/* Exchange rates */}
      <div style={s.card}>
        <h3 style={s.cardTitle}>💱 Курсы валют</h3>
        <p style={s.hint}>Базовые курсы обмена. Итоговая цена = цена × курс × (1 + наценка%)</p>
        <div style={s.rateGrid}>
          <div style={s.rateField}>
            <label style={s.label}>Курс UAH → BYN</label>
            <div style={s.rateRow}>
              <input
                style={s.rateInput}
                type="number" step="0.001" min="0"
                value={form.uah_rate}
                onChange={e => set('uah_rate', e.target.value)}
              />
              <span style={s.unit}>1 UAH = {form.uah_rate || '?'} BYN</span>
            </div>
          </div>
          <div style={s.rateField}>
            <label style={s.label}>Курс TRY → BYN</label>
            <div style={s.rateRow}>
              <input
                style={s.rateInput}
                type="number" step="0.001" min="0"
                value={form.try_rate}
                onChange={e => set('try_rate', e.target.value)}
              />
              <span style={s.unit}>1 TRY = {form.try_rate || '?'} BYN</span>
            </div>
          </div>
        </div>
      </div>

      {/* Markup tiers */}
      <div style={s.card}>
        <h3 style={s.cardTitle}>📊 Наценка по ценовым диапазонам</h3>
        <p style={s.hint}>
          Наценка применяется поверх курса. Чем дороже товар — тем меньше наценка.
          Настраивается отдельно для регионов UA и TR.
        </p>

        <div style={s.tiersGrid}>
          {/* UAH tiers */}
          <div>
            <div style={s.tierHeader}>
              <span style={s.regionBadge}>🇺🇦 UAH</span>
              <span style={s.tierHint}>Курс: {form.uah_rate} BYN/UAH</span>
            </div>
            <table style={s.table}>
              <thead>
                <tr>
                  <th style={s.th}>Диапазон цены</th>
                  <th style={s.th}>Наценка %</th>
                  <th style={s.th}>Пример (500 UAH)</th>
                </tr>
              </thead>
              <tbody>
                {MARKUP_TIERS.map(tier => {
                  const key = `uah${tier.key}` as keyof Settings
                  const pct = parseFloat(form[key]) || 0
                  const examplePrice = tier.key === '_max' ? 2500 : parseInt(tier.range.replace('≤ ', '').replace('> ', ''))
                  return (
                    <tr key={key} style={s.tr}>
                      <td style={s.td}>
                        <span style={s.tierLabel}>{tier.label}</span>
                        <span style={s.tierRange}>{tier.range} UAH</span>
                      </td>
                      <td style={s.td}>
                        <div style={s.pctRow}>
                          <input
                            style={s.pctInput}
                            type="number" min="0" max="300" step="1"
                            value={form[key]}
                            onChange={e => set(key, e.target.value)}
                          />
                          <span style={s.pct}>%</span>
                        </div>
                      </td>
                      <td style={{ ...s.td, color: '#2563eb', fontWeight: 600 }}>
                        {calcByn(examplePrice, uahRate, pct)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* TRY tiers */}
          <div>
            <div style={s.tierHeader}>
              <span style={{ ...s.regionBadge, background: '#dc2626' }}>🇹🇷 TRY</span>
              <span style={s.tierHint}>Курс: {form.try_rate} BYN/TRY</span>
            </div>
            <table style={s.table}>
              <thead>
                <tr>
                  <th style={s.th}>Диапазон цены</th>
                  <th style={s.th}>Наценка %</th>
                  <th style={s.th}>Пример</th>
                </tr>
              </thead>
              <tbody>
                {MARKUP_TIERS.map(tier => {
                  const key = `try${tier.key}` as keyof Settings
                  const pct = parseFloat(form[key]) || 0
                  const examplePrice = tier.key === '_max' ? 2500 : parseInt(tier.range.replace('≤ ', '').replace('> ', ''))
                  return (
                    <tr key={key} style={s.tr}>
                      <td style={s.td}>
                        <span style={s.tierLabel}>{tier.label}</span>
                        <span style={s.tierRange}>{tier.range} TRY</span>
                      </td>
                      <td style={s.td}>
                        <div style={s.pctRow}>
                          <input
                            style={s.pctInput}
                            type="number" min="0" max="300" step="1"
                            value={form[key]}
                            onChange={e => set(key, e.target.value)}
                          />
                          <span style={s.pct}>%</span>
                        </div>
                      </td>
                      <td style={{ ...s.td, color: '#2563eb', fontWeight: 600 }}>
                        {calcByn(examplePrice, tryRate, pct)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Live calculator */}
      <Calculator uahRate={uahRate} tryRate={tryRate} form={form} />

      <div style={s.footer}>
        <button style={s.btnPrimary} onClick={handleSave} disabled={saving}>
          {saving ? 'Сохранение...' : '💾 Сохранить настройки'}
        </button>
        <p style={s.footerHint}>Изменения вступят в силу немедленно для всех новых запросов цен.</p>
      </div>
    </div>
  )
}

function Calculator({ uahRate, tryRate, form }: { uahRate: number; tryRate: number; form: Settings }) {
  const [priceUah, setPriceUah] = useState('1000')
  const [priceTry, setPriceTry] = useState('800')

  const calcFor = (price: number, rate: number, prefix: 'uah' | 'try') => {
    const tiers: [number, string][] = [
      [500, `${prefix}_markup_500`],
      [1000, `${prefix}_markup_1000`],
      [1500, `${prefix}_markup_1500`],
      [2000, `${prefix}_markup_2000`],
      [Infinity, `${prefix}_markup_max`],
    ]
    const key = tiers.find(([t]) => price <= t)![1]
    const pct = parseFloat((form as any)[key]) || 0
    return Math.ceil(price * rate * (1 + pct / 100)).toLocaleString('ru-RU') + ' BYN'
  }

  return (
    <div style={s.card}>
      <h3 style={s.cardTitle}>🧮 Калькулятор цены</h3>
      <div style={s.calcGrid}>
        <div style={s.calcField}>
          <label style={s.label}>Цена в UAH</label>
          <input style={s.rateInput} type="number" value={priceUah} onChange={e => setPriceUah(e.target.value)} />
          <div style={s.calcResult}>
            → <strong>{calcFor(parseFloat(priceUah) || 0, uahRate, 'uah')}</strong>
          </div>
        </div>
        <div style={s.calcField}>
          <label style={s.label}>Цена в TRY</label>
          <input style={s.rateInput} type="number" value={priceTry} onChange={e => setPriceTry(e.target.value)} />
          <div style={s.calcResult}>
            → <strong>{calcFor(parseFloat(priceTry) || 0, tryRate, 'try')}</strong>
          </div>
        </div>
      </div>
    </div>
  )
}

const s: Record<string, React.CSSProperties> = {
  wrap: { display: 'flex', flexDirection: 'column', gap: 20 },
  loader: { padding: 40, textAlign: 'center', color: '#64748b' },
  error: { background: '#fee2e2', color: '#b91c1c', padding: '12px 16px', borderRadius: 8, fontSize: 14 },
  success: { background: '#dcfce7', color: '#15803d', padding: '12px 16px', borderRadius: 8, fontSize: 14, fontWeight: 600 },
  card: { background: '#fff', borderRadius: 12, padding: 24, boxShadow: '0 1px 3px rgba(0,0,0,.06)' },
  cardTitle: { margin: '0 0 6px', fontSize: 16, fontWeight: 700, color: '#1e293b' },
  hint: { margin: '0 0 20px', fontSize: 13, color: '#64748b', lineHeight: 1.6 },
  rateGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 },
  rateField: { display: 'flex', flexDirection: 'column', gap: 6 },
  rateRow: { display: 'flex', alignItems: 'center', gap: 10 },
  rateInput: { width: 120, padding: '9px 12px', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 16, fontWeight: 700, outline: 'none' },
  unit: { fontSize: 13, color: '#64748b' },
  label: { fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em' },
  tiersGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 },
  tierHeader: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 },
  regionBadge: { background: '#1d4ed8', color: '#fff', fontSize: 12, fontWeight: 700, padding: '3px 10px', borderRadius: 20 },
  tierHint: { fontSize: 12, color: '#64748b' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 13 },
  th: { padding: '8px 10px', textAlign: 'left', fontSize: 11, color: '#64748b', fontWeight: 700, textTransform: 'uppercase', borderBottom: '2px solid #e2e8f0', letterSpacing: '0.05em' },
  tr: { borderBottom: '1px solid #f1f5f9' },
  td: { padding: '10px 10px', verticalAlign: 'middle' },
  tierLabel: { display: 'block', fontSize: 13, fontWeight: 600, color: '#1e293b' },
  tierRange: { display: 'block', fontSize: 11, color: '#94a3b8', marginTop: 2 },
  pctRow: { display: 'flex', alignItems: 'center', gap: 4 },
  pctInput: { width: 64, padding: '6px 8px', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 15, fontWeight: 700, textAlign: 'center', outline: 'none' },
  pct: { fontSize: 14, color: '#64748b', fontWeight: 600 },
  calcGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 },
  calcField: { display: 'flex', flexDirection: 'column', gap: 8 },
  calcResult: { fontSize: 16, color: '#1e293b' },
  footer: { display: 'flex', flexDirection: 'column', gap: 8 },
  btnPrimary: { padding: '12px 28px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 9, fontSize: 15, fontWeight: 700, cursor: 'pointer', width: 'fit-content' },
  footerHint: { fontSize: 12, color: '#94a3b8', margin: 0 },
}
