import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import type { StageEvent, SwarmStatus } from './api'
import {
  type ClaimRow,
  type CostTime,
  DETAIL_STAGES,
  type MapProbe,
  type ObsRow,
  type TimelineStep,
  agentRoles,
  behaviourMap,
  coveragePlain,
  detailStageState,
  evidenceLinks,
  logSections,
  observationsForClaim,
  probeItems,
  reasonPoints,
  demoHelperLines,
  summaryText,
  testGlance,
  verdictLabel,
  verdictTone,
} from './present'

const AGENTS: { key: keyof SwarmStatus; name: string; role: string }[] = [
  { key: 'ultra', name: 'Ultra', role: 'Judge — labels findings' },
  { key: 'lightning', name: 'Lightning', role: 'Helper — remediation notes' },
  { key: 'super', name: 'Super', role: 'Summary — the pull-request story' },
]

export function VerdictBadge({ verdict, large = false }: { verdict?: string | null; large?: boolean }) {
  const tone = verdictTone(verdict)
  return (
    <span className={`badge verdict-badge tone-${tone}${large ? ' is-large' : ''}`}>{verdictLabel(verdict)}</span>
  )
}

export function Timeline({
  steps,
  illustrative = false,
  caption,
}: {
  steps: TimelineStep[]
  illustrative?: boolean
  caption?: string | null
}) {
  return (
    <div className={`timeline-wrap${illustrative ? ' is-illustrative' : ''}`}>
      <ol
        className="timeline"
        aria-label={illustrative ? 'Illustration of how a check moves. This is not a live run.' : 'Check progress'}
      >
        {steps.map((step, index) => (
          <li
            key={step.id}
            className={`tl-step is-${step.state}${step.id === 'advice' ? ' is-advice' : ''}`}
            style={{ ['--i' as string]: String(index) }}
            aria-current={!illustrative && step.state === 'current' ? 'step' : undefined}
            aria-label={
              illustrative
                ? `${step.label}. ${step.hint}`
                : `${step.label}, ${step.state}. ${step.hint}`
            }
          >
            <span className="tl-dot" aria-hidden="true" />
            <span className="tl-label">{step.label}</span>
            {step.id === 'advice' ? (
              <span className="advice-flag tl-advice">Doesn't change the verdict</span>
            ) : (
              <span className="tl-hint">{step.hint}</span>
            )}
          </li>
        ))}
      </ol>
      {caption ? <p className="tl-now">{caption}</p> : null}
    </div>
  )
}

export function DetailRail({ stages, current }: { stages: StageEvent[]; current?: string | null }) {
  const failed = stages.some((event) => event.stage === 'failed') || current === 'failed'
  return (
    <ol className="detail-rail">
      {DETAIL_STAGES.map((stage) => {
        const state = detailStageState(stage.id, stages, current)
        return (
          <li key={stage.id} className={`detail-step is-${state}`}>
            <span className="tl-dot" aria-hidden="true" />
            <span>{stage.label}</span>
          </li>
        )
      })}
      {failed ? (
        <li className="detail-step is-failed">
          <span className="tl-dot" aria-hidden="true" />
          <span>Failed</span>
        </li>
      ) : null}
    </ol>
  )
}

export function SwarmTheater({
  swarm,
  currentAgent,
  detail,
}: {
  swarm?: SwarmStatus
  currentAgent?: string | null
  detail?: string | null
}) {
  const status = swarm || { ultra: 'idle', lightning: 'idle', super: 'idle' }
  const active = AGENTS.find((agent) => status[agent.key] === 'active' || currentAgent === agent.key)
  const live = active
    ? `${active.name} is ${status[active.key] || 'active'}.${detail ? ` ${detail}` : ''}`
    : 'All three agents are idle. Their notes do not change the verdict.'
  return (
    <section className="swarm" aria-label="Advisory agent swarm">
      <header className="swarm-head">
        <h2>Agent swarm</h2>
        <p className="advice-flag">Advice only — doesn’t change the verdict</p>
      </header>
      <p className="visually-hidden" aria-live="polite">
        {live}
      </p>
      <div className="swarm-row">
        {AGENTS.map((agent) => {
          const state = status[agent.key] || 'idle'
          const on = state === 'active' || currentAgent === agent.key
          return (
            <article
              key={agent.key}
              className={`agent is-${state}${on && state === 'active' ? ' is-hot' : ''}`}
              data-agent={agent.key}
            >
              <header>
                <span className="agent-name">{agent.name}</span>
                <span className={`agent-state is-${state}`}>{state}</span>
              </header>
              <p className="agent-role">{agent.role}</p>
              {on && state === 'active' && detail ? <p className="agent-detail">{detail}</p> : null}
              {on && state === 'active' ? <span className="agent-pulse" aria-hidden="true" /> : null}
            </article>
          )
        })}
      </div>
    </section>
  )
}

