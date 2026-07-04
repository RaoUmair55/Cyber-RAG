import React, { useState } from 'react'
import CyberMode from './CyberMode.jsx'
import AssistantMode from './AssistantMode.jsx'
import './App.css'

export default function App() {
  const [mode, setMode] = useState('cyber')
  return mode === 'cyber'
    ? <CyberMode mode={mode} setMode={setMode} />
    : <AssistantMode mode={mode} setMode={setMode} />
}
