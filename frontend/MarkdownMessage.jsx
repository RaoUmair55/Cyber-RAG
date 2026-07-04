import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

function CodeBlock({ className, children }) {
  const [copied, setCopied] = useState(false)
  const lang = (className || '').replace('language-', '') || 'text'
  const code = String(children).replace(/\n$/, '')

  function copy() {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="md-codeblock">
      <div className="md-codeblock-top">
        <span className="md-lang">{lang}</span>
        <button className="md-copy-btn" onClick={copy}>{copied ? 'copied' : 'copy'}</button>
      </div>
      <pre><code>{code}</code></pre>
    </div>
  )
}

// Detects a leading keyword in a blockquote and turns it into a colored
// callout box with an icon, the way "> **Warning:** ..." reads better as
// a flagged box than as a plain indented quote.
const CALLOUT_PATTERNS = [
  { re: /^(warning|danger|caution)[:\s]/i, type: 'danger', icon: '!' },
  { re: /^(note|info)[:\s]/i, type: 'info', icon: 'i' },
  { re: /^tip[:\s]/i, type: 'tip', icon: '\u2713' },
  { re: /^important[:\s]/i, type: 'important', icon: '\u2605' },
]

function flattenText(children) {
  return React.Children.toArray(children)
    .map(c => {
      if (typeof c === 'string') return c
      if (c?.props?.children) return flattenText(c.props.children)
      return ''
    })
    .join(' ')
}

function Callout({ children }) {
  const flat = flattenText(children).trim()
  const match = CALLOUT_PATTERNS.find(p => p.re.test(flat))

  if (!match) {
    return <blockquote className="md-callout md-callout-default">{children}</blockquote>
  }
  return (
    <blockquote className={`md-callout md-callout-${match.type}`}>
      <span className="md-callout-icon">{match.icon}</span>
      <div className="md-callout-body">{children}</div>
    </blockquote>
  )
}

function TableWrapper({ children }) {
  return (
    <div className="md-table-wrap">
      <table>{children}</table>
    </div>
  )
}

/**
 * Renders LLM output as formatted, styled markdown — headers, lists,
 * callout boxes for notes/warnings/tips, card-style tables, and code
 * blocks with copy buttons.
 */
export default function MarkdownMessage({ content }) {
  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ inline, className, children }) {
            if (inline) return <code className="md-inline-code">{children}</code>
            return <CodeBlock className={className}>{children}</CodeBlock>
          },
          blockquote({ children }) {
            return <Callout>{children}</Callout>
          },
          table({ children }) {
            return <TableWrapper>{children}</TableWrapper>
          },
          a({ href, children }) {
            return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}