export function LiveLog({ text, running }: { text?: string | null; running?: boolean }) {
  const sections = logSections(text)
  const [open, setOpen] = useState<Record<string, boolean>>({})
  const scroller = useRef<HTMLDivElement>(null)
  const stick = useRef(true)

  useEffect(() => {
    const node = scroller.current
    if (!node || !stick.current) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    node.scrollTo({ top: node.scrollHeight, behavior: reduce ? 'auto' : 'smooth' })
  }, [text])

  if (!sections.length) return <p className="empty">Waiting for process output…</p>

  return (
    <div
      className="log-stack"
      ref={scroller}
      onScroll={(event) => {
        const node = event.currentTarget
        stick.current = node.scrollHeight - node.scrollTop - node.clientHeight < 48
      }}
    >
      {sections.map((section, index) => {
        const isOpen = open[section.id] ?? index === sections.length - 1
        const panelId = `log-${section.id}`
        return (
          <section key={section.id} className={`log-sec${isOpen ? ' is-open' : ''}`}>
            <button
              type="button"
              className="log-toggle"
              aria-expanded={isOpen}
              aria-controls={panelId}
              onClick={() => setOpen((prev) => ({ ...prev, [section.id]: !isOpen }))}
            >
              <span>{section.title}</span>
              <span className="chevron" aria-hidden="true" />
            </button>
            <div className="log-panel" id={panelId} role="region" aria-label={section.title}>
              <pre className="log" tabIndex={isOpen ? 0 : -1} aria-hidden={isOpen ? undefined : true}>
                {section.body}
                {running && index === sections.length - 1 ? <span className="log-caret" aria-hidden="true" /> : null}
              </pre>
            </div>
          </section>
        )
      })}
    </div>
  )
}

export function CostTimePanel({ cost }: { cost: CostTime }) {
  const items = [
    ['Total', cost.total],
    ['AI', cost.ai],
    ['Computer', cost.computer],
    ['Wall time', cost.wall],
    ['Test time', cost.tests],
    ['Tokens', cost.tokens],
  ].filter((item): item is [string, string] => Boolean(item[1]))
  if (!items.length && !cost.swarm) return <p className="empty">This run did not record cost or time.</p>
  return (
    <div className="stat-grid" aria-label="Cost and time for this pull request">
      {items.map(([label, value]) => (
        <article key={label} className="stat">
          <p className="stat-label">{label}</p>
          <p className="stat-value">{value}</p>
        </article>
      ))}
      {cost.swarm ? (
        <article className="stat stat-advice">
          <p className="stat-label">Swarm advice</p>
          <p className="stat-value">{cost.swarm}</p>
          <p className="stat-note">Not part of the check total. Doesn’t change the verdict.</p>
        </article>
      ) : null}
      {cost.complete === false ? <p className="stat-note span">Some AI calls did not report token use, so the AI figure may be low.</p> : null}
    </div>
  )
}

export function ReasonList({ reason }: { reason?: string | null }) {
  const points = reasonPoints(reason)
  if (!points.length) return <p className="empty">No written reason on this run.</p>
  return (
    <ul className="reasons">
      {points.map((point) => (
        <li key={point}>{point}</li>
      ))}
    </ul>
  )
}

export function EvidenceLinks({
  record,
  pdf,
  html,
}: {
  record: Record<string, unknown>
  pdf?: string | null
  html?: string | null
}) {
  const links = evidenceLinks(record, { pdf, html })
  return (
    <ul className="evidence">
      {links.map((link) => (
        <li key={link.href + link.label}>
          <a href={link.href} {...(link.external ? { target: '_blank', rel: 'noreferrer' } : {})}>
            {link.label}
          </a>
        </li>
      ))}
    </ul>
  )
}

