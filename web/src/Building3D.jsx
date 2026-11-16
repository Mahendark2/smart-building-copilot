import { heat } from './Plan.jsx'

// A cut-away 3D model of the floor, drawn in isometric view.
// Floors are coloured by temperature. Blue dots are supply air leaving the
// air handler; a zone whose fan is off gets no air, so its dots stop.

const S = 21                      // pixels per metre-ish unit
const W = 10, D = 8, HALL = 3     // room width, room depth, corridor depth
const WALL = 1.1

// world (x, y, z) to screen
const px = (x, y, z = 0) => [(x - y) * 0.866 * S, (x + y) * 0.5 * S - z * S]
const pt = (x, y, z) => px(x, y, z).map(v => v.toFixed(1)).join(',')
const poly = cs => cs.map(([x, y, z]) => pt(x, y, z)).join(' ')

const ROOMS = [1, 2, 3, 4, 5, 6].map(z => {
  const c = (z - 1) % 3, r = z > 3 ? 1 : 0
  const x1 = c * W + 0.2, y1 = r * (D + HALL) + 0.2
  return { z, x1, y1 }
}).map(r => ({ ...r, x2: r.x1 + W - 0.4, y2: r.y1 + D - 0.4 }))

const AIR_Y = D + HALL / 2

function airPath(r) {
  const cx = (r.x1 + r.x2) / 2, cy = (r.y1 + r.y2) / 2
  return `M${pt(-1, AIR_Y, 0.3)} L${pt(cx, AIR_Y, 0.3)} L${pt(cx, cy, 0.3)}`
}

const still = typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

