import { useEffect, useState, useRef } from 'react'
import { adminApi } from './api'

interface Product {
  id: number
  category_id: number
  category_name: string
  title: string
  description: string | null
  image_url: string | null
  price_uah: number | null
  price_try: number | null
  price_inr: number | null
  price_pln: number | null
  price_byn: number | null
  price_byn_tr: number | null
  platform: string | null
  product_type: string | null
  rating: number
  is_featured: number
  is_active: number
  discount_pct: number
  discount_until: string | null
}

interface Category { id: number; name: string; slug: string }

const emptyForm = (): Omit<Product, 'id' | 'category_name'> => ({
  category_id: 1, title: '', description: '', image_url: '',
  price_uah: null, price_try: null, price_inr: null, price_pln: null,
  price_byn: null, price_byn_tr: null,
  platform: 'PS5', product_type: 'game', rating: 0,
  is_featured: 0, is_active: 1, discount_pct: 0, discount_until: null,
})

const PAGE_SIZE = 50

// ── Inline BYN editor ────────────────────────────────────────────────
function BynCell({ value, onSave }: { value: number | null; onSave: (v: number | null) => void }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const start = () => {
    setDraft(value != null ? String(value) : '')
    setEditing(true)
  }

  useEffect(() => {
    if (editing) inputRef.current?.focus()
  }, [editing])

  const commit = () => {
    setEditing(false)
    const num = draft.trim() === '' ? null : Number(draft)
    if (isNaN(num as number)) return
    onSave(num)
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={e => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') setEditing(false) }}
        style={s.bynInput}
        type="number"
      />
    )
  }

  return (
    <span
      onClick={start}
      title="Нажмите для редактирования"
      style={value != null ? s.bynValue : s.bynEmpty}
    >
      {value != null ? value : '—'}
    </span>
  )
}

