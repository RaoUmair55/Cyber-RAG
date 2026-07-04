import React, { useEffect, useRef, useState } from 'react'
import Vault from './Vault.jsx'
import './App.css'

const API_BASE = 'http://localhost:8000'

const SUGGESTIONS = [
  'How does SQL Injection work?',
  'Which attacks target cloud infrastructure?',
  'How do I detect a ransomware attack early?',
]

function ScanIndicator({ recordCount }) {
  return (
    <div className="scan" role="status" aria-live="polite">
      <div className="scan-line" />
      <div className="scan-text">
        searching vector index &middot;{' '}
        <b>{recordCount ? recordCount.toLocaleString() : '—'} records</b>
      </div>
    </div>
  )
}

function SourceCard({ source }) {
  const pct = Math.round(source.similarity * 100)
  return (
    <div className="source-card">
      <span className="source-title">{source.title}</span>
      <span className="source-type">{source.attack_type}</span>
      <div className="source-sim">
        <div className="source-sim-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="source-sim-pct">{pct}%</span>
    </div>
  )
}

export default function CyberMode({ mode, setMode }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [stats, setStats] = useState(null)
  const [filterOptions, setFilterOptions] = useState(null)
  const [filters, setFilters] = useState({ category: '', attack_type: '', target_type: '' })
  const [tab, setTab] = useState('console')
  const threadRef = useRef(null)

  useEffect(() => {
    fetch(`${API_BASE}/stats`).then(r => r.json()).then(setStats).catch(() => {})
    fetch(`${API_BASE}/filters`).then(r => r.json()).then(setFilterOptions).catch(() => {})
  }, [])

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, loading])

  async function ask(question) {
    if (!question.trim() || loading) return
    setError(null)
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: question }])
    setLoading(true)

    const body = { question, top_k: 5 }
    Object.entries(filters).forEach(([k, v]) => { if (v) body[k] = v })

    try {
      const res = await fetch(`${API_BASE}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`Server responded ${res.status}`)
      const data = await res.json()
      setMessages(prev => [...prev, {
        role: 'assistant', text: data.answer, sources: data.sources, vaultSources: data.vault_sources,
      }])
    } catch (e) {
      setError('Could not reach the API. Is uvicorn running on port 8000?')
    } finally {
      setLoading(false)
    }
  }

  function updateFilter(key, value) {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  return (
    <div className="shell">
      <aside className="rail">
        <div className="brand">
          <span className="brand-mark" />
          <div>
            <div className="brand-name">CYBER-RAG</div>
            <div className="brand-sub">threat intel console</div>
          </div>
        </div>

        <div className="mode-switch">
          <button className={`mode-btn ${mode === 'cyber' ? 'active' : ''}`} onClick={() => setMode('cyber')}>Cyber Mode</button>
          <button className={`mode-btn ${mode === 'assistant' ? 'active' : ''}`} onClick={() => setMode('assistant')}>Assistant Mode</button>
        </div>

        <div>
          <div className="rail-section-label">Index</div>
          <div className="stat-row">
            <span>records</span>
            <b>{stats ? stats.total_records.toLocaleString() : '—'}</b>
          </div>
        </div>

        {stats && (
          <div>
            <div className="rail-section-label">Top attack types</div>
            {stats.top_attack_types.slice(0, 6).map(item => {
              const max = stats.top_attack_types[0].count
              return (
                <div className="bar-item" key={item.label}>
                  <div className="bar-label">
                    <span>{item.label}</span>
                    <span>{item.count}</span>
                  </div>
                  <div className="bar-track">
                    <div className="bar-fill" style={{ width: `${(item.count / max) * 100}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {filterOptions && (
          <div>
            <div className="rail-section-label">Filter query</div>
            <div className="filter-group">
              <label>Category</label>
              <select value={filters.category} onChange={e => updateFilter('category', e.target.value)}>
                <option value="">All</option>
                {filterOptions.categories.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="filter-group">
              <label>Attack type</label>
              <select value={filters.attack_type} onChange={e => updateFilter('attack_type', e.target.value)}>
                <option value="">All</option>
                {filterOptions.attack_types.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="filter-group">
              <label>Target type</label>
              <select value={filters.target_type} onChange={e => updateFilter('target_type', e.target.value)}>
                <option value="">All</option>
                {filterOptions.target_types.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            {(filters.category || filters.attack_type || filters.target_type) && (
              <button
                className="clear-filters"
                onClick={() => setFilters({ category: '', attack_type: '', target_type: '' })}
              >
                clear filters
              </button>
            )}
          </div>
        )}
      </aside>

      <main className="console">
        <div className="console-header">
          <div className="console-title">
            QUERY <span>CONSOLE</span>
          </div>
          <div className="tabs">
            <button className={`tab-btn ${tab === 'console' ? 'active' : ''}`} onClick={() => setTab('console')}>
              Console
            </button>
            <button className={`tab-btn ${tab === 'vault' ? 'active' : ''}`} onClick={() => setTab('vault')}>
              Vault
            </button>
          </div>
        </div>

        {tab === 'vault' && <Vault />}

        {tab === 'console' && <>
        <div className="thread" ref={threadRef}>
          {messages.length === 0 && !loading && (
            <div className="empty-state">
              <div className="glyph">&gt;_</div>
              <h2>Ask about any attack in the index</h2>
              <p>
                Answers are generated only from the {stats ? stats.total_records.toLocaleString() : ''} records
                in the dataset — retrieval first, then grounded generation.
              </p>
              {SUGGESTIONS.map(s => (
                <span key={s} className="suggestion-chip" onClick={() => ask(s)}>{s}</span>
              ))}
            </div>
          )}

          {messages.map((m, i) => (
            <div className={`msg ${m.role}`} key={i}>
              <div className="msg-label">{m.role === 'user' ? 'query' : 'response'}</div>
              <div className="msg-bubble">{m.text}</div>
              {m.sources && m.sources.length > 0 && (
                <div className="sources">
                  <div className="sources-label">Matched records ({m.sources.length})</div>
                  {m.sources.map((s, j) => <SourceCard source={s} key={j} />)}
                </div>
              )}
              {m.vaultSources && m.vaultSources.length > 0 && (
                <div className="sources">
                  <div className="sources-label vault-sources-label">From your Vault ({m.vaultSources.length})</div>
                  {m.vaultSources.map((v, j) => (
                    <div className="source-card" key={j}>
                      <span className={`vault-badge vault-badge-${v.type}`}>{v.type}</span>
                      <span className="source-title">{v.title}</span>
                      <span className="source-sim-pct">{Math.round(v.similarity * 100)}%</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}

          {loading && <ScanIndicator recordCount={stats?.total_records} />}
        </div>

        <div className="input-bar">
          <div className="input-row">
            <span className="prompt-glyph">&gt;</span>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') ask(input) }}
              placeholder="Ask about an attack, e.g. how is phishing detected?"
              disabled={loading}
            />
            <button className="send-btn" onClick={() => ask(input)} disabled={loading || !input.trim()}>
              {loading ? 'searching' : 'ask'}
            </button>
          </div>
          {error && <div className="error-banner">{error}</div>}
        </div>
        </>}
      </main>
    </div>
  )
}
