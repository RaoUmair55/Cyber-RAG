import React, { useEffect, useRef, useState } from 'react'
import { MemoryPanel } from './AssistantMode.jsx'
import MarkdownMessage from './MarkdownMessage.jsx'

const API_BASE = 'http://localhost:8000'

const SOURCE_LABELS = {
  attacks: 'Attack dataset',
  vault: 'Your Vault',
  memory: 'What I know about you',
  documents: 'Uploaded documents',
}

function SourceGroup({ label, items, renderLabel }) {
  if (!items || items.length === 0) return null
  return (
    <div className="sources">
      <div className="sources-label">{label} ({items.length})</div>
      {items.map((item, j) => (
        <div className="source-card" key={j}>
          <span className="source-title">{renderLabel(item)}</span>
          <span className="source-sim-pct">{Math.round(item.similarity * 100)}%</span>
        </div>
      ))}
    </div>
  )
}

export default function SuperMode({ mode, setMode }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('chat')
  const [memoryVersion, setMemoryVersion] = useState(0)
  const threadRef = useRef(null)

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
      const res = await fetch(`${API_BASE}/super/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: question, history }),
      })
      if (!res.ok) throw new Error(`Server responded ${res.status}`)
      const data = await res.json()
      setMessages(prev => [...prev, {
        role: 'assistant', text: data.answer, sources: data.sources, remembered: data.newly_remembered,
      }])
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
            <div className="brand-sub">super assistant</div>
          </div>
        </div>

        <div className="mode-switch mode-switch-3">
          <button className={`mode-btn ${mode === 'cyber' ? 'active' : ''}`} onClick={() => setMode('cyber')}>Cyber</button>
          <button className={`mode-btn ${mode === 'assistant' ? 'active' : ''}`} onClick={() => setMode('assistant')}>Assistant</button>
          <button className={`mode-btn ${mode === 'super' ? 'active' : ''}`} onClick={() => setMode('super')}>Super</button>
        </div>

        <div>
          <div className="rail-section-label">Sources searched</div>
          <div className="stat-row"><span>attack dataset</span></div>
          <div className="stat-row"><span>your vault</span></div>
          <div className="stat-row"><span>your memory</span></div>
          <div className="stat-row"><span>uploaded documents</span></div>
        </div>
      </aside>

      <main className="console">
        <div className="console-header">
          <div className="console-title">SUPER <span>ASSISTANT</span></div>
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
                <h2>One assistant, everything combined</h2>
                <p>
                  Ask about an attack, a tool you uploaded docs for, your own notes, or just
                  talk normally — it searches the attack dataset, your Vault, your memory, and
                  uploaded documents, and blends whatever's actually relevant.
                </p>
              </div>
            )}

            {messages.map((m, i) => (
              <div className={`msg ${m.role}`} key={i}>
                <div className="msg-label">{m.role === 'user' ? 'you' : 'assistant'}</div>
                <div className="msg-bubble">
                  {m.role === 'assistant' ? <MarkdownMessage content={m.text} /> : m.text}
                </div>

                {m.sources && (
                  <>
                    <SourceGroup label={SOURCE_LABELS.attacks} items={m.sources.attacks} renderLabel={s => s.title} />
                    <SourceGroup label={SOURCE_LABELS.vault} items={m.sources.vault} renderLabel={s => `[${s.type}] ${s.title}`} />
                    <SourceGroup label={SOURCE_LABELS.memory} items={m.sources.memory} renderLabel={s => s.text} />
                    <SourceGroup label={SOURCE_LABELS.documents} items={m.sources.documents} renderLabel={s => s.filename} />
                  </>
                )}

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
                <div className="scan-text">searching all sources...</div>
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
                placeholder="Ask anything — attacks, tools, your notes, or just talk..."
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