export function BehaviourMapView({ record }: { record: Record<string, unknown> }) {
  const map = behaviourMap(record)
  const [openId, setOpenId] = useState<string | null>(null)
  const [hot, setHot] = useState<string | null>(null)
  const root = useRef<HTMLDivElement>(null)

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const nodes = [...(root.current?.querySelectorAll<HTMLButtonElement>('[data-node]') || [])]
    const index = nodes.indexOf(document.activeElement as HTMLButtonElement)
    if (index < 0) return
    let next = index
    if (event.key === 'ArrowDown' || event.key === 'ArrowRight') next = Math.min(nodes.length - 1, index + 1)
    else if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') next = Math.max(0, index - 1)
    else if (event.key === 'Home') next = 0
    else if (event.key === 'End') next = nodes.length - 1
    else if (event.key === 'Escape') {
      setOpenId(null)
      return
    } else return
    event.preventDefault()
    nodes[next]?.focus()
  }

  if (!map.claims.length && !map.probes.length) {
    return <p className="empty">No claims or probes were recorded for this run.</p>
  }

  return (
    <div
      className="bmap"
      ref={root}
      data-hot={hot || undefined}
      onKeyDown={onKeyDown}
      onMouseLeave={() => setHot(null)}
    >
      <p className="hint">
        Hover or focus a claim to light the probes that check it. Press Enter to expand the evidence. Arrow keys move
        between claims and probes. Escape closes the open card.
      </p>
      <ul className="bmap-list">
        {map.claims.map((claim) => {
          const expanded = openId === claim.id
          const panelId = `claim-panel-${claim.id}`
          return (
            <li key={claim.id} className={`bmap-claim${hot === claim.id ? ' is-hot' : ''}`}>
              <button
                type="button"
                className="node"
                data-node="claim"
                data-id={claim.id}
                aria-expanded={expanded}
                aria-controls={panelId}
                aria-label={`${claim.id}, ${claim.result}. ${claim.text}`}
                onMouseEnter={() => setHot(claim.id)}
                onFocus={() => setHot(claim.id)}
                onClick={() => setOpenId((id) => (id === claim.id ? null : claim.id))}
              >
                <span className="node-id">{claim.id}</span>
                <span className={`claim-badge ${claim.result.replace(/\s+/g, '-')}`}>{claim.result}</span>
                <span className="node-tip" role="tooltip">
                  {claim.text}
                </span>
              </button>
              <ul className="bmap-probes">
                {claim.probeIds.map((id) => (
                  <li key={id}>
                    <button
                      type="button"
                      className="probe-chip"
                      data-node="probe"
                      data-id={id}
                      data-links={claim.id}
                      aria-label={`Probe ${id}, checks ${claim.id}`}
                      onMouseEnter={() => setHot(claim.id)}
                      onFocus={() => setHot(claim.id)}
                      onClick={() => setOpenId(id)}
                    >
                      {id}
                    </button>
                  </li>
                ))}
              </ul>
              {expanded ? <ClaimDetail id={panelId} claim={claim} record={record} /> : null}
            </li>
          )
        })}
      </ul>
      {openId && map.probes.some((probe) => probe.id === openId) ? (
        <ProbeDetail probe={map.probes.find((probe) => probe.id === openId)!} />
      ) : null}
    </div>
  )
}

function ClaimDetail({
  id,
  claim,
  record,
}: {
  id: string
  claim: ClaimRow & { result: string; probeIds: string[] }
  record: Record<string, unknown>
}) {
  const obs = observationsForClaim(record, claim.id)
  return (
    <div className="bmap-detail" id={id}>
      <p>{claim.text}</p>
      {claim.expect ? <p className="claim-expect">Expected: {claim.expect}</p> : null}
      {claim.source_quote ? <blockquote className="claim-quote">From the pull request: {claim.source_quote}</blockquote> : null}
      {obs.length ? (
        <ul className="obs-list">
          {obs.map((item, index) => (
            <li key={`${item.name}-${index}`}>{observationLine(item)}</li>
          ))}
        </ul>
      ) : (
        <p className="empty">No observation is tied to this claim.</p>
      )}
    </div>
  )
}

