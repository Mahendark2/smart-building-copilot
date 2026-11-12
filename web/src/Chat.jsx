import { useState } from 'react'

const EXAMPLES = [
  'Are there any faults right now?',
  'Why is zone 3 so warm?',
  'How has the zone 5 supply air temperature changed in the last 30 minutes?',
]

export default function Chat() {
  const [msgs, setMsgs] = useState([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)

  async function send(q) {
    const question = (q ?? text).trim()
    if (!question || busy) return
    const next = [...msgs, { role: 'user', content: question }]
    setMsgs(next)
    setText('')
    setBusy(true)
    try {
      const r = await fetch('/assistant/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: next.map(({ role, content }) => ({ role, content })) }),
      })
      const data = await r.json()
      const reply = data.answer || data.error || 'No answer.'
      setMsgs([...next, { role: 'assistant', content: reply, steps: data.steps || [] }])
    } catch (e) {
      setMsgs([...next, { role: 'assistant', content: `Could not reach the assistant: ${e.message}` }])
    }
    setBusy(false)
  }

  return (
    <aside className="chat">
      <h2>Ask the copilot</h2>
      <div className="msgs">
        {msgs.length === 0 && (
          <div className="examples">
            {EXAMPLES.map(e => <button key={e} onClick={() => send(e)}>{e}</button>)}
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <p>{m.content}</p>
            {m.steps?.length > 0 && (
              <small>Tools used: {m.steps.map(s => s.tool).join(' → ')}</small>
            )}
          </div>
        ))}
        {busy && <div className="msg assistant"><p>Checking the building…</p></div>}
      </div>
      <form onSubmit={e => { e.preventDefault(); send() }}>
        <input value={text} onChange={e => setText(e.target.value)} placeholder="Ask about any zone…" />
        <button disabled={busy}>Send</button>
      </form>
    </aside>
  )
}
