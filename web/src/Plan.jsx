// Floor plan of the building. Each room is coloured by how far it is from
// its cooling setpoint, so a warm zone stands out before you read a number.

const W = 260, H = 170, GAP = 60

const ROOMS = {
  1: [30, 30], 2: [30 + W, 30], 3: [30 + 2 * W, 30],
  4: [30, 30 + H + GAP], 5: [30 + W, 30 + H + GAP], 6: [30 + 2 * W, 30 + H + GAP],
}

// within half a degree of setpoint = pale; 2 C cooler = blue; 2.5 C warmer = orange
export function heat(d) {
  d = Math.sign(d) * Math.max(0, Math.abs(d) - 0.5)
  const cool = [79, 134, 198], mid = [226, 233, 228], warm = [229, 138, 78]
  const t = Math.max(-1, Math.min(1, d < 0 ? d / 1.5 : d / 2))
  const [a, b] = t < 0 ? [mid, cool] : [mid, warm]
  const k = Math.abs(t)
  return `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * k)).join(',')})`
}

export default function Plan({ zones, faults, pick, onPick }) {
  return (
    <svg className="plan" viewBox="0 0 840 460" role="img" aria-label="Floor plan coloured by temperature">
      <rect x="30" y="30" width={3 * W} height={2 * H + GAP} className="shell" />
      <rect x="30" y={30 + H} width={3 * W} height={GAP} className="hall" />
      <text x="420" y={30 + H + GAP / 2 + 5} className="hall-name">Corridor</text>

      {Object.entries(ROOMS).map(([z, [x, y]]) => {
        const v = zones[z] || {}
        const d = (v.zone_temp ?? 0) - (v.cool_setpoint ?? 0)
        const bad = faults.filter(f => f.zone === Number(z))
        const top = y < 100
        const door = top ? y + H : y
        return (
          <g key={z} className={`room ${pick === Number(z) ? 'on' : ''} ${bad.length ? 'alarm' : ''}`}
             onClick={() => onPick(Number(z))} tabIndex="0" role="button"
             onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && onPick(Number(z))}
             aria-label={`Zone ${z}, ${v.zone_temp?.toFixed(1) ?? 'no data'} degrees`}>
            <rect x={x} y={y} width={W} height={H} fill={v.zone_temp == null ? '#eef1ef' : heat(d)} className="floor" />
            <line x1={x + W / 2 - 22} x2={x + W / 2 + 22} y1={door} y2={door} className="door" />
            <text x={x + 18} y={y + 30} className="room-name">Zone {z}</text>
            <text x={x + 18} y={y + 76} className="room-temp">
              {v.zone_temp != null ? `${v.zone_temp.toFixed(1)}°` : '--'}
            </text>
            <text x={x + 18} y={y + 100} className="room-sub">
              {v.cool_setpoint != null && `setpoint ${v.cool_setpoint.toFixed(1)}°`}
            </text>
            <text x={x + 18} y={y + 124} className="room-sub">
              {v.fan_status != null && `fan ${v.fan_status ? 'on' : 'off'} · damper ${Math.round(v.damper_pos)}%`}
            </text>
            {bad.length > 0 && (
              <g>
                <circle cx={x + W - 26} cy={y + 26} r="13" className="badge" />
                <text x={x + W - 26} y={y + 31} className="badge-n">{bad.length}</text>
              </g>
            )}
          </g>
        )
      })}
    </svg>
  )
}
