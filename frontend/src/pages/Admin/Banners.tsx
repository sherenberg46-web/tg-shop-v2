import { useState, useEffect, useRef } from 'react'
import { adminApi } from './api'

interface Banner {
  id: number
  title: string
  subtitle: string
  image_url: string
  link_ua: string
  link_tr: string
  link_url: string
  gradient: string
  sort_order: number
  is_active: number
  collection_slug: string
}

interface Collection {
  id: number
  title: string
  slug: string
}

const EMPTY: Omit<Banner, 'id'> = {
  title: '',
  subtitle: '',
  image_url: '',
  link_ua: '',
  link_tr: '',
  link_url: '',
  gradient: '',
  sort_order: 0,
  is_active: 1,
  collection_slug: '',
}

const GRADIENT_PRESETS = [
  { label: 'Красный', value: 'linear-gradient(135deg, #1a0005 0%, #6b0010 35%, #c0001a 65%, #ff6b00 100%)' },
  { label: 'Синий', value: 'linear-gradient(135deg, #001a3a 0%, #003380 40%, #0055cc 70%, #0088ff 100%)' },
  { label: 'Фиолетовый', value: 'linear-gradient(135deg, #1a0030 0%, #4a0080 40%, #7c00d4 70%, #c040ff 100%)' },
  { label: 'Зелёный', value: 'linear-gradient(135deg, #001a00 0%, #004d00 40%, #008000 70%, #00cc44 100%)' },
  { label: 'Тёмный', value: 'linear-gradient(135deg, #0d0d0d 0%, #1a1a1a 50%, #2d2d2d 100%)' },
  { label: 'Золотой', value: 'linear-gradient(135deg, #2a1500 0%, #7a3800 40%, #c97400 70%, #ffd700 100%)' },
]

