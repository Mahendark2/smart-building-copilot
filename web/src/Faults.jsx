const NAMES = {
  stuck_damper: 'Stuck damper',
  fan_off_while_occupied: 'Fan off while occupied',
  supply_sensor_drift: 'Supply sensor drift',
  high_co2: 'High CO2',
  too_warm: 'Too warm',
  ml_anomaly: 'Unusual behaviour (ML)',
}

export default function Faults({ faults }) {
  return (
    <section className="faults">
      <h2>Active faults <span className="count">{faults.length}</span></h2>
      {faults.length === 0 && <p className="ok">No faults right now.</p>}
      <ul>
        {faults.map((f, i) => (
          <li key={i} className={f.severity}>
            <div className="fault-top">
              <strong>Zone {f.zone}: {NAMES[f.type] || f.type}</strong>
              <span className="tag">{f.source === 'rule' ? 'rule' : 'ML'} · {f.severity}</span>
            </div>
            <p>{f.detail}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}
