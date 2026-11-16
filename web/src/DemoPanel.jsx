import { useEffect, useState } from 'react'

const NAMES = {
  stuck_damper: 'Stuck damper',
  sensor_drift: 'Drifting supply sensor',
  fan_off: 'Fan off while occupied',
  high_co2: 'Poor ventilation (CO₂)',
}

function secs(n) {
  return n < 90 ? `${Math.round(n)} s` : `${Math.floor(n / 60)} min ${Math.round(n % 60)} s`
}

export default function DemoPanel({ demo, found, onChange }) {
  const [zone, setZone] = useState(2)
  const [kind, setKind] = useState('fan_off')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  async function send(z, fault) {
    setBusy(true)
    setMsg('')
    try {
      const r = await fetch(`/api/demo/faults/${z}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fault }),
      })
      if (!r.ok) throw new Error(`the API returned ${r.status}`)
      onChange()
    } catch (e) {
      setMsg(`Couldn't change zone ${z}: ${e.message}`)
    }
    setBusy(false)
  }

  return (
    <section className="demo">
      <div className="demo-head">
        <h2>Break something</h2>
        <p className="quiet">Switch a fault on in the simulated building, then watch the system find it on its own.</p>
      </div>

      <form className="demo-form" onSubmit={e => { e.preventDefault(); send(zone, kind) }}>
        <label htmlFor="demo-zone">Zone</label>
        <select id="demo-zone" value={zone} onChange={e => setZone(Number(e.target.value))}>
          {[1, 2, 3, 4, 5, 6].map(z => <option key={z} value={z}>{z}</option>)}
        </select>
        <label htmlFor="demo-kind">Fault</label>
        <select id="demo-kind" value={kind} onChange={e => setKind(e.target.value)}>
          {Object.entries(NAMES).map(([k, n]) => <option key={k} value={k}>{n}</option>)}
        </select>
        <button disabled={busy}>Break zone {zone}</button>
      </form>
      {msg && <p className="demo-err">{msg}</p>}

      {demo.length > 0 && (
        <ul className="demo-list">
          {demo.map(d => {
            const key = `${d.zone}:${d.fault}:${d.set_at}`
            const hit = found[key]
            const age = (now - Date.parse(d.set_at)) / 1000
            return (
              <li key={key}>
                <div>
                  <b>Zone {d.zone} · {NAMES[d.fault] || d.fault}</b>
                  <span className={hit ? 'caught' : 'waiting'}>
                    {hit == null && `Watching for it… ${secs(age)}`}
                    {hit === 'seen' && 'Detected'}
                    {typeof hit === 'number' && `Detected after ${secs(hit)}`}
                  </span>
                </div>
                <button type="button" className="fix" disabled={busy} onClick={() => send(d.zone, null)}>Fix</button>
              </li>
            )
          })}
        </ul>
      )}
      <p className="demo-foot">Rules wait for enough readings to be sure, so detection takes about 1 to 3 minutes. A fixed zone clears once its window is clean.</p>
    </section>
  )
}