function ProbeDetail({ probe }: { probe: MapProbe }) {
  return (
    <div className="bmap-detail" id={`probe-panel-${probe.id}`}>
      <p>
        <code>{probe.id}</code>
        {probe.status ? <span className="muted"> · {probe.status}</span> : null}
      </p>
      {probe.about ? <p>{probe.about}</p> : null}
      {probe.claimIds.length ? <p className="probe-claims">Covers {probe.claimIds.join(', ')}</p> : null}
      {probe.observations.length ? (
        <ul className="obs-list">
          {probe.observations.map((item, index) => (
            <li key={`${item.name}-${index}`}>{observationLine(item)}</li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

function observationLine(item: ObsRow) {
  return (
    <>
      <code>{String(item.name || 'observation')}</code>
      {item.claim ? <> · claim {String(item.claim)}</> : null}
      {' — '}
      <strong>{String(item.label || item.state || '')}</strong>
      {item.state ? ` (state: ${item.state})` : ''}
    </>
  )
}

export function HelperNotes({ notes }: { notes?: string[] | null }) {
  const lines = (notes || []).filter((line) => line.trim())
  if (lines.length === 0) return null
  return (
    <section className="panel" aria-label="Demo helper">
      <h2>Demo helper</h2>
      <p className="hint">Background only. These notes do not change the verdict.</p>
      <ul>
        {lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </section>
  )
}

export function RunAnalysis({ record }: { record: Record<string, unknown> }) {
  const map = behaviourMap(record)
  const probes = probeItems(record)
  const roles = agentRoles(record)
  const judge = roles.find((role) => role.role === 'judge')
  const helper = roles.find((role) => role.role === 'helper')
  const labels = (Array.isArray(judge?.labels) ? judge.labels : []) as Array<Record<string, unknown>>
  const notes = (Array.isArray(helper?.notes) ? helper.notes : []) as string[]
  const glance = testGlance(record)
  const summary = summaryText(record)
  const coverage = coveragePlain(record)
  const helperLines = demoHelperLines(record)

  return (
    <div className="analysis">
      <section>
        <h2>In plain English</h2>
        <pre className="summary-block">{summary}</pre>
      </section>

      <HelperNotes notes={helperLines} />

      <section id="behaviour-map">
        <h2>Behaviour map</h2>
        <BehaviourMapView record={record} />
      </section>

      <section id="claims">
        <h2>Claims under test</h2>
        <p className="hint">
          Each claim is a behaviour statement taken from the pull request. Probes check whether the base and the pull
          request match what the claim says should stay the same or change.
        </p>
        {map.claims.length === 0 ? (
          <p className="empty">No claims were extracted for this run.</p>
        ) : (
          <ul className="claim-list">
            {map.claims.map((claim) => {
              const obs = observationsForClaim(record, claim.id)
              return (
                <li key={claim.id} className="claim-card">
                  <header>
                    <strong>{claim.id}</strong>
                    <span className={`claim-badge ${claim.result.replace(/\s+/g, '-')}`}>{claim.result}</span>
                    {claim.expect ? <span className="claim-expect">expect: {claim.expect}</span> : null}
                  </header>
                  <p className="claim-text">{claim.text}</p>
                  {claim.source_quote ? (
                    <blockquote className="claim-quote">From the pull request: {claim.source_quote}</blockquote>
                  ) : null}
                  {obs.length > 0 ? (
                    <ul className="obs-list">
                      {obs.map((item, index) => (
                        <li key={`${item.name}-${index}`}>{observationLine(item)}</li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              )
            })}
          </ul>
        )}
      </section>

      <section id="probes">
        <h2>Probes</h2>
        <p className="hint">
          A probe is a small script run on the base and on the pull request with the same inputs. The observation says
          whether the result differed.
        </p>
        {probes.length === 0 ? (
          <p className="empty">No probes ran.</p>
        ) : (
          <ul className="probe-list">
            {probes.map((probe, index) => (
              <li key={String(probe.id ?? index)} className="probe-card">
                <header>
                  <code>{String(probe.id ?? '')}</code>
                  <span className="muted">{String(probe.status ?? '')}</span>
                </header>
                <p>{String(probe.about ?? '')}</p>
                {Array.isArray(probe.claims) && (probe.claims as ClaimRow[]).length > 0 ? (
                  <p className="probe-claims">
                    Covers {(probe.claims as ClaimRow[]).map((claim) => claim.id).filter(Boolean).join(', ')}
                  </p>
                ) : null}
                {Array.isArray(probe.observations) && (probe.observations as ObsRow[]).length > 0 ? (
                  <ul className="obs-list">
                    {(probe.observations as ObsRow[]).map((item, index) => (
                      <li key={`${String(probe.id)}-${index}`}>{observationLine(item)}</li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      {coverage ? (
        <section id="coverage">
          <h2>Coverage</h2>
          <p>{coverage}</p>
        </section>
      ) : null}

      {glance.length > 0 ? (
        <section id="tests">
          <h2>Project tests</h2>
          <ul className="glance-list">
            {glance.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section>
        <h2>Agent notes</h2>
        <p className="advice-flag">Advice only — doesn’t change the verdict</p>
        {labels.length > 0 ? (
          <>
            <h3>Ultra (judge)</h3>
            <ul className="agent-findings">
              {labels.map((label, index) => (
                <li key={String(label.id ?? index)}>
                  <strong>{String(label.label ?? '')}</strong> on <code>{String(label.id ?? '')}</code>
                  {label.reason ? <> — {String(label.reason)}</> : null}
                </li>
              ))}
            </ul>
          </>
        ) : null}
        {notes.length > 0 ? (
          <>
            <h3>Lightning (helper)</h3>
            <ul className="agent-findings">
              {notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </>
        ) : null}
        {labels.length === 0 && notes.length === 0 ? <p className="empty">No agent notes were recorded for this run.</p> : null}
      </section>
    </div>
  )
}
