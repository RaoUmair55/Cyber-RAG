import React, { useEffect, useState } from 'react'

const API_BASE = 'http://localhost:8000'
const TYPES = ['command', 'note', 'payload']
const PHASES = ['recon', 'enumeration', 'exploitation', 'post-exploitation', 'reporting', 'general']

const EMPTY_FORM = { type: 'command', title: '', content: '', tags: '', phase: 'general', target: '' }

function TypeBadge({ type }) {
  return <span className={`vault-badge vault-badge-${type}`}>{type}</span>
}

function EntryCard({ entry, onDelete }) {
  return (
    <div className="vault-card">
      <div className="vault-card-top">
        <TypeBadge type={entry.type} />
        <span className="vault-phase">{entry.phase}</span>
        {entry.similarity !== undefined && (
          <span className="vault-sim">{Math.round(entry.similarity * 100)}% match</span>
        )}
        <button className="vault-delete" onClick={() => onDelete(entry.id)} title="Delete">✕</button>
      </div>
      <div className="vault-title">{entry.title}</div>
      <pre className="vault-content">{entry.content}</pre>
      <div className="vault-meta">
        {entry.target && <span className="vault-target">target: {entry.target}</span>}
        {entry.tags && <span className="vault-tags">{entry.tags}</span>}
      </div>
    </div>
  )
}

export default function Vault() {
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [query, setQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)

  async function loadRecent() {
    setLoading(true)
    const params = new URLSearchParams()
    if (typeFilter) params.set('type', typeFilter)
    const res = await fetch(`${API_BASE}/kb/list?${params}`)
    const data = await res.json()
    setEntries(data.results)
    setLoading(false)
  }

  useEffect(() => { loadRecent() }, [typeFilter])

  async function runSearch(e) {
    e.preventDefault()
    if (!query.trim()) { loadRecent(); return }
    setLoading(true)
    const params = new URLSearchParams({ q: query })
    if (typeFilter) params.set('type', typeFilter)
    const res = await fetch(`${API_BASE}/kb/search?${params}`)
    const data = await res.json()
    setEntries(data.results)
    setLoading(false)
  }

  async function handleSave(e) {
    e.preventDefault()
    if (!form.title.trim() || !form.content.trim()) return
    setSaving(true)
    await fetch(`${API_BASE}/kb/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    setForm(EMPTY_FORM)
    setSaving(false)
    setShowForm(false)
    setQuery('')
    loadRecent()
  }

  async function handleDelete(id) {
    await fetch(`${API_BASE}/kb/${id}`, { method: 'DELETE' })
    setEntries(prev => prev.filter(e => e.id !== id))
  }

  return (
    <div className="vault">
      <div className="vault-toolbar">
        <form className="vault-search" onSubmit={runSearch}>
          <span className="prompt-glyph">&gt;</span>
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search your commands, notes, payloads..."
          />
          <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
            <option value="">All types</option>
            {TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <button type="submit" className="send-btn">search</button>
        </form>
        <button className="vault-add-btn" onClick={() => setShowForm(s => !s)}>
          {showForm ? 'cancel' : '+ add entry'}
        </button>
      </div>

      {showForm && (
        <form className="vault-form" onSubmit={handleSave}>
          <div className="vault-form-row">
            <select value={form.type} onChange={e => setForm({ ...form, type: e.target.value })}>
              {TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
            <select value={form.phase} onChange={e => setForm({ ...form, phase: e.target.value })}>
              {PHASES.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
            <input
              placeholder="target / engagement (optional)"
              value={form.target}
              onChange={e => setForm({ ...form, target: e.target.value })}
            />
          </div>
          <input
            className="vault-title-input"
            placeholder="Title, e.g. 'gobuster with common wordlist'"
            value={form.title}
            onChange={e => setForm({ ...form, title: e.target.value })}
          />
          <textarea
            placeholder="Command, note, or payload content..."
            rows={4}
            value={form.content}
            onChange={e => setForm({ ...form, content: e.target.value })}
          />
          <input
            placeholder="tags, comma separated e.g. subdomain, enum, ffuf"
            value={form.tags}
            onChange={e => setForm({ ...form, tags: e.target.value })}
          />
          <button type="submit" className="send-btn" disabled={saving}>
            {saving ? 'saving...' : 'save to vault'}
          </button>
        </form>
      )}

      <div className="vault-list">
        {loading && <div className="vault-empty">loading...</div>}
        {!loading && entries.length === 0 && (
          <div className="vault-empty">No entries yet. Add your first command, note, or payload above.</div>
        )}
        {!loading && entries.map(entry => (
          <EntryCard entry={entry} onDelete={handleDelete} key={entry.id} />
        ))}
      </div>
    </div>
  )
}
