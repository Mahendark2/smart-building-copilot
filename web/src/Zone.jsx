const LABELS = {
  zone_temp: 'Room temp',
  cool_setpoint: 'Cool setpoint',
  heat_setpoint: 'Heat setpoint',
  supply_air_temp: 'Supply air',
  return_air_temp: 'Return air',
  humidity: 'Humidity',
  co2: 'CO2',
  damper_pos: 'Damper',
  valve_pos: 'Cooling valve',
  fan_speed: 'Fan speed',
  fan_status: 'Fan',
  occupied: 'Occupied',
}

const UNITS = { degC: '°C', percent: '%', ppm: ' ppm' }

function show(p) {
  if (p.kind === 'fan_status') return p.value ? 'On' : 'Off'
  if (p.kind === 'occupied') return p.value ? 'Yes' : 'No'
  return `${p.value.toFixed(p.kind === 'co2' ? 0 : 1)}${UNITS[p.units] || ''}`
}

export default function Zone({ zone, points, hasFault }) {
  const temp = points.find(p => p.kind === 'zone_temp')
  return (
    <section className={`zone ${hasFault ? 'bad' : ''}`}>
      <div className="zone-head">
        <h3>Zone {zone}</h3>
        <span className="big">{temp ? show(temp) : '--'}</span>
      </div>
      <table>
        <tbody>
          {points.filter(p => p.kind !== 'zone_temp').map(p => (
            <tr key={p.name}>
              <td>{LABELS[p.kind] || p.kind}</td>
              <td className="num">{show(p)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
