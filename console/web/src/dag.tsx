import { useState } from 'react'
import type { StageEvent } from './api'
import { FLOW_EDGES, edgeActive, flowNodes, type FlowNode } from './flow'

const STATE_LABEL: Record<FlowNode['state'], string> = {
  pending: 'Waiting',
  running: 'Running',
  done: 'Done',
  failed: 'Failed',
  skipped: 'Skipped',
}

export function ProcessDag({
  events,
  record,
  log,
}: {
  events?: StageEvent[] | null
  record?: Record<string, unknown> | null
  log?: string | null
}) {
  const nodes = flowNodes(events, record)
  const byId = Object.fromEntries(nodes.map((node) => [node.id, node]))
  const [selected, setSelected] = useState<string>(nodes.find((node) => node.state === 'running')?.id || 'verdict')
  const current = nodes.find((node) => node.id === selected) || nodes[0]
  return (
    <section className="panel dag" aria-label="Check process">
      <h2>How this check moves</h2>
      <p className="hint">Each box is one step. Reviewer notes come after the verdict and do not change it.</p>
      <svg className="dag-svg" viewBox="0 0 1720 340" role="img">
        <title>Directed graph of the check</title>
        {FLOW_EDGES.map(([from, to]) => {
          const a = byId[from]
          const b = byId[to]
          const live = edgeActive(a.state, b.state)
          return (
            <line
              key={`${from}-${to}`}
              x1={a.x + 156}
              y1={a.y + 22}
              x2={b.x}
              y2={b.y + 22}
              stroke={live ? '#3d6200' : '#3c4a32'}
              strokeWidth={3}
              className={live ? 'dag-edge is-live' : 'dag-edge'}
            />
          )
        })}
        {nodes.map((node) => (
          <g key={node.id} transform={`translate(${node.x} ${node.y})`}>
            <rect
              width="156"
              height="44"
              rx="8"
              className={`dag-node is-${node.state}${node.id === current.id ? ' is-selected' : ''}`}
              role="button"
              tabIndex={0}
              aria-label={`${node.label}, ${STATE_LABEL[node.state]}`}
              onClick={() => setSelected(node.id)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  setSelected(node.id)
                }
              }}
            />
            <text x="78" y="27" textAnchor="middle" className="dag-label">
              {node.label}
            </text>
          </g>
        ))}
      </svg>
      <div className="dag-detail" aria-live="polite">
        <p className="kicker">{STATE_LABEL[current.state]}{current.duration ? ` · ${current.duration}` : ''}</p>
        <h3>{current.label}</h3>
        <p>{current.hint}</p>
        {current.detail ? <p className="meta-line">{current.detail}</p> : null}
        {current.id === 'advice' ? <p className="hint">Doesn't change the verdict.</p> : null}
        {log && (current.state === 'running' || current.state === 'failed') ? (
          <pre className="log dag-log">{log.slice(-1200)}</pre>
        ) : null}
      </div>
    </section>
  )
}
