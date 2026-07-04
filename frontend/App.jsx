import React, { useState } from 'react'
import CyberMode from './CyberMode.jsx'
import AssistantMode from './AssistantMode.jsx'
import SuperMode from './SuperMode.jsx'
import './App.css'

export default function App() {
  const [mode, setMode] = useState('cyber')
  if (mode === 'assistant') return <AssistantMode mode={mode} setMode={setMode} />
  if (mode === 'super') return <SuperMode mode={mode} setMode={setMode} />
  return <CyberMode mode={mode} setMode={setMode} />
}