export default function Products() {
  const [products, setProducts]     = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [total, setTotal]           = useState(0)
  const [page, setPage]             = useState(1)
  const [loading, setLoading]       = useState(false)
  const [modal, setModal]           = useState<'add' | 'edit' | null>(null)
  const [form, setForm]             = useState(emptyForm())
  const [editId, setEditId]         = useState<number | null>(null)
  const [saving, setSaving]         = useState(false)
  const [error, setError]           = useState('')
  const [uploadingImg, setUploadingImg] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  // filters
  const [search, setSearch]           = useState('')
  const [filterCat, setFilterCat]     = useState('')
  const [filterType, setFilterType]   = useState('')
  const [filterActive, setFilterActive] = useState('')

  const totalPages = Math.ceil(total / PAGE_SIZE)

  const load = async (p: number, cat: string, type: string, active: string, q: string) => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = { limit: PAGE_SIZE, offset: (p - 1) * PAGE_SIZE }
      if (q)            params.search       = q
      if (cat)          params.category_id  = cat
      if (type)         params.product_type = type
      if (active !== '') params.is_active   = active
      const { data } = await adminApi.get('/products', { params })
      setProducts(data.items ?? [])
      setTotal(data.total ?? 0)
    } finally { setLoading(false) }
  }

  const loadCategories = async () => {
    try {
      const { data } = await adminApi.get('/categories')
      if (Array.isArray(data)) setCategories(data)
    } catch {
      try {
        const r = await fetch('/api/v1/categories')
        const d = await r.json()
        if (Array.isArray(d)) setCategories(d)
      } catch { /* ignore */ }
    }
  }

  // Single effect: fires when page or any filter changes
  useEffect(() => {
    load(page, filterCat, filterType, filterActive, search)
  }, [page, filterCat, filterType, filterActive, search]) // eslint-disable-line

  useEffect(() => { loadCategories() }, [])

  // When filters change, reset to page 1. Batch state updates so only one effect run.
  const handleSearch    = (v: string) => { setSearch(v);       setPage(1) }
  const handleCat       = (v: string) => { setFilterCat(v);    setPage(1) }
  const handleType      = (v: string) => { setFilterType(v);   setPage(1) }
  const handleActive    = (v: string) => { setFilterActive(v); setPage(1) }

  const goPage = (p: number) => { if (p >= 1 && p <= totalPages) setPage(p) }

  const openAdd  = () => { setForm(emptyForm()); setEditId(null); setError(''); setModal('add') }
  const openEdit = (p: Product) => {
    setForm({
      category_id: p.category_id, title: p.title, description: p.description || '',
      image_url: p.image_url || '', price_uah: p.price_uah, price_try: p.price_try,
      price_inr: p.price_inr, price_pln: p.price_pln,
      price_byn: p.price_byn, price_byn_tr: p.price_byn_tr,
      platform: p.platform || 'PS5', product_type: p.product_type || 'game',
      rating: p.rating, is_featured: p.is_featured,
      is_active: p.is_active, discount_pct: p.discount_pct || 0, discount_until: p.discount_until || null,
    })
    setEditId(p.id); setError(''); setModal('edit')
  }

  const reload = () => load(page, filterCat, filterType, filterActive, search)

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить товар?')) return
    await adminApi.delete(`/products/${id}`)
    reload()
  }

  const handleSave = async () => {
    if (!form.title.trim()) { setError('Название обязательно'); return }
    setSaving(true); setError('')
    try {
      const payload = {
        ...form,
        is_featured: Boolean(form.is_featured),
        is_active: Boolean(form.is_active),
        discount_until: form.discount_until || null,
      }
      if (modal === 'add') await adminApi.post('/products', payload)
      else await adminApi.put(`/products/${editId}`, payload)
      setModal(null); reload()
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Ошибка сохранения')
    } finally { setSaving(false) }
  }

  // Inline BYN save — only updates the BYN fields, keeps everything else
  const saveByn = async (product: Product, field: 'price_byn' | 'price_byn_tr', value: number | null) => {
    const updated = { ...product, [field]: value }
    // Optimistic update
    setProducts(prev => prev.map(p => p.id === product.id ? updated : p))
    try {
      await adminApi.put(`/products/${product.id}`, {
        category_id: product.category_id,
        title: product.title,
        description: product.description,
        image_url: product.image_url,
        price_uah: product.price_uah,
        price_try: product.price_try,
        price_inr: product.price_inr,
        price_pln: product.price_pln,
        price_byn: field === 'price_byn' ? value : product.price_byn,
        price_byn_tr: field === 'price_byn_tr' ? value : product.price_byn_tr,
        platform: product.platform,
        rating: product.rating,
        is_featured: Boolean(product.is_featured),
        is_active: Boolean(product.is_active),
        discount_pct: product.discount_pct,
        discount_until: product.discount_until || null,
        product_type: product.product_type || 'game',
        release_date: null,
        is_preorder: false,
      })
    } catch {
      // Revert on error
      setProducts(prev => prev.map(p => p.id === product.id ? product : p))
    }
  }

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return
    setUploadingImg(true)
    try {
      const fd = new FormData(); fd.append('file', file)
      const { data } = await adminApi.post('/upload', fd)
      setForm(f => ({ ...f, image_url: data.url }))
    } catch { setError('Ошибка загрузки изображения') }
    finally { setUploadingImg(false) }
  }

  const f  = (v: number | null) => v ?? ''
  const num = (v: string) => v === '' ? null : Number(v)

  const pageButtons = () => {
    const btns: (number | '...')[] = []
    if (totalPages <= 7) { for (let i = 1; i <= totalPages; i++) btns.push(i); return btns }
    btns.push(1)
    if (page > 3) btns.push('...')
    for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) btns.push(i)
    if (page < totalPages - 2) btns.push('...')
    btns.push(totalPages)
    return btns
  }

  return (
    <div>
      {/* Toolbar */}
      <div style={s.toolbar}>
        <input placeholder="Поиск по названию…" value={search}
          onChange={e => handleSearch(e.target.value)} style={s.searchInput} />
        <select value={filterCat} onChange={e => handleCat(e.target.value)} style={s.sel}>
          <option value="">Все категории</option>
          {categories.map(c => <option key={c.id} value={String(c.id)}>{c.name}</option>)}
        </select>
        <select value={filterType} onChange={e => handleType(e.target.value)} style={s.sel}>
          <option value="">Все типы</option>
          <option value="game">Игры</option>
          <option value="subscription">Подписки</option>
          <option value="topup">Пополнения</option>
          <option value="dlc">DLC</option>
        </select>
        <select value={filterActive} onChange={e => handleActive(e.target.value)} style={s.sel}>
          <option value="">Активность</option>
          <option value="1">Активные</option>
          <option value="0">Неактивные</option>
        </select>
        <span style={s.count}>{total} товаров</span>
        <button onClick={openAdd} style={s.btnPrimary}>+ Добавить</button>
      </div>

      {/* Table */}
      {loading ? <div style={s.loading}>Загрузка…</div> : (
        <div style={s.tableWrap}>
          <table style={s.table}>
            <thead>
              <tr style={s.thead}>
                <th style={s.th}>ID</th>
                <th style={s.th}>Название</th>
                <th style={s.th}>Тип</th>
                <th style={s.th}>Категория</th>
                <th style={s.th}>Платф.</th>
                <th style={s.th}>UAH</th>
                <th style={s.th}>TRY</th>
                <th style={s.th} title="Цена BYN для UA-региона (кликабельно)">BYN UA</th>
                <th style={s.th} title="Цена BYN для TR-региона (кликабельно)">BYN TR</th>
                <th style={s.th}>Скидка</th>
                <th style={s.th}>Акт.</th>
                <th style={s.th}>Действия</th>
              </tr>
            </thead>
            <tbody>
              {products.map(p => (
                <tr key={p.id} style={s.tr}>
                  <td style={s.td}>{p.id}</td>
                  <td style={{ ...s.td, maxWidth: 220 }}>
                    <div style={s.titleCell}>
                      {p.image_url && <img src={p.image_url} style={s.thumb} alt="" />}
                      <span style={s.titleText}>{p.title}</span>
                    </div>
                  </td>
                  <td style={s.td}><span style={typeStyle(p.product_type)}>{p.product_type || 'game'}</span></td>
                  <td style={s.td}>{p.category_name}</td>
                  <td style={s.td}>{p.platform}</td>
                  <td style={s.td}>{p.price_uah ?? '—'}</td>
                  <td style={s.td}>{p.price_try ?? '—'}</td>
                  <td style={s.td}>
                    <BynCell
                      value={p.price_byn}
                      onSave={v => saveByn(p, 'price_byn', v)}
                    />
                  </td>
                  <td style={s.td}>
                    <BynCell
                      value={p.price_byn_tr}
                      onSave={v => saveByn(p, 'price_byn_tr', v)}
                    />
                  </td>
                  <td style={s.td}>{p.discount_pct ? `${p.discount_pct}%` : '—'}</td>
                  <td style={s.td}>
                    <span style={p.is_active ? s.badgeGreen : s.badgeGray}>{p.is_active ? 'Да' : 'Нет'}</span>
                  </td>
                  <td style={s.td}>
                    <button onClick={() => openEdit(p)} style={s.btnEdit}>✏️</button>
                    <button onClick={() => handleDelete(p.id)} style={s.btnDel}>🗑</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={s.pagination}>
          <button onClick={() => goPage(page - 1)} disabled={page === 1} style={s.pageBtn}>‹</button>
          {pageButtons().map((b, i) =>
            b === '...' ? <span key={`e${i}`} style={s.pageEllipsis}>…</span> :
            <button key={b} onClick={() => goPage(b as number)}
              style={{ ...s.pageBtn, ...(b === page ? s.pageBtnActive : {}) }}>{b}</button>
          )}
          <button onClick={() => goPage(page + 1)} disabled={page === totalPages} style={s.pageBtn}>›</button>
          <span style={s.pageInfo}>Стр. {page} из {totalPages} · {total} товаров</span>
        </div>
      )}

      {/* Modal */}
      {modal && (
        <div style={s.overlay} onClick={e => e.target === e.currentTarget && setModal(null)}>
          <div style={s.modal}>
            <div style={s.modalHeader}>
              <span>{modal === 'add' ? 'Добавить товар' : 'Редактировать товар'}</span>
              <button onClick={() => setModal(null)} style={s.closeBtn}>✕</button>
            </div>
            <div style={s.modalBody}>
              <div style={s.row2}>
                <div>
                  <label style={s.label}>Название *</label>
                  <input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} style={s.input} />
                </div>
                <div>
                  <label style={s.label}>Тип</label>
                  <select value={form.product_type || 'game'} onChange={e => setForm(f => ({ ...f, product_type: e.target.value }))} style={s.input}>
                    <option value="game">Игра</option>
                    <option value="subscription">Подписка</option>
                    <option value="topup">Пополнение</option>
                    <option value="dlc">DLC</option>
                  </select>
                </div>
              </div>
              <div style={s.row2}>
                <div>
                  <label style={s.label}>Категория</label>
                  <select value={form.category_id} onChange={e => setForm(f => ({ ...f, category_id: Number(e.target.value) }))} style={s.input}>
                    {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
                <div>
                  <label style={s.label}>Платформа</label>
                  <select value={form.platform || ''} onChange={e => setForm(f => ({ ...f, platform: e.target.value }))} style={s.input}>
                    {['PS5','PS4','PS3','PSN','PS Plus','EA Play','Other'].map(p => <option key={p}>{p}</option>)}
                  </select>
                </div>
              </div>
              <label style={s.label}>URL картинки</label>
              <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                <input value={form.image_url || ''} onChange={e => setForm(f => ({ ...f, image_url: e.target.value }))}
                  style={{ ...s.input, marginBottom: 0, flex: 1 }} placeholder="https://…" />
                <button onClick={() => fileRef.current?.click()} style={s.btnSecondary} disabled={uploadingImg}>
                  {uploadingImg ? '…' : '📁'}
                </button>
                <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handleImageUpload} />
              </div>
              {form.image_url && <img src={form.image_url} style={s.previewImg} alt="" />}
              <label style={s.label}>Описание</label>
              <textarea value={form.description || ''} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                style={{ ...s.input, minHeight: 60, resize: 'vertical' }} />
              <div style={s.row4}>
                <div><label style={s.label}>Цена UAH</label>
                  <input type="number" value={f(form.price_uah)} onChange={e => setForm(f => ({ ...f, price_uah: num(e.target.value) }))} style={s.input} /></div>
                <div><label style={s.label}>Цена TRY</label>
                  <input type="number" value={f(form.price_try)} onChange={e => setForm(f => ({ ...f, price_try: num(e.target.value) }))} style={s.input} /></div>
                <div><label style={s.label}>Цена INR</label>
                  <input type="number" value={f(form.price_inr)} onChange={e => setForm(f => ({ ...f, price_inr: num(e.target.value) }))} style={s.input} /></div>
                <div><label style={s.label}>Цена PLN</label>
                  <input type="number" value={f(form.price_pln)} onChange={e => setForm(f => ({ ...f, price_pln: num(e.target.value) }))} style={s.input} /></div>
              </div>
              <div style={s.row2}>
                <div>
                  <label style={s.label}>BYN (UA) — ручная цена</label>
                  <input type="number" value={f(form.price_byn)} onChange={e => setForm(f => ({ ...f, price_byn: num(e.target.value) }))} style={s.input} placeholder="Авто из UAH если пусто" />
                </div>
                <div>
                  <label style={s.label}>BYN (TR) — ручная цена</label>
                  <input type="number" value={f(form.price_byn_tr)} onChange={e => setForm(f => ({ ...f, price_byn_tr: num(e.target.value) }))} style={s.input} placeholder="Авто из TRY если пусто" />
                </div>
              </div>
              <div style={s.row3}>
                <div><label style={s.label}>Скидка %</label>
                  <input type="number" min={0} max={100} value={form.discount_pct} onChange={e => setForm(f => ({ ...f, discount_pct: Number(e.target.value) }))} style={s.input} /></div>
                <div><label style={s.label}>Акция до</label>
                  <input type="datetime-local" value={form.discount_until?.slice(0,16) || ''} onChange={e => setForm(f => ({ ...f, discount_until: e.target.value || null }))} style={s.input} /></div>
                <div><label style={s.label}>Рейтинг</label>
                  <input type="number" step={0.1} min={0} max={5} value={form.rating} onChange={e => setForm(f => ({ ...f, rating: Number(e.target.value) }))} style={s.input} /></div>
              </div>
              <div style={s.rowCheck}>
                <label style={s.checkLabel}><input type="checkbox" checked={Boolean(form.is_featured)} onChange={e => setForm(f => ({ ...f, is_featured: e.target.checked ? 1 : 0 }))} /> Рекомендуемый</label>
                <label style={s.checkLabel}><input type="checkbox" checked={Boolean(form.is_active)} onChange={e => setForm(f => ({ ...f, is_active: e.target.checked ? 1 : 0 }))} /> Активен</label>
              </div>
              {error && <div style={s.error}>{error}</div>}
            </div>
            <div style={s.modalFooter}>
              <button onClick={() => setModal(null)} style={s.btnSecondary}>Отмена</button>
              <button onClick={handleSave} disabled={saving} style={s.btnPrimary}>{saving ? 'Сохранение…' : 'Сохранить'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function typeStyle(t: string | null): React.CSSProperties {
  const map: Record<string, string> = { game: '#dbeafe', subscription: '#dcfce7', topup: '#fef9c3', dlc: '#f3e8ff' }
  const txt: Record<string, string> = { game: '#1d4ed8', subscription: '#15803d', topup: '#854d0e', dlc: '#7e22ce' }
  const type = t || 'game'
  return { background: map[type] || '#f1f5f9', color: txt[type] || '#374151', padding: '2px 7px', borderRadius: 10, fontSize: 11, fontWeight: 600, whiteSpace: 'nowrap' }
}

const s: Record<string, React.CSSProperties> = {
  toolbar: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, flexWrap: 'wrap' },
  searchInput: { padding: '8px 12px', border: '1px solid #cbd5e1', borderRadius: 7, fontSize: 14, width: 180 },
  sel: { padding: '8px 10px', border: '1px solid #cbd5e1', borderRadius: 7, fontSize: 13 },
  count: { color: '#64748b', fontSize: 13, marginLeft: 4 },
  btnPrimary: { padding: '8px 18px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 7, fontSize: 14, fontWeight: 600, cursor: 'pointer', marginLeft: 'auto' },
  btnSecondary: { padding: '8px 14px', background: '#f1f5f9', color: '#374151', border: '1px solid #cbd5e1', borderRadius: 7, fontSize: 13, cursor: 'pointer' },
  btnEdit: { background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, marginRight: 4 },
  btnDel: { background: 'none', border: 'none', cursor: 'pointer', fontSize: 16 },
  loading: { textAlign: 'center', color: '#94a3b8', padding: 40 },
  tableWrap: { overflowX: 'auto' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 13 },
  thead: { background: '#f8fafc' },
  th: { padding: '10px 10px', textAlign: 'left', fontWeight: 600, color: '#374151', borderBottom: '2px solid #e2e8f0', whiteSpace: 'nowrap' },
  tr: { borderBottom: '1px solid #f1f5f9' },
  td: { padding: '8px 10px', verticalAlign: 'middle', color: '#1e293b' },
  titleCell: { display: 'flex', alignItems: 'center', gap: 8 },
  titleText: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 160 },
  thumb: { width: 30, height: 30, borderRadius: 4, objectFit: 'cover', flexShrink: 0 },
  badgeGreen: { background: '#dcfce7', color: '#16a34a', padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 600 },
  badgeGray: { background: '#f1f5f9', color: '#64748b', padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 600 },
  pagination: { display: 'flex', alignItems: 'center', gap: 4, marginTop: 16, flexWrap: 'wrap' },
  pageBtn: { minWidth: 32, height: 32, padding: '0 8px', border: '1px solid #e2e8f0', borderRadius: 6, background: '#fff', color: '#374151', fontSize: 13, cursor: 'pointer' },
  pageBtnActive: { background: '#2563eb', color: '#fff', borderColor: '#2563eb', fontWeight: 700 },
  pageEllipsis: { padding: '0 4px', color: '#94a3b8' },
  pageInfo: { marginLeft: 8, fontSize: 12, color: '#64748b' },
  overlay: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 1000, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: 40, overflowY: 'auto' },
  modal: { background: '#fff', borderRadius: 12, width: '100%', maxWidth: 680, boxShadow: '0 20px 60px rgba(0,0,0,0.2)', margin: '0 16px 40px' },
  modalHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '18px 24px', borderBottom: '1px solid #e2e8f0', fontSize: 16, fontWeight: 700, color: '#1e293b' },
  closeBtn: { background: 'none', border: 'none', fontSize: 18, cursor: 'pointer', color: '#94a3b8' },
  modalBody: { padding: '20px 24px', maxHeight: '65vh', overflowY: 'auto' },
  modalFooter: { padding: '14px 24px', borderTop: '1px solid #e2e8f0', display: 'flex', justifyContent: 'flex-end', gap: 10 },
  label: { display: 'block', fontSize: 11, fontWeight: 600, color: '#64748b', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' },
  input: { width: '100%', padding: '8px 10px', border: '1px solid #cbd5e1', borderRadius: 7, fontSize: 14, marginBottom: 12, boxSizing: 'border-box' },
  row2: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 },
  row3: { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginTop: 4 },
  row4: { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 10 },
  rowCheck: { display: 'flex', gap: 20, marginTop: 8 },
  checkLabel: { display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, color: '#374151', cursor: 'pointer' },
  error: { color: '#ef4444', fontSize: 13, marginTop: 8 },
  previewImg: { width: 80, height: 80, objectFit: 'cover', borderRadius: 6, marginBottom: 12 },
  // Inline BYN editor
  bynValue: { cursor: 'pointer', color: '#0ea5e9', fontWeight: 600, padding: '2px 6px', borderRadius: 4, background: '#f0f9ff', display: 'inline-block', minWidth: 36, textAlign: 'center' },
  bynEmpty: { cursor: 'pointer', color: '#cbd5e1', padding: '2px 6px', borderRadius: 4, display: 'inline-block', minWidth: 36, textAlign: 'center' },
  bynInput: { width: 72, padding: '3px 6px', border: '2px solid #2563eb', borderRadius: 5, fontSize: 13, outline: 'none', fontWeight: 600 },
}
