import { useState } from 'react'

// Tiny formatter for model replies: **bold** and "* " or "- " bullet lines.
function bold(line) {
  return line.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**')
      ? <strong key={i}>{part.slice(2, -2)}</strong>
      : part)
}

function Reply({ text }) {
  const out = []
  let items = []
  const flush = () => {
    if (items.length) out.push(<ul key={`u${out.length}`}>{items}</ul>)
    items = []
  }
  text.split('\n').forEach((raw, i) => {
    const line = raw.trim()
    if (/^[*-] /.test(line)) {
      items.push(<li key={i}>{bold(line.slice(2))}</li>)
    } else {
      flush()
      if (line) out.push(<p key={i}>{bold(line)}</p>)
    }
  })
  flush()
  return out
}

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
      const text = await r.text()
      let data
      try {
        data = JSON.parse(text)
      } catch {
        data = { error: `The assistant did not answer in time (HTTP ${r.status}). Try again.` }
      }
      const reply = data.answer || data.error || 'No answer.'
      setMsgs([...next, { role: 'assistant', content: reply, steps: data.steps || [], model: data.model }])
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
            {m.role === 'assistant' ? <Reply text={m.content} /> : <p>{m.content}</p>}
            {m.steps?.length > 0 && (
              <small>Tools used: {m.steps.map(s => s.tool).join(' → ')}</small>
            )}
            {m.model && <small>Model: {m.model}</small>}
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
