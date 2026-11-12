import { useEffect, useState } from 'react'
import Zone from './Zone.jsx'
import Faults from './Faults.jsx'
import Chat from './Chat.jsx'

async function getJson(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${url} returned ${r.status}`)
  return [await r.json(), r.headers.get('X-Served-By')]
}

export default function App() {
  const [points, setPoints] = useState([])
  const [faults, setFaults] = useState([])
  const [host, setHost] = useState('')
  const [err, setErr] = useState('')
  const [updated, setUpdated] = useState(null)

  async function load() {
    try {
      const [[pts, h], [f]] = await Promise.all([getJson('/api/points'), getJson('/api/faults')])
      setPoints(pts)
      setFaults(f.faults)
      setHost(h)
      setUpdated(new Date())
      setErr('')
    } catch (e) {
      setErr(e.message)
    }
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [])

  const zones = {}
  for (const p of points) (zones[p.zone] ||= []).push(p)
  const faultZones = new Set(faults.filter(f => f.severity !== 'low').map(f => f.zone))

  return (
    <div className="page">
      <header>
        <div>
          <h1>Smart Building Copilot</h1>
          <p className="sub">72 HVAC points from a simulated BACnet/IP controller</p>
        </div>
        <div className="meta">
          {updated && <span>Updated {updated.toLocaleTimeString()}</span>}
          {host && <span>API copy: {host}</span>}
        </div>
      </header>

      {err && <div className="error">Cannot reach the API: {err}</div>}

      <div className="layout">
        <main>
          <Faults faults={faults} />
          <div className="zones">
            {Object.entries(zones).map(([z, pts]) => (
              <Zone key={z} zone={z} points={pts} hasFault={faultZones.has(Number(z))} />
            ))}
          </div>
        </main>
        <Chat />
      </div>
    </div>
  )
}
