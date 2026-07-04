import React, { useEffect, useRef, useState } from 'react'

const API_BASE = 'http://localhost:8000'

function MemoryPanel({ refreshKey, onChanged }) {
  const [items, setItems] = useState([])
  const [teachText, setTeachText] = useState('')
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)

  async function load() {
    const [memRes, fileRes] = await Promise.all([
      fetch(`${API_BASE}/memory/list`).then(r => r.json()),
      fetch(`${API_BASE}/memory/files`).then(r => r.json()),
    ])
    setItems(memRes.results)
    setFiles(fileRes.results)
  }

  useEffect(() => { load() }, [refreshKey])

  async function teach(e) {
    e.preventDefault()
    if (!teachText.trim()) return
    await fetch(`${API_BASE}/memory/teach`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: teachText }),
    })
    setTeachText('')
    load()
    onChanged?.()
  }

  async function deleteMemory(id) {
    await fetch(`${API_BASE}/memory/${id}`, { method: 'DELETE' })
    setItems(prev => prev.filter(i => i.id !== id))
  }

  async function handleUpload(e) {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    await fetch(`${API_BASE}/memory/upload`, { method: 'POST', body: formData })
    setUploading(false)
    e.target.value = ''
    load()
    onChanged?.()
  }

  async function deleteFile(filename) {
    await fetch(`${API_BASE}/memory/files/${encodeURIComponent(filename)}`, { method: 'DELETE' })
    setFiles(prev => prev.filter(f => f.filename !== filename))
  }

  return (
    <div className="vault">
      <form className="vault-form" onSubmit={teach} style={{ marginBottom: 0 }}>
        <div className="rail-section-label" style={{ marginBottom: 0 }}>Teach it something</div>
        <textarea
          placeholder="e.g. I prefer short, direct answers. My exams start in August."
          rows={2}
          value={teachText}
          onChange={e => setTeachText(e.target.value)}
        />
        <button type="submit" className="send-btn">remember this</button>
      </form>

      <div>
        <div className="rail-section-label">Uploaded files</div>
        <label className="vault-add-btn" style={{ display: 'inline-block', cursor: 'pointer' }}>
          {uploading ? 'uploading...' : '+ upload file'}
          <input type="file" accept=".txt,.md,.py,.js,.jsx,.json,.csv" onChange={handleUpload} style={{ display: 'none' }} />
        </label>
        <div className="vault-list" style={{ marginTop: 10 }}>
          {files.length === 0 && <div className="vault-empty">No files uploaded yet.</div>}
          {files.map(f => (
            <div className="vault-card" key={f.filename}>
              <div className="vault-card-top">
                <span className="vault-badge vault-badge-note">file</span>
                <span className="vault-title" style={{ margin: 0 }}>{f.filename}</span>
                <span className="vault-phase" style={{ marginLeft: 'auto' }}>{f.chunks} chunks</span>
                <button className="vault-delete" onClick={() => deleteFile(f.filename)}>✕</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="rail-section-label">Long-term memory ({items.length})</div>
        <div className="vault-list">
          {items.length === 0 && <div className="vault-empty">Nothing remembered yet — teach it something or just keep chatting.</div>}
          {items.map(item => (
            <div className="vault-card" key={item.id}>
              <div className="vault-card-top">
                <span className={`vault-badge ${item.source === 'auto' ? 'vault-badge-command' : 'vault-badge-note'}`}>
                  {item.source}
                </span>
                <button className="vault-delete" onClick={() => deleteMemory(item.id)}>✕</button>
              </div>
              <div className="vault-content" style={{ marginBottom: 0 }}>{item.text}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function AssistantMode({ mode, setMode }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('chat')
  const [memoryVersion, setMemoryVersion] = useState(0)
  const [memCount, setMemCount] = useState(null)
  const threadRef = useRef(null)

  useEffect(() => {
    fetch(`${API_BASE}/memory/list`).then(r => r.json()).then(d => setMemCount(d.results.length)).catch(() => {})
  }, [memoryVersion])

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, loading])

  async function ask(question) {
    if (!question.trim() || loading) return
    setError(null)
    setInput('')
    const history = messages.map(m => ({ role: m.role, content: m.text }))
    setMessages(prev => [...prev, { role: 'user', text: question }])
    setLoading(true)

    try {
      const res = await fetch(`${API_BASE}/assistant/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: question, history }),
      })
      if (!res.ok) throw new Error(`Server responded ${res.status}`)
      const data = await res.json()
      setMessages(prev => [...prev, { role: 'assistant', text: data.answer, remembered: data.newly_remembered }])
      if (data.newly_remembered?.length) setMemoryVersion(v => v + 1)
    } catch (e) {
      setError('Could not reach the API. Is uvicorn running on port 8000?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="shell">
      <aside className="rail">
        <div className="brand">
          <span className="brand-mark" />
          <div>
            <div className="brand-name">CYBER-RAG</div>
            <div className="brand-sub">personal assistant</div>
          </div>
        </div>

        <div className="mode-switch">
          <button className={`mode-btn ${mode === 'cyber' ? 'active' : ''}`} onClick={() => setMode('cyber')}>Cyber Mode</button>
          <button className={`mode-btn ${mode === 'assistant' ? 'active' : ''}`} onClick={() => setMode('assistant')}>Assistant Mode</button>
        </div>

        <div>
          <div className="rail-section-label">Memory</div>
          <div className="stat-row">
            <span>facts remembered</span>
            <b>{memCount ?? '—'}</b>
          </div>
        </div>
      </aside>

      <main className="console">
        <div className="console-header">
          <div className="console-title">
            ASSISTANT <span>MODE</span>
          </div>
          <div className="tabs">
            <button className={`tab-btn ${tab === 'chat' ? 'active' : ''}`} onClick={() => setTab('chat')}>Chat</button>
            <button className={`tab-btn ${tab === 'memory' ? 'active' : ''}`} onClick={() => setTab('memory')}>Memory</button>
          </div>
        </div>

      {tab === 'memory' && <MemoryPanel refreshKey={memoryVersion} onChanged={() => setMemoryVersion(v => v + 1)} />}

      {tab === 'chat' && <>
        <div className="thread" ref={threadRef}>
          {messages.length === 0 && !loading && (
            <div className="empty-state">
              <div className="glyph">&gt;_</div>
              <h2>Your personal assistant</h2>
              <p>
                Ask about anything — your projects, coursework, or just talk things through.
                It remembers facts worth keeping as you go, and you can teach or upload files
                in the Memory tab.
              </p>
            </div>
          )}

          {messages.map((m, i) => (
            <div className={`msg ${m.role}`} key={i}>
              <div className="msg-label">{m.role === 'user' ? 'you' : 'assistant'}</div>
              <div className="msg-bubble">{m.text}</div>
              {m.remembered && m.remembered.length > 0 && (
                <div className="sources">
                  <div className="sources-label vault-sources-label">Remembered from this</div>
                  {m.remembered.map((f, j) => (
                    <div className="source-card" key={j}><span className="source-title">{f}</span></div>
                  ))}
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="scan">
              <div className="scan-line" />
              <div className="scan-text">thinking...</div>
            </div>
          )}
        </div>

        <div className="input-bar">
          <div className="input-row">
            <span className="prompt-glyph">&gt;</span>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') ask(input) }}
              placeholder="Ask me anything..."
              disabled={loading}
            />
            <button className="send-btn" onClick={() => ask(input)} disabled={loading || !input.trim()}>
              {loading ? 'thinking' : 'send'}
            </button>
          </div>
          {error && <div className="error-banner">{error}</div>}
        </div>
      </>}
      </main>
    </div>
  )
}
