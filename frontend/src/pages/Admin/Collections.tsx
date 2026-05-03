import { useState, useEffect, useCallback } from 'react'
import { adminApi } from './api'

interface Collection {
  id: number
  title: string
  slug: string
  description: string
  is_active: number
  product_count: number
}

interface ColProduct {
  id: number
  title: string
  image_url: string | null
  price_uah: number | null
  price_try: number | null
  product_type: string
  platform: string | null
  sort_order: number
}

interface SearchProduct {
  id: number
  title: string
  image_url: string | null
  product_type: string
  price_uah: number | null
}

type View = 'list' | 'edit'

export default function Collections() {
  const [view, setView] = useState<View>('list')
  const [collections, setCollections] = useState<Collection[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  // Edit state
  const [editCol, setEditCol] = useState<Collection | null>(null)
  const [form, setForm] = useState({ title: '', slug: '', description: '', is_active: 1 })
  const [colProducts, setColProducts] = useState<ColProduct[]>([])
  const [searchQ, setSearchQ] = useState('')
  const [searchResults, setSearchResults] = useState<SearchProduct[]>([])
  const [searching, setSearching] = useState(false)
  const [saving, setSaving] = useState(false)

  // ── List view ──────────────────────────────────────────────────

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await adminApi.get('/collections')
      setCollections(data)
    } catch {
      setErr('Не удалось загрузить коллекции')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadList() }, [loadList])

  const handleDelete = async (id: number, title: string) => {
    if (!confirm(`Удалить коллекцию «${title}»?`)) return
    try {
      await adminApi.delete(`/collections/${id}`)
      loadList()
    } catch { setErr('Ошибка удаления') }
  }

  const openCreate = () => {
    setEditCol(null)
    setForm({ title: '', slug: '', description: '', is_active: 1 })
    setColProducts([])
    setSearchQ('')
    setSearchResults([])
    setView('edit')
  }

  const openEdit = async (col: Collection) => {
    setEditCol(col)
    setForm({ title: col.title, slug: col.slug, description: col.description || '', is_active: col.is_active })
    setSearchQ('')
    setSearchResults([])
    setView('edit')
    loadColProducts(col.id)
  }

  // ── Edit view ──────────────────────────────────────────────────

  const loadColProducts = async (colId: number) => {
    try {
      const { data } = await adminApi.get(`/collections/${colId}/products`)
      setColProducts(data)
    } catch { setErr('Ошибка загрузки товаров коллекции') }
  }

  // Auto-generate slug from title
  const handleTitleChange = (val: string) => {
    const slug = val.toLowerCase().replace(/[^a-z0-9а-яёіїє]+/gi, '-').replace(/[^a-z0-9-]/g, '').replace(/^-+|-+$/g, '')
    setForm(f => ({ ...f, title: val, slug: f.slug || slug }))
  }

  // Search products
  useEffect(() => {
    if (!searchQ.trim() || searchQ.length < 2) { setSearchResults([]); return }
    const t = setTimeout(async () => {
      setSearching(true)
      try {
        const { data } = await adminApi.get('/products', { params: { search: searchQ, limit: 20 } })
        const inCol = new Set(colProducts.map(p => p.id))
        setSearchResults((data.items || []).filter((p: SearchProduct) => !inCol.has(p.id)))
      } catch { /* ignore */ }
      finally { setSearching(false) }
    }, 350)
    return () => clearTimeout(t)
  }, [searchQ, colProducts])

  const addProduct = async (product: SearchProduct) => {
    if (!editCol) return
    try {
      await adminApi.post(`/collections/${editCol.id}/products`, { product_ids: [product.id] })
      loadColProducts(editCol.id)
      setSearchResults(r => r.filter(p => p.id !== product.id))
    } catch { setErr('Ошибка добавления товара') }
  }

  const removeProduct = async (productId: number) => {
    if (!editCol) return
    try {
      await adminApi.delete(`/collections/${editCol.id}/products/${productId}`)
      setColProducts(p => p.filter(x => x.id !== productId))
    } catch { setErr('Ошибка удаления товара') }
  }

  const moveProduct = async (productId: number, direction: 'up' | 'down') => {
    if (!editCol) return
    const idx = colProducts.findIndex(p => p.id === productId)
    if (direction === 'up' && idx === 0) return
    if (direction === 'down' && idx === colProducts.length - 1) return
    const newList = [...colProducts]
    const swapIdx = direction === 'up' ? idx - 1 : idx + 1
    ;[newList[idx], newList[swapIdx]] = [newList[swapIdx], newList[idx]]
    // Update sort_orders
    const updated = newList.map((p, i) => ({ ...p, sort_order: i }))
    setColProducts(updated)
    // Persist to backend
    try {
      await Promise.all(updated.map((p, i) =>
        adminApi.put(`/collections/${editCol.id}/products/${p.id}/order`, { sort_order: i })
      ))
    } catch { setErr('Ошибка сохранения порядка') }
  }

  const handleSave = async () => {
    if (!form.title.trim()) { setErr('Название обязательно'); return }
    setSaving(true); setErr('')
    try {
      if (editCol) {
        await adminApi.put(`/collections/${editCol.id}`, form)
        // Reload to get updated collection
        const { data } = await adminApi.get('/collections')
        const updated = data.find((c: Collection) => c.id === editCol.id)
        if (updated) setEditCol(updated)
      } else {
        const { data } = await adminApi.post('/collections', form)
        // Now open the new collection for editing products
        setEditCol({ ...data, product_count: 0, is_active: 1, description: form.description })
        setForm(f => ({ ...f, slug: data.slug }))
      }
      loadList()
    } catch (e: any) {
      setErr(e.response?.data?.detail || 'Ошибка сохранения')
    } finally { setSaving(false) }
  }

  // ── Render ─────────────────────────────────────────────────────

  if (view === 'list') {
    return (
      <div style={s.wrap}>
        {err && <div style={s.error}>{err}<button onClick={() => setErr('')} style={s.errX}>✕</button></div>}
        <div style={s.toolbar}>
          <span style={s.count}>{collections.length} коллекций</span>
          <button style={s.btnPrimary} onClick={openCreate}>+ Создать коллекцию</button>
        </div>
        {loading ? <div style={s.loader}>Загрузка...</div> : collections.length === 0 ? (
          <div style={s.empty}>Коллекций пока нет</div>
        ) : (
          <div style={s.colList}>
            {collections.map(c => (
              <div key={c.id} style={s.colCard}>
                <div style={s.colInfo}>
                  <div style={s.colTitle}>{c.title}</div>
                  <div style={s.colMeta}>
                    <code style={s.slug}>/collection/{c.slug}</code>
                    <span style={{ ...s.badge, background: c.is_active ? '#dcfce7' : '#fee2e2', color: c.is_active ? '#15803d' : '#b91c1c' }}>
                      {c.is_active ? 'Активна' : 'Скрыта'}
                    </span>
                    <span style={s.badgeGray}>{c.product_count} товаров</span>
                  </div>
                  {c.description && <div style={s.colDesc}>{c.description}</div>}
                </div>
                <div style={s.colActions}>
                  <button style={s.btnEdit} onClick={() => openEdit(c)}>✏️ Редактировать</button>
                  <button style={s.btnDel} onClick={() => handleDelete(c.id, c.title)}>🗑 Удалить</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  // Edit view
  return (
    <div style={s.wrap}>
      {err && <div style={s.error}>{err}<button onClick={() => setErr('')} style={s.errX}>✕</button></div>}

      <div style={s.editHeader}>
        <button onClick={() => setView('list')} style={s.backBtn}>← Все коллекции</button>
        <h2 style={s.editTitle}>{editCol ? `Редактировать: ${editCol.title}` : 'Новая коллекция'}</h2>
      </div>

      <div style={s.twoCol}>
        {/* Left: form */}
        <div>
          <div style={s.card}>
            <h3 style={s.cardTitle}>Основная информация</h3>

            <label style={s.label}>Название *</label>
            <input style={s.input} value={form.title} onChange={e => handleTitleChange(e.target.value)} placeholder="Например: Лучшие хиты" />

            <label style={s.label}>Slug (URL)</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={s.urlPrefix}>/collection/</span>
              <input style={{ ...s.input, marginBottom: 0, flex: 1 }} value={form.slug}
                onChange={e => setForm(f => ({ ...f, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') }))}
                placeholder="luchshie-hity" />
            </div>
            <p style={s.hint}>Только латинские буквы, цифры и дефис</p>

            <label style={s.label}>Описание</label>
            <textarea style={{ ...s.input, minHeight: 60, resize: 'vertical' as const }}
              value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              placeholder="Краткое описание коллекции (необязательно)" />

            <label style={s.checkRow}>
              <input type="checkbox" checked={!!form.is_active} onChange={e => setForm(f => ({ ...f, is_active: e.target.checked ? 1 : 0 }))} />
              <span>Активна (видна пользователям)</span>
            </label>

            <button style={s.btnSave} onClick={handleSave} disabled={saving}>
              {saving ? 'Сохранение...' : editCol ? '💾 Сохранить изменения' : '✓ Создать и добавить товары'}
            </button>
          </div>
        </div>

        {/* Right: products (only after collection is created) */}
        <div>
          {editCol ? (
            <>
              {/* Search + Add */}
              <div style={s.card}>
                <h3 style={s.cardTitle}>Добавить товары</h3>
                <input
                  style={s.input}
                  placeholder="Поиск по названию товара..."
                  value={searchQ}
                  onChange={e => setSearchQ(e.target.value)}
                />
                {searching && <div style={s.hint}>Поиск...</div>}
                {searchResults.length > 0 && (
                  <div style={s.searchList}>
                    {searchResults.map(p => (
                      <div key={p.id} style={s.searchItem}>
                        {p.image_url && <img src={p.image_url} style={s.thumb} alt="" />}
                        <div style={{ flex: 1 }}>
                          <div style={s.searchTitle}>{p.title}</div>
                          <div style={s.searchMeta}>{p.product_type} · {p.price_uah ? `${p.price_uah} UAH` : '—'}</div>
                        </div>
                        <button style={s.btnAdd} onClick={() => addProduct(p)}>+ Добавить</button>
                      </div>
                    ))}
                  </div>
                )}
                {searchQ.length >= 2 && !searching && searchResults.length === 0 && (
                  <div style={s.hint}>Ничего не найдено или все уже добавлены</div>
                )}
              </div>

              {/* Products in collection */}
              <div style={s.card}>
                <h3 style={s.cardTitle}>Товары в коллекции ({colProducts.length})</h3>
                {colProducts.length === 0 ? (
                  <div style={s.hint}>Пока пусто. Используйте поиск выше.</div>
                ) : (
                  <div style={s.colProductList}>
                    {colProducts.map((p, i) => (
                      <div key={p.id} style={s.colProductItem}>
                        <span style={s.orderNum}>{i + 1}</span>
                        {p.image_url && <img src={p.image_url} style={s.thumb} alt="" />}
                        <div style={{ flex: 1 }}>
                          <div style={s.searchTitle}>{p.title}</div>
                          <div style={s.searchMeta}>{p.product_type} · {p.price_uah ? `${p.price_uah} UAH` : '—'}</div>
                        </div>
                        <div style={s.orderBtns}>
                          <button style={s.btnOrder} onClick={() => moveProduct(p.id, 'up')} disabled={i === 0}>↑</button>
                          <button style={s.btnOrder} onClick={() => moveProduct(p.id, 'down')} disabled={i === colProducts.length - 1}>↓</button>
                          <button style={s.btnRemove} onClick={() => removeProduct(p.id)}>✕</button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div style={s.card}>
              <div style={s.hint}>Сначала создайте коллекцию, затем добавьте в неё товары.</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const s: Record<string, React.CSSProperties> = {
  wrap: { display: 'flex', flexDirection: 'column', gap: 16 },
  loader: { padding: 40, textAlign: 'center', color: '#64748b' },
  error: { background: '#fee2e2', color: '#b91c1c', padding: '10px 16px', borderRadius: 8, fontSize: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  errX: { background: 'none', border: 'none', cursor: 'pointer', color: '#b91c1c', fontSize: 16 },
  toolbar: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  count: { color: '#64748b', fontSize: 14 },
  btnPrimary: { padding: '9px 18px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer' },
  empty: { background: '#fff', borderRadius: 12, padding: 40, textAlign: 'center', color: '#64748b', boxShadow: '0 1px 3px rgba(0,0,0,.06)' },
  colList: { display: 'flex', flexDirection: 'column', gap: 10 },
  colCard: { background: '#fff', borderRadius: 12, padding: '16px 20px', boxShadow: '0 1px 3px rgba(0,0,0,.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 },
  colInfo: { flex: 1 },
  colTitle: { fontSize: 16, fontWeight: 700, color: '#1e293b', marginBottom: 6 },
  colMeta: { display: 'flex', gap: 8, flexWrap: 'wrap' as const, alignItems: 'center', marginBottom: 4 },
  slug: { background: '#f1f5f9', padding: '2px 7px', borderRadius: 4, fontSize: 12, color: '#475569' },
  badge: { fontSize: 11, padding: '2px 8px', borderRadius: 20, fontWeight: 600 },
  badgeGray: { fontSize: 11, padding: '2px 8px', borderRadius: 20, background: '#f1f5f9', color: '#64748b' },
  colDesc: { fontSize: 13, color: '#64748b', marginTop: 4 },
  colActions: { display: 'flex', gap: 8, flexShrink: 0 },
  btnEdit: { padding: '7px 14px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 7, fontSize: 13, cursor: 'pointer' },
  btnDel: { padding: '7px 14px', background: '#fee2e2', color: '#b91c1c', border: '1px solid #fca5a5', borderRadius: 7, fontSize: 13, cursor: 'pointer' },
  // Edit view
  editHeader: { display: 'flex', alignItems: 'center', gap: 16, marginBottom: 4 },
  backBtn: { background: 'none', border: 'none', color: '#2563eb', fontSize: 14, fontWeight: 600, cursor: 'pointer', padding: 0 },
  editTitle: { fontSize: 18, fontWeight: 700, color: '#1e293b', margin: 0 },
  twoCol: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, alignItems: 'start' },
  card: { background: '#fff', borderRadius: 12, padding: 20, boxShadow: '0 1px 3px rgba(0,0,0,.06)', display: 'flex', flexDirection: 'column', gap: 2, marginBottom: 16 },
  cardTitle: { fontSize: 15, fontWeight: 700, color: '#1e293b', margin: '0 0 12px' },
  label: { fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase' as const, letterSpacing: '0.05em', marginTop: 8 },
  input: { width: '100%', padding: '8px 12px', border: '1px solid #e2e8f0', borderRadius: 7, fontSize: 14, marginBottom: 4, boxSizing: 'border-box' as const, outline: 'none' },
  urlPrefix: { fontSize: 13, color: '#64748b', whiteSpace: 'nowrap' as const },
  hint: { fontSize: 12, color: '#94a3b8', margin: '2px 0 6px' },
  checkRow: { display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 14, color: '#374151', marginTop: 8 },
  btnSave: { marginTop: 14, padding: '10px 20px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 700, cursor: 'pointer', width: '100%' },
  // Search
  searchList: { border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden', marginTop: 4 },
  searchItem: { display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', borderBottom: '1px solid #f1f5f9', background: '#fff' },
  searchTitle: { fontSize: 13, fontWeight: 600, color: '#1e293b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const },
  searchMeta: { fontSize: 11, color: '#94a3b8', marginTop: 2 },
  btnAdd: { padding: '5px 12px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: 'pointer', flexShrink: 0 },
  thumb: { width: 36, height: 36, borderRadius: 6, objectFit: 'cover' as const, flexShrink: 0 },
  // Collection products
  colProductList: { display: 'flex', flexDirection: 'column', gap: 6 },
  colProductItem: { display: 'flex', alignItems: 'center', gap: 10, padding: '8px 4px', borderBottom: '1px solid #f1f5f9' },
  orderNum: { fontSize: 12, color: '#94a3b8', width: 20, textAlign: 'center' as const, flexShrink: 0 },
  orderBtns: { display: 'flex', gap: 4 },
  btnOrder: { width: 28, height: 28, background: '#f1f5f9', border: '1px solid #e2e8f0', borderRadius: 5, fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  btnRemove: { width: 28, height: 28, background: '#fee2e2', color: '#b91c1c', border: '1px solid #fca5a5', borderRadius: 5, fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' },
}