export default function Building3D({ zones, faults, pick, onPick }) {
  const [vx, vy] = px(-5, 22)
  const [wx] = px(32, -2)
  const [, ty] = px(-5, -2, 4)
  const [, by] = px(32, 22, -0.6)
  const box = `${(vx - 20).toFixed(0)} ${(ty - 20).toFixed(0)} ${(wx - vx + 40).toFixed(0)} ${(by - ty + 30).toFixed(0)}`

  return (
    <svg className="iso" viewBox={box} role="img" aria-label="3D model of the floor, coloured by temperature">
      {/* plinth */}
      <polygon points={poly([[-1, -1, 0], [31, -1, 0], [31, 2 * D + HALL + 1, 0], [-1, 2 * D + HALL + 1, 0]])} className="slab-top" />
      <polygon points={poly([[31, -1, 0], [31, 2 * D + HALL + 1, 0], [31, 2 * D + HALL + 1, -0.6], [31, -1, -0.6]])} className="slab-side" />
      <polygon points={poly([[-1, 2 * D + HALL + 1, 0], [31, 2 * D + HALL + 1, 0], [31, 2 * D + HALL + 1, -0.6], [-1, 2 * D + HALL + 1, -0.6]])} className="slab-front" />

      {/* air handler at the end of the corridor */}
      <g className="ahu">
        <polygon points={poly([[-4.5, D, 3.2], [-1, D, 3.2], [-1, D + HALL, 3.2], [-4.5, D + HALL, 3.2]])} className="ahu-top" />
        <polygon points={poly([[-1, D, 3.2], [-1, D + HALL, 3.2], [-1, D + HALL, 0], [-1, D, 0]])} className="ahu-side" />
        <polygon points={poly([[-4.5, D + HALL, 3.2], [-1, D + HALL, 3.2], [-1, D + HALL, 0], [-4.5, D + HALL, 0]])} className="ahu-front" />
        <text x={px(-2.8, D + HALL + 1.6, 0)[0]} y={px(-2.8, D + HALL + 1.6, 0)[1]} className="iso-note">Air handler</text>
      </g>

      {/* floors */}
      {ROOMS.map(r => {
        const v = zones[r.z] || {}
        const d = (v.zone_temp ?? 0) - (v.cool_setpoint ?? 0)
        const bad = faults.some(f => f.zone === r.z)
        return (
          <polygon key={`f${r.z}`}
            points={poly([[r.x1, r.y1, 0], [r.x2, r.y1, 0], [r.x2, r.y2, 0], [r.x1, r.y2, 0]])}
            fill={v.zone_temp == null ? '#eef1ef' : heat(d)}
            className={`iso-floor ${bad ? 'alarm' : ''} ${pick === r.z ? 'on' : ''}`} />
        )
      })}

      {/* supply air */}
      {!still && ROOMS.map(r => {
        const v = zones[r.z] || {}
        if (!v.fan_status) return null
        const dur = (5.5 - (v.fan_speed ?? 50) / 25).toFixed(1)
        const path = airPath(r)
        return [0, 1, 2].map(i => (
          <circle key={`a${r.z}${i}`} r="3" className="air">
            <animateMotion dur={`${dur}s`} begin={`${(i * dur / 3).toFixed(2)}s`} repeatCount="indefinite" path={path} />
          </circle>
        ))
      })}

      {/* low glass walls, back ones first */}
      {ROOMS.map(r => {
        const sel = pick === r.z
        return (
          <g key={`w${r.z}`} className={`walls ${sel ? 'on' : ''}`}
             onClick={() => onPick(r.z)} tabIndex="0" role="button"
             onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && onPick(r.z)}
             aria-label={`Zone ${r.z}`}>
            <polygon points={poly([[r.x1, r.y1, 0], [r.x2, r.y1, 0], [r.x2, r.y2, 0], [r.x1, r.y2, 0]])} className="hit" />
            <polygon points={poly([[r.x1, r.y1, 0], [r.x2, r.y1, 0], [r.x2, r.y1, WALL], [r.x1, r.y1, WALL]])} className="wall back" />
            <polygon points={poly([[r.x1, r.y1, 0], [r.x1, r.y2, 0], [r.x1, r.y2, WALL], [r.x1, r.y1, WALL]])} className="wall back" />
            <polygon points={poly([[r.x2, r.y1, 0], [r.x2, r.y2, 0], [r.x2, r.y2, WALL], [r.x2, r.y1, WALL]])} className="wall front" />
            <polygon points={poly([[r.x1, r.y2, 0], [r.x2, r.y2, 0], [r.x2, r.y2, WALL], [r.x1, r.y2, WALL]])} className="wall front" />
          </g>
        )
      })}

      {/* labels float above each room */}
      {ROOMS.map(r => {
        const v = zones[r.z] || {}
        const n = faults.filter(f => f.zone === r.z).length
        const cx = (r.x1 + r.x2) / 2, cy = (r.y1 + r.y2) / 2
        const [lx, ly] = px(cx, cy, 3.2)
        const fy = px(cx, cy, 0)[1]
        return (
          <g key={`l${r.z}`} className={`iso-label ${pick === r.z ? 'on' : ''}`} onClick={() => onPick(r.z)}>
            <line x1={lx} x2={lx} y1={ly + 14} y2={fy} className="pin" />
            <circle cx={lx} cy={fy} r="3" className="pin-dot" />
            <rect x={lx - 46} y={ly - 40} width="92" height={v.fan_status === 0 ? 70 : 54} rx="8" className={`tag ${n ? 'alarm' : ''}`} />
            <text x={lx} y={ly - 22} className="iso-zone">Zone {r.z}</text>
            <text x={lx} y={ly + 4} className="iso-temp">{v.zone_temp != null ? `${v.zone_temp.toFixed(1)}°` : '--'}</text>
            {v.fan_status === 0 && <text x={lx} y={ly + 22} className="iso-off">fan off</text>}
            {n > 0 && (
              <g>
                <circle cx={lx + 46} cy={ly - 40} r="11" className="ping" />
                <circle cx={lx + 46} cy={ly - 40} r="11" className="badge" />
                <text x={lx + 46} y={ly - 35} className="badge-n">{n}</text>
              </g>
            )}
          </g>
        )
      })}
    </svg>
  )
}