export default function Banners() {
  const [banners, setBanners] = useState<Banner[]>([])
  const [collections, setCollections] = useState<Collection[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editBanner, setEditBanner] = useState<Banner | null>(null)
  const [form, setForm] = useState<Omit<Banner, 'id'>>(EMPTY)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = async () => {
    setLoading(true)
    try {
      const [bannersRes, collectionsRes] = await Promise.all([
        adminApi.get('/banners'),
        adminApi.get('/collections'),
      ])
      setBanners(bannersRes.data)
      setCollections(collectionsRes.data)
    } catch {
      setErr('Не удалось загрузить баннеры')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const openAdd = () => {
    setEditBanner(null)
    setForm(EMPTY)
    setShowForm(true)
  }

  const openEdit = (b: Banner) => {
    setEditBanner(b)
    setForm({
      title: b.title, subtitle: b.subtitle, image_url: b.image_url,
      link_ua: b.link_ua, link_tr: b.link_tr, link_url: b.link_url,
      gradient: b.gradient, sort_order: b.sort_order, is_active: b.is_active,
      collection_slug: b.collection_slug || '',
    })
    setShowForm(true)
  }

  const handleSave = async () => {
    setSaving(true)
    setErr('')
    try {
      if (editBanner) {
        await adminApi.put(`/banners/${editBanner.id}`, form)
      } else {
        await adminApi.post('/banners', form)
      }
      setShowForm(false)
      await load()
    } catch {
      setErr('Ошибка при сохранении баннера')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить баннер?')) return
    try {
      await adminApi.delete(`/banners/${id}`)
      await load()
    } catch {
      setErr('Ошибка при удалении')
    }
  }

  const toggleActive = async (b: Banner) => {
    try {
      await adminApi.put(`/banners/${b.id}`, { ...b, is_active: b.is_active ? 0 : 1 })
      await load()
    } catch {
      setErr('Ошибка при обновлении')
    }
  }

  // Upload image from local computer
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const { data } = await adminApi.post('/upload', fd)
      setForm(f => ({ ...f, image_url: data.url }))
    } catch {
      setErr('Ошибка загрузки изображения')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const set = (k: keyof typeof form, v: string | number) => setForm(f => ({ ...f, [k]: v }))

  if (loading) return <div style={s.loader}>Загрузка...</div>

  return (
    <div style={s.wrap}>
      {err && <div style={s.error}>{err}<button onClick={() => setErr('')} style={s.errClose}>✕</button></div>}

      <div style={s.toolbar}>
        <span style={s.count}>{banners.length} баннеров</span>
        <button style={s.btnPrimary} onClick={openAdd}>+ Добавить баннер</button>
      </div>

      {/* Modal form */}
      {showForm && (
        <div style={s.overlay} onClick={e => e.target === e.currentTarget && setShowForm(false)}>
          <div style={s.modal}>
            <div style={s.modalHeader}>
              <span>{editBanner ? 'Редактировать баннер' : 'Новый баннер'}</span>
              <button onClick={() => setShowForm(false)} style={s.closeBtn}>✕</button>
            </div>

            <div style={s.modalBody}>
              {/* Image */}
              <label style={s.label}>Изображение</label>
              <div style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
                <input
                  style={{ ...s.input, marginBottom: 0, flex: 1 }}
                  value={form.image_url}
                  onChange={e => set('image_url', e.target.value)}
                  placeholder="https://... или загрузи с компьютера →"
                />
                <button
                  style={s.btnUpload}
                  onClick={() => fileRef.current?.click()}
                  disabled={uploading}
                  title="Загрузить с компьютера"
                >
                  {uploading ? '⏳' : '📁 Файл'}
                </button>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  style={{ display: 'none' }}
                  onChange={handleFileUpload}
                />
              </div>
              <p style={s.hint}>Поддерживаются: jpg, png, webp, gif. Файл сохранится на сервере.</p>

              {form.image_url && (
                <img
                  src={form.image_url}
                  alt="preview"
                  style={s.preview}
                  onError={e => (e.currentTarget.style.display = 'none')}
                />
              )}

              {/* Gradient */}
              <label style={s.label}>Фоновый градиент</label>
              <div style={s.presetRow}>
                {GRADIENT_PRESETS.map(p => (
                  <button
                    key={p.value}
                    title={p.label}
                    onClick={() => set('gradient', p.value)}
                    style={{
                      ...s.presetBtn,
                      background: p.value,
                      outline: form.gradient === p.value ? '2px solid #2563eb' : 'none',
                    }}
                  />
                ))}
                <button
                  title="Сбросить (использовать изображение)"
                  onClick={() => set('gradient', '')}
                  style={{ ...s.presetBtn, background: '#f1f5f9', color: '#64748b', fontSize: 14 }}
                >✕</button>
              </div>
              <input
                style={s.input}
                value={form.gradient}
                onChange={e => set('gradient', e.target.value)}
                placeholder="linear-gradient(...) — опционально, если есть картинка"
              />

              {/* Title / Subtitle */}
              <div style={s.row2}>
                <div>
                  <label style={s.label}>Заголовок</label>
                  <input style={s.input} value={form.title} onChange={e => set('title', e.target.value)} placeholder="Заголовок на баннере" />
                </div>
                <div>
                  <label style={s.label}>Подзаголовок</label>
                  <input style={s.input} value={form.subtitle} onChange={e => set('subtitle', e.target.value)} placeholder="Дополнительный текст" />
                </div>
              </div>

              {/* Links */}
              {/* Collection link */}
              <label style={s.label}>Ссылка на коллекцию (приоритет над ссылками ниже)</label>
              <select
                style={{ ...s.input, background: '#fff' }}
                value={form.collection_slug}
                onChange={e => set('collection_slug', e.target.value)}
              >
                <option value="">— Не выбрана —</option>
                {collections.map(c => (
                  <option key={c.id} value={c.slug}>{c.title} ({c.slug})</option>
                ))}
              </select>
              {form.collection_slug && (
                <p style={s.hint}>При нажатии откроется /collection/{form.collection_slug}</p>
              )}

              <label style={s.label}>Ссылка для региона UA</label>
              <input style={s.input} value={form.link_ua} onChange={e => set('link_ua', e.target.value)} placeholder="/sale или https://..." />

              <label style={s.label}>Ссылка для региона TR</label>
              <input style={s.input} value={form.link_tr} onChange={e => set('link_tr', e.target.value)} placeholder="/sale/big-games или https://..." />

              <label style={s.label}>Ссылка (общая, если не указаны выше)</label>
              <input style={s.input} value={form.link_url} onChange={e => set('link_url', e.target.value)} placeholder="Запасная ссылка" />

              {/* Order + Active */}
              <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                <div style={{ flex: 1 }}>
                  <label style={s.label}>Порядок сортировки</label>
                  <input style={s.input} type="number" value={form.sort_order} onChange={e => set('sort_order', Number(e.target.value))} />
                </div>
                <label style={s.checkRow}>
                  <input type="checkbox" checked={!!form.is_active} onChange={e => set('is_active', e.target.checked ? 1 : 0)} />
                  <span style={{ fontSize: 14 }}>Активен</span>
                </label>
              </div>
            </div>

            <div style={s.modalFooter}>
              <button style={s.btnSecondary} onClick={() => setShowForm(false)}>Отмена</button>
              <button style={s.btnPrimary} onClick={handleSave} disabled={saving}>
                {saving ? 'Сохранение...' : 'Сохранить'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Banners list */}
      {banners.length === 0 ? (
        <div style={s.empty}>Баннеров пока нет. Нажмите «+ Добавить баннер».</div>
      ) : (
        <div style={s.grid}>
          {banners.map(b => (
            <div key={b.id} style={{ ...s.card, opacity: b.is_active ? 1 : 0.55 }}>
              {/* Preview */}
              <div style={{
                height: 120, overflow: 'hidden', position: 'relative',
                background: b.gradient || '#1e293b',
              }}>
                {b.image_url && (
                  <img
                    src={b.image_url}
                    alt={b.title}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    onError={e => (e.currentTarget.style.display = 'none')}
                  />
                )}
                <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(to right, rgba(0,0,0,.6) 40%, transparent 100%)' }} />
                <div style={{ position: 'absolute', bottom: 8, left: 10, right: 10 }}>
                  {b.title && <p style={{ color: '#fff', fontSize: 13, fontWeight: 700, margin: 0, textShadow: '0 1px 4px rgba(0,0,0,.8)' }}>{b.title}</p>}
                  {b.subtitle && <p style={{ color: 'rgba(255,255,255,.8)', fontSize: 11, margin: '2px 0 0' }}>{b.subtitle}</p>}
                </div>
              </div>

              <div style={s.cardBody}>
                {b.link_ua && <div style={s.linkRow}><span style={s.linkBadge}>UA</span> {b.link_ua}</div>}
                {b.link_tr && <div style={s.linkRow}><span style={{ ...s.linkBadge, background: '#dc2626' }}>TR</span> {b.link_tr}</div>}
                {b.link_url && !b.link_ua && !b.link_tr && <div style={s.linkRow}>🔗 {b.link_url}</div>}

                <div style={s.cardMeta}>
                  <span style={{ ...s.badge, background: b.is_active ? '#dcfce7' : '#fee2e2', color: b.is_active ? '#15803d' : '#b91c1c' }}>
                    {b.is_active ? 'Активен' : 'Скрыт'}
                  </span>
                  <span style={s.badgeGray}>#{b.sort_order}</span>
                </div>

                <div style={s.cardActions}>
                  <button style={s.btnSm} onClick={() => openEdit(b)}>✏️ Изменить</button>
                  <button style={s.btnSm} onClick={() => toggleActive(b)}>
                    {b.is_active ? '🙈 Скрыть' : '👁 Показать'}
                  </button>
                  <button style={s.btnSmDanger} onClick={() => handleDelete(b.id)}>🗑 Удалить</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const s: Record<string, React.CSSProperties> = {
  wrap: { display: 'flex', flexDirection: 'column', gap: 20 },
  loader: { padding: 40, textAlign: 'center', color: '#64748b' },
  error: { background: '#fee2e2', color: '#b91c1c', padding: '10px 16px', borderRadius: 8, fontSize: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  errClose: { background: 'none', border: 'none', cursor: 'pointer', color: '#b91c1c', fontSize: 16 },
  toolbar: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  count: { color: '#64748b', fontSize: 14 },
  btnPrimary: { padding: '9px 18px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer' },
  btnSecondary: { padding: '9px 18px', background: '#f1f5f9', color: '#1e293b', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 14, cursor: 'pointer' },
  btnUpload: { padding: '8px 12px', background: '#f1f5f9', color: '#374151', border: '1px solid #cbd5e1', borderRadius: 8, fontSize: 13, cursor: 'pointer', whiteSpace: 'nowrap' as const, fontWeight: 600 },
  empty: { background: '#fff', borderRadius: 12, padding: 40, textAlign: 'center', color: '#64748b', boxShadow: '0 1px 3px rgba(0,0,0,.06)' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 },
  card: { background: '#fff', borderRadius: 12, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,.06)', display: 'flex', flexDirection: 'column' },
  cardBody: { padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 6 },
  linkRow: { fontSize: 12, color: '#475569', display: 'flex', alignItems: 'center', gap: 6, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const },
  linkBadge: { background: '#1d4ed8', color: '#fff', fontSize: 10, fontWeight: 700, padding: '1px 5px', borderRadius: 4, flexShrink: 0 },
  cardMeta: { display: 'flex', gap: 6, flexWrap: 'wrap' as const },
  badge: { fontSize: 11, padding: '2px 8px', borderRadius: 20, fontWeight: 600 },
  badgeGray: { fontSize: 11, padding: '2px 8px', borderRadius: 20, background: '#f1f5f9', color: '#64748b' },
  cardActions: { display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' as const },
  btnSm: { padding: '5px 10px', background: '#f1f5f9', color: '#374151', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 12, cursor: 'pointer' },
  btnSmDanger: { padding: '5px 10px', background: '#fee2e2', color: '#b91c1c', border: '1px solid #fca5a5', borderRadius: 6, fontSize: 12, cursor: 'pointer' },
  // Modal
  overlay: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'flex-start', justifyContent: 'center', zIndex: 1000, paddingTop: 40, overflowY: 'auto' },
  modal: { background: '#fff', borderRadius: 16, width: '100%', maxWidth: 560, margin: '0 16px 40px', boxShadow: '0 20px 60px rgba(0,0,0,.2)', display: 'flex', flexDirection: 'column' },
  modalHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '18px 24px', borderBottom: '1px solid #e2e8f0', fontSize: 16, fontWeight: 700, color: '#1e293b' },
  closeBtn: { background: 'none', border: 'none', fontSize: 18, cursor: 'pointer', color: '#94a3b8' },
  modalBody: { padding: '20px 24px', maxHeight: '70vh', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 2 },
  modalFooter: { padding: '14px 24px', borderTop: '1px solid #e2e8f0', display: 'flex', justifyContent: 'flex-end', gap: 10 },
  label: { display: 'block', fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4, marginTop: 10 },
  input: { width: '100%', padding: '9px 12px', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 14, marginBottom: 4, boxSizing: 'border-box' as const, outline: 'none' },
  hint: { fontSize: 11, color: '#94a3b8', margin: '0 0 8px' },
  preview: { width: '100%', height: 110, objectFit: 'cover', borderRadius: 8, border: '1px solid #e2e8f0', marginBottom: 4 },
  presetRow: { display: 'flex', gap: 8, flexWrap: 'wrap' as const, marginBottom: 8 },
  presetBtn: { width: 32, height: 32, borderRadius: 6, border: 'none', cursor: 'pointer', flexShrink: 0 },
  row2: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 },
  checkRow: { display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginTop: 8 },
}
