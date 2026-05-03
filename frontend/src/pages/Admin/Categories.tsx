import { useState, useEffect } from 'react'
import { adminApi } from './api'

interface Category {
  id: number
  name: string
  slug: string
  sort_order: number
}

export default function Categories() {
  const [cats, setCats] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [newName, setNewName] = useState('')
  const [newSlug, setNewSlug] = useState('')
  const [adding, setAdding] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [editSlug, setEditSlug] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const { data } = await adminApi.get('/categories')
      setCats(data)
    } catch {
      setErr('Не удалось загрузить категории')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleAdd = async () => {
    if (!newName.trim()) return
    setAdding(true)
    setErr('')
    try {
      await adminApi.post('/categories', { name: newName.trim(), slug: newSlug.trim() || undefined })
      setNewName('')
      setNewSlug('')
      await load()
    } catch {
      setErr('Ошибка при добавлении категории')
    } finally {
      setAdding(false)
    }
  }

  const handleEdit = (cat: Category) => {
    setEditId(cat.id)
    setEditName(cat.name)
    setEditSlug(cat.slug)
  }

  const handleSave = async () => {
    if (!editId) return
    setSaving(true)
    setErr('')
    try {
      await adminApi.put(`/categories/${editId}`, { name: editName.trim(), slug: editSlug.trim() })
      setEditId(null)
      await load()
    } catch {
      setErr('Ошибка при сохранении')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Удалить категорию «${name}»? Это может повлиять на товары.`)) return
    setErr('')
    try {
      await adminApi.delete(`/categories/${id}`)
      await load()
    } catch {
      setErr('Ошибка при удалении')
    }
  }

  if (loading) return <div style={s.loader}>Загрузка...</div>

  return (
    <div style={s.wrap}>
      {err && <div style={s.error}>{err}</div>}

      {/* Add new */}
      <div style={s.card}>
        <h3 style={s.cardTitle}>Добавить категорию</h3>
        <div style={s.row}>
          <input
            style={s.input}
            placeholder="Название (напр. Экшен)"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleAdd()}
          />
          <input
            style={s.input}
            placeholder="Slug (напр. action) — опционально"
            value={newSlug}
            onChange={e => setNewSlug(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleAdd()}
          />
          <button style={s.btnPrimary} onClick={handleAdd} disabled={adding || !newName.trim()}>
            {adding ? 'Добавление...' : '+ Добавить'}
          </button>
        </div>
      </div>

      {/* List */}
      <div style={s.card}>
        <h3 style={s.cardTitle}>Категории ({cats.length})</h3>
        {cats.length === 0 ? (
          <p style={{ color: '#64748b' }}>Категорий пока нет</p>
        ) : (
          <table style={s.table}>
            <thead>
              <tr style={s.thead}>
                <th style={s.th}>ID</th>
                <th style={s.th}>Название</th>
                <th style={s.th}>Slug</th>
                <th style={s.th}>Действия</th>
              </tr>
            </thead>
            <tbody>
              {cats.map(cat => (
                <tr key={cat.id} style={s.tr}>
                  <td style={s.td}>{cat.id}</td>
                  <td style={s.td}>
                    {editId === cat.id ? (
                      <input
                        style={{ ...s.input, margin: 0 }}
                        value={editName}
                        onChange={e => setEditName(e.target.value)}
                        autoFocus
                      />
                    ) : (
                      cat.name
                    )}
                  </td>
                  <td style={s.td}>
                    {editId === cat.id ? (
                      <input
                        style={{ ...s.input, margin: 0 }}
                        value={editSlug}
                        onChange={e => setEditSlug(e.target.value)}
                      />
                    ) : (
                      <code style={s.slug}>{cat.slug}</code>
                    )}
                  </td>
                  <td style={s.td}>
                    {editId === cat.id ? (
                      <div style={s.actions}>
                        <button style={s.btnSm} onClick={handleSave} disabled={saving}>
                          {saving ? '...' : '✓ Сохранить'}
                        </button>
                        <button style={s.btnSmDanger} onClick={() => setEditId(null)}>
                          Отмена
                        </button>
                      </div>
                    ) : (
                      <div style={s.actions}>
                        <button style={s.btnSm} onClick={() => handleEdit(cat)}>Изменить</button>
                        <button style={s.btnSmDanger} onClick={() => handleDelete(cat.id, cat.name)}>Удалить</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

const s: Record<string, React.CSSProperties> = {
  wrap: { display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 800 },
  loader: { padding: 40, textAlign: 'center', color: '#64748b' },
  error: { background: '#fee2e2', color: '#b91c1c', padding: '10px 16px', borderRadius: 8, fontSize: 14 },
  card: { background: '#fff', borderRadius: 12, padding: 24, boxShadow: '0 1px 3px rgba(0,0,0,.06)' },
  cardTitle: { margin: '0 0 16px', fontSize: 16, fontWeight: 700, color: '#1e293b' },
  row: { display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' },
  input: {
    flex: 1,
    minWidth: 160,
    padding: '8px 12px',
    border: '1px solid #e2e8f0',
    borderRadius: 7,
    fontSize: 14,
    outline: 'none',
  },
  btnPrimary: {
    padding: '8px 18px',
    background: '#2563eb',
    color: '#fff',
    border: 'none',
    borderRadius: 7,
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  table: { width: '100%', borderCollapse: 'collapse' },
  thead: { background: '#f8fafc' },
  th: { padding: '10px 12px', textAlign: 'left', fontSize: 12, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', borderBottom: '1px solid #e2e8f0' },
  tr: { borderBottom: '1px solid #f1f5f9' },
  td: { padding: '12px 12px', fontSize: 14, color: '#1e293b', verticalAlign: 'middle' },
  slug: { background: '#f1f5f9', padding: '2px 6px', borderRadius: 4, fontSize: 12, color: '#475569' },
  actions: { display: 'flex', gap: 6 },
  btnSm: { padding: '5px 12px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 6, fontSize: 13, cursor: 'pointer' },
  btnSmDanger: { padding: '5px 12px', background: '#ef4444', color: '#fff', border: 'none', borderRadius: 6, fontSize: 13, cursor: 'pointer' },
}
