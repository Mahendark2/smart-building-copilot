const NAMES = {
  stuck_damper: 'Stuck damper',
  fan_off_while_occupied: 'Fan off while occupied',
  supply_sensor_drift: 'Supply sensor drift',
  high_co2: 'High CO₂',
  too_warm: 'Too warm',
  ml_anomaly: 'Unusual behaviour',
}

export default function Faults({ faults, onPick }) {
  return (
    <section className="faults">
      <h2>Faults</h2>
      {faults.length === 0 && <p className="quiet">Nothing found in the last 30 minutes.</p>}
      <ul>
        {faults.map((f, i) => (
          <li key={i} className={`fault ${f.severity}`}>
            <button onClick={() => onPick(f.zone)}>
              <span className="fault-name">Zone {f.zone} · {NAMES[f.type] || f.type}</span>
              <span className={`src ${f.source === 'rule' ? '' : 'ml'}`}>
                {f.source === 'rule' ? 'Rule' : 'ML model'}
              </span>
            </button>
            <p>{f.detail}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}
