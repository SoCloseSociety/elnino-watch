import { useId } from 'react'

/**
 * Cross-section of the equatorial Pacific, west (Indonesia / Southeast Asia) on the
 * left, east (South America) on the right: normal conditions vs El Nino.
 * Schematic, after NOAA's ENSO diagrams (CPC FAQ, Climate.gov Walker circulation):
 *  - normal: strong easterly trade winds, warm pool and rising air in the west,
 *    thermocline deep in the west and shallow in the east, cold upwelling in the east;
 *  - El Nino: weak trade winds, warm water spread east, thermocline flatter (deeper in
 *    the east), rising air moved to the central/east Pacific, sinking air over the west.
 */
export function EnsoDiagram() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel mode="normal" />
      <Panel mode="nino" />
    </div>
  )
}

const INK = { fill: 'var(--ink-2)' }
const SMALL = { fontSize: 11 } as const

function Panel({ mode }: { mode: 'normal' | 'nino' }) {
  const uid = useId().replace(/:/g, '')
  const nino = mode === 'nino'
  const titleId = `enso-d-t-${uid}`
  const descId = `enso-d-d-${uid}`
  const grad = `enso-warm-${uid}`
  const arrow = `enso-arrow-${uid}`
  // thermocline: y at the west (x=40) and east (x=600) ends
  const tcW = nino ? 226 : 252
  const tcE = nino ? 214 : 176
  const warmEnd = nino ? 0.85 : 0.45 // how far east the warm colour reaches (fraction)
  return (
    <figure className="card overflow-hidden">
      <figcaption className="border-b border-line px-3 py-2 text-[12px] font-semibold tracking-wide text-ink-2 uppercase">
        {nino ? 'El Nino conditions' : 'Normal (neutral) conditions'}
      </figcaption>
      <svg viewBox="0 0 640 300" className="block h-auto w-full" role="img" aria-labelledby={`${titleId} ${descId}`}>
        <title id={titleId}>{nino ? 'El Nino conditions in the equatorial Pacific' : 'Normal conditions in the equatorial Pacific'}</title>
        <desc id={descId}>
          {nino
            ? 'Trade winds are weak. Warm surface water spreads east across the Pacific. The thermocline is flatter and deeper in the east, so cold water no longer rises near South America. Rising air and rain clouds move to the central and eastern Pacific, while air sinks over Indonesia and Southeast Asia, bringing drier weather there.'
            : 'Strong trade winds blow from east to west and pile warm water in the west. The thermocline is deep in the west and shallow in the east, where cold water rises to the surface. Air rises with rain clouds over the warm western Pacific and sinks as dry air over the cool eastern Pacific.'}
        </desc>
        <defs>
          <linearGradient id={grad} x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" style={{ stopColor: 'var(--warm)', stopOpacity: 0.85 }} />
            <stop offset={warmEnd} style={{ stopColor: 'var(--warm)', stopOpacity: 0.55 }} />
            <stop offset="1" style={{ stopColor: 'var(--cold)', stopOpacity: nino ? 0.35 : 0.55 }} />
          </linearGradient>
          <marker id={arrow} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" style={{ fill: 'var(--ink)' }} />
          </marker>
        </defs>

        {/* deep cold ocean */}
        <rect x="0" y="150" width="640" height="150" style={{ fill: 'var(--cold)', fillOpacity: 0.18 }} />
        {/* warm upper layer above the thermocline */}
        <path d={`M40,150 L600,150 L600,${tcE} Q320,${(tcW + tcE) / 2 + (nino ? 4 : 10)} 40,${tcW} Z`} style={{ fill: `url(#${grad})` }} />
        {/* thermocline */}
        <path d={`M40,${tcW} Q320,${(tcW + tcE) / 2 + (nino ? 4 : 10)} 600,${tcE}`} style={{ fill: 'none', stroke: 'var(--ink)', strokeWidth: 2, strokeDasharray: '6 4' }} />
        <text x={nino ? 250 : 300} y={nino ? 238 : 232} style={{ ...INK, ...SMALL }}>Thermocline</text>
        {/* ocean surface */}
        <line x1="0" y1="150" x2="640" y2="150" style={{ stroke: 'var(--cold)', strokeWidth: 2 }} />
        {/* land: west (Indonesia / SE Asia) and east (South America) */}
        <path d="M0,150 L0,118 Q18,108 40,126 L40,300 L0,300 Z" style={{ fill: 'var(--ink-3)', fillOpacity: 0.55 }} />
        <path d="M600,300 L600,120 Q618,96 640,90 L640,300 Z" style={{ fill: 'var(--ink-3)', fillOpacity: 0.55 }} />
        <text x="4" y="292" style={{ ...INK, fontSize: 10 }}>West</text>
        <text x="608" y="292" style={{ ...INK, fontSize: 10 }}>East</text>
        <text x="46" y="170" style={{ ...INK, ...SMALL, fontWeight: 600 }}>Indonesia / SE Asia side</text>
        <text x="594" y="170" textAnchor="end" style={{ ...INK, ...SMALL, fontWeight: 600 }}>South America side</text>
        <text x={nino ? 250 : 110} y="196" style={{ fill: 'var(--ink)', fontSize: 12, fontWeight: 600 }}>
          {nino ? 'Warm water spreads east' : 'Warm pool'}
        </text>

        {/* upwelling near South America */}
        {nino ? (
          <text x="594" y="262" textAnchor="end" style={{ ...INK, ...SMALL }}>Cold upwelling weakens</text>
        ) : (
          <>
            <line x1="560" y1="250" x2="560" y2="160" markerEnd={`url(#${arrow})`} style={{ stroke: 'var(--cold)', strokeWidth: 3 }} />
            <text x="552" y="268" textAnchor="end" style={{ ...INK, ...SMALL }}>Cold water rises</text>
          </>
        )}

        {/* trade winds at the surface */}
        {nino ? (
          <>
            <line x1="470" y1="136" x2="420" y2="136" markerEnd={`url(#${arrow})`} style={{ stroke: 'var(--ink)', strokeWidth: 1.5 }} />
            <line x1="120" y1="136" x2="170" y2="136" markerEnd={`url(#${arrow})`} style={{ stroke: 'var(--ink)', strokeWidth: 1.5 }} />
            <text x="320" y="140" textAnchor="middle" style={{ ...INK, ...SMALL }}>Weak or reversed trade winds</text>
          </>
        ) : (
          <>
            {[520, 380, 240].map((x) => (
              <line key={x} x1={x} y1="136" x2={x - 90} y2="136" markerEnd={`url(#${arrow})`} style={{ stroke: 'var(--ink)', strokeWidth: 2.5 }} />
            ))}
            <text x="320" y="128" textAnchor="middle" style={{ ...INK, ...SMALL }}>Strong trade winds (east to west)</text>
          </>
        )}

        {/* Walker circulation: rising branch with rain cloud, flow aloft, sinking branch */}
        {nino ? (
          <>
            <Cloud x={380} y={46} />
            <line x1="380" y1="118" x2="380" y2="70" markerEnd={`url(#${arrow})`} style={{ stroke: 'var(--ink)', strokeWidth: 2 }} />
            <path d="M350,30 Q220,14 100,40" markerEnd={`url(#${arrow})`} style={{ fill: 'none', stroke: 'var(--ink)', strokeWidth: 2 }} />
            <line x1="90" y1="56" x2="90" y2="112" markerEnd={`url(#${arrow})`} style={{ stroke: 'var(--ink)', strokeWidth: 2 }} />
            <text x="100" y="92" style={{ ...INK, ...SMALL }}>Sinking dry air:</text>
            <text x="100" y="106" style={{ ...INK, ...SMALL }}>less rain in the west</text>
            <text x="416" y="92" style={{ ...INK, ...SMALL }}>Rising air and rain</text>
            <text x="416" y="106" style={{ ...INK, ...SMALL }}>move to the central Pacific</text>
          </>
        ) : (
          <>
            <Cloud x={110} y={46} />
            <line x1="110" y1="118" x2="110" y2="70" markerEnd={`url(#${arrow})`} style={{ stroke: 'var(--ink)', strokeWidth: 2 }} />
            <path d="M150,28 Q340,10 530,40" markerEnd={`url(#${arrow})`} style={{ fill: 'none', stroke: 'var(--ink)', strokeWidth: 2 }} />
            <line x1="540" y1="56" x2="540" y2="112" markerEnd={`url(#${arrow})`} style={{ stroke: 'var(--ink)', strokeWidth: 2 }} />
            <text x="150" y="92" style={{ ...INK, ...SMALL }}>Rising air, rain clouds</text>
            <text x="532" y="92" textAnchor="end" style={{ ...INK, ...SMALL }}>Sinking dry air</text>
            <text x="340" y="52" textAnchor="middle" style={{ ...INK, fontSize: 10 }}>Walker circulation</text>
          </>
        )}
      </svg>
    </figure>
  )
}

function Cloud({ x, y }: { x: number; y: number }) {
  return (
    <g aria-hidden>
      <ellipse cx={x} cy={y} rx="34" ry="14" style={{ fill: 'var(--ink-3)', fillOpacity: 0.85 }} />
      <ellipse cx={x - 16} cy={y - 8} rx="16" ry="11" style={{ fill: 'var(--ink-3)', fillOpacity: 0.85 }} />
      <ellipse cx={x + 12} cy={y - 10} rx="18" ry="12" style={{ fill: 'var(--ink-3)', fillOpacity: 0.85 }} />
      {[-18, -6, 6, 18].map((dx) => (
        <line key={dx} x1={x + dx} y1={y + 16} x2={x + dx - 4} y2={y + 26} style={{ stroke: 'var(--cold)', strokeWidth: 1.5 }} />
      ))}
    </g>
  )
}
