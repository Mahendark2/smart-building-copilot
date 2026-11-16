import { useEffect, useState } from 'react'

const ROWS = [
  ['supply_air_temp', 'Supply air', '°C'],
  ['return_air_temp', 'Return air', '°C'],
  ['humidity', 'Humidity', '%'],
  ['co2', 'CO₂', ' ppm'],
  ['damper_pos', 'Damper', '%'],
  ['valve_pos', 'Cooling valve', '%'],
  ['fan_speed', 'Fan speed', '%'],
  ['occupied', 'Occupied', ''],
]

function show(k, v, u) {
  if (v == null) return '--'
  if (k === 'occupied') return v ? 'Yes' : 'No'
  return `${v.toFixed(k === 'co2' ? 0 : 1)}${u}`
}

// small line chart; a dashed line marks the setpoint when there is one
function Spark({ data, line, label, unit }) {
  if (data.length < 2) return <div className="spark empty">Collecting readings…</div>
  const vals = data.map(r => r.value)
  const lo = Math.min(...vals, line ?? Infinity) - 0.3
  const hi = Math.max(...vals, line ?? -Infinity) + 0.3
  const x = i => (i / (data.length - 1)) * 300
  const y = v => 70 - ((v - lo) / (hi - lo)) * 64
  const d = vals.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ')
  const last = vals.at(-1)
  return (
    <div className="spark">
      <div className="spark-head">
        <span>{label}</span>
        <b>{last.toFixed(1)}{unit}</b>
      </div>
      <svg viewBox="0 0 300 74" preserveAspectRatio="none" aria-label={`${label}, last 30 minutes`}>
        {line != null && <line x1="0" x2="300" y1={y(line)} y2={y(line)} className="sp" />}
        <path d={d} className="trace" />
      </svg>
    </div>
  )
}

export default function ZoneDetail({ zone, values, faults }) {
  const [temp, setTemp] = useState([])
  const [supply, setSupply] = useState([])

  useEffect(() => {
    let live = true
    async function load() {
      try {
        const get = n => fetch(`/api/points/zone${zone}.${n}/history?minutes=30`).then(r => r.json())
        const [a, b] = await Promise.all([get('zone_temp'), get('supply_air_temp')])
        if (live) { setTemp(a.readings || []); setSupply(b.readings || []) }
      } catch { /* the main page already shows API errors */ }
    }
    load()
    const id = setInterval(load, 10000)
    return () => { live = false; clearInterval(id) }
  }, [zone])

  return (
    <section className="detail">
      <h2>Zone {zone}</h2>
      {faults.length > 0
        ? <p className="detail-note alarm-text">{faults.length === 1 ? '1 fault' : `${faults.length} faults`} in this zone</p>
        : <p className="detail-note">Running normally</p>}
      <div className="sparks">
        <Spark data={temp} line={values.cool_setpoint} label="Room temperature" unit="°C" />
        <Spark data={supply} label="Supply air" unit="°C" />
      </div>
      <p className="spark-foot">Last 30 minutes · dashed line is the cooling setpoint</p>
      <dl className="readings">
        {ROWS.map(([k, name, u]) => (
          <div key={k}>
            <dt>{name}</dt>
            <dd>{show(k, values[k], u)}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
