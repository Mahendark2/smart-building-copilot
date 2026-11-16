import { useEffect, useRef, useState } from 'react'
import Plan from './Plan.jsx'
import Building3D from './Building3D.jsx'
import DemoPanel from './DemoPanel.jsx'
import ZoneDetail from './ZoneDetail.jsx'
import Faults from './Faults.jsx'
import Chat from './Chat.jsx'

// which detected fault proves each demo fault was caught
const CATCHES = {
  stuck_damper: 'stuck_damper',
  sensor_drift: 'supply_sensor_drift',
  fan_off: 'fan_off_while_occupied',
  high_co2: 'high_co2',
}

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
  const [pick, setPick] = useState(null)
  const [view, setView] = useState('3d')
  const [demo, setDemo] = useState([])
  const [found, setFound] = useState({})
  const first = useRef(true)

  async function load() {
    try {
      const [[pts, h], [f], [dm]] = await Promise.all(
        [getJson('/api/points'), getJson('/api/faults'), getJson('/api/demo/faults')])
      setPoints(pts)
      setFaults(f.faults)
      setDemo(dm.faults)
      const isFirst = first.current
      setFound(old => {
        const next = { ...old }
        for (const d of dm.faults) {
          const key = `${d.zone}:${d.fault}:${d.set_at}`
          if (next[key] != null) continue
          if (f.faults.some(x => x.zone === d.zone && x.type === CATCHES[d.fault])) {
            // on the first load we don't know when it was caught, only that it was
            next[key] = isFirst ? 'seen' : (Date.now() - Date.parse(d.set_at)) / 1000
          }
        }
        return next
      })
      first.current = false
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
  for (const p of points) (zones[p.zone] ||= {})[p.kind] = p.value
  const serious = faults.filter(f => f.severity !== 'low')
  const hurt = [...new Set(serious.map(f => f.zone))].sort()
  const zone = pick ?? hurt[0] ?? 1

  let status = 'Waiting for the first readings'
  if (points.length) {
    status = hurt.length === 0
      ? 'All zones running normally'
      : `${hurt.length === 1 ? 'Zone' : 'Zones'} ${hurt.length > 1 ? `${hurt.slice(0, -1).join(', ')} and ${hurt.at(-1)}` : hurt[0]} ${hurt.length === 1 ? 'needs' : 'need'} attention`
  }

  return (
    <div className="page">
      <header className="top">
        <div>
          <h1>Smart Building Copilot</h1>
          <p className={`status ${hurt.length ? 'warn' : ''}`}>{status}</p>
        </div>
        <div className="meta">
          {updated && <span>Updated {updated.toLocaleTimeString()}</span>}
          {host && <span>Served by {host}</span>}
        </div>
      </header>

      {err && <div className="error">The dashboard can't reach the building API ({err}). It will retry every 5 seconds.</div>}

      <div className="layout">
        <main>
          <section className="plan-wrap">
            <div className="view-switch" role="group" aria-label="Building view">
              <button type="button" aria-pressed={view === '3d'} onClick={() => setView('3d')}>3D</button>
              <button type="button" aria-pressed={view === 'plan'} onClick={() => setView('plan')}>Plan</button>
            </div>
            {view === '3d'
              ? <Building3D zones={zones} faults={serious} pick={zone} onPick={setPick} />
              : <Plan zones={zones} faults={serious} pick={zone} onPick={setPick} />}
            <div className="legend" aria-hidden="true">
              <span>Cooler than setpoint</span>
              <i />
              <span>Warmer</span>
            </div>
          </section>
          <DemoPanel demo={demo} found={found} onChange={load} />
          <div className="below">
            <ZoneDetail zone={zone} values={zones[zone] || {}} faults={faults.filter(f => f.zone === zone)} />
            <Faults faults={faults} onPick={setPick} />
          </div>
        </main>
        <Chat />
      </div>
    </div>
  )
}
