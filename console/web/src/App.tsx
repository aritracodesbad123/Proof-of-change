import { useCallback, useEffect, useState } from 'react'
import { api, type Job, type RunRow, type StageEvent, type SwarmStatus } from './api'
import './App.css'

type View =
  | { name: 'home' }
  | { name: 'run'; id: string }
  | { name: 'job'; id: string }

const STAGE_ORDER = [
  'queued',
  'fetch_pr',
  'install_main',
  'install_pr',
  'claims',
  'probes',
  'pytest',
  'verdict',
  'agent_judge',
  'agent_helper',
  'agent_summary',
  'report',
  'done',
] as const

const STAGE_LABEL: Record<string, string> = {
  queued: 'Queued',
  fetch_pr: 'Fetch PR',
  install_main: 'Install main',
  install_pr: 'Install PR',
  claims: 'Claims',
  probes: 'Probes',
  pytest: 'Pytest',
  verdict: 'Code verdict',
  agent_judge: 'Ultra judging',
  agent_helper: 'Lightning helping',
  agent_summary: 'Super summarizing',
  report: 'Report',
  done: 'Done',
  failed: 'Failed',
}

const AGENTS: { key: keyof SwarmStatus; name: string; role: string }[] = [
  { key: 'ultra', name: 'Ultra', role: 'Judge — labels findings' },
  { key: 'lightning', name: 'Lightning', role: 'Helper — remediation notes' },
  { key: 'super', name: 'Super', role: 'Summary — PR narrative' },
]

function verdictClass(v?: string) {
  if (v === 'verified') return 'v-ok'
  if (v === 'needs_attention') return 'v-warn'
  return 'v-muted'
}

export default function App() {
  const [view, setView] = useState<View>({ name: 'home' })
  const [runs, setRuns] = useState<RunRow[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [apiOk, setApiOk] = useState<boolean | null>(null)
  const [prUrl, setPrUrl] = useState('')
  const [provider, setProvider] = useState('nebius')
  const [busy, setBusy] = useState(false)
  const [detail, setDetail] = useState<{
    record: Record<string, unknown>
    folder: string
    hosted_report: string | null
  } | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [logOpen, setLogOpen] = useState(false)

  const refresh = useCallback(async () => {
    try {
      setApiOk((await api.health()).ok)
      setRuns((await api.runs()).runs)
      setErr(null)
    } catch (e) {
      setApiOk(false)
      setErr(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (view.name !== 'run') return
    void api
      .run(view.id)
      .then(setDetail)
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
  }, [view])

  useEffect(() => {
    if (view.name !== 'job') return
    let stop = false
    const tick = async () => {
      try {
        const j = await api.job(view.id)
        if (stop) return
        setJob(j)
        if (j.status === 'done' || j.status === 'failed') {
          void refresh()
          return
        }
        window.setTimeout(() => void tick(), 1500)
      } catch (e) {
        if (!stop) setErr(e instanceof Error ? e.message : String(e))
      }
    }
    void tick()
    return () => {
      stop = true
    }
  }, [view, refresh])

  async function onStart(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    setLogOpen(false)
    try {
      const j = await api.startCheck(prUrl.trim(), provider)
      setView({ name: 'job', id: j.id })
      setJob(j)
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : String(ex))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="shell">
      <header className="top">
        <button type="button" className="brand" onClick={() => setView({ name: 'home' })}>
          Proof-of-Change
        </button>
        <p className="tag">Nemotron swarm on every PR — paste a link, watch Ultra · Lightning · Super</p>
        <span className={`pill ${apiOk ? 'on' : 'off'}`}>
          {apiOk == null ? '…' : apiOk ? 'API up' : 'API down'}
        </span>
      </header>

      {err && (
        <p className="banner err" role="alert">
          {err}
          {apiOk === false && ' — start the API: make console-api'}
        </p>
      )}

      {view.name === 'home' && (
        <main className="main">
          <section className="panel start">
            <h1>Check a pull request</h1>
            <p className="lede">
              Paste a GitHub PR URL. Pipeline + advisory agent swarm run for that PR only.
            </p>
            <form onSubmit={onStart} className="form">
              <label>
                Pull request URL
                <input
                  value={prUrl}
                  onChange={(e) => setPrUrl(e.target.value)}
                  placeholder="https://github.com/owner/repo/pull/123"
                  required
                  autoComplete="off"
                />
              </label>
              <label>
                Model provider
                <select value={provider} onChange={(e) => setProvider(e.target.value)}>
                  <option value="nebius">nebius</option>
                  <option value="none">none (no AI)</option>
                  <option value="recorded">recorded</option>
                </select>
              </label>
              <button type="submit" disabled={busy || !prUrl.trim()}>
                {busy ? 'Starting…' : 'Run check'}
              </button>
            </form>
          </section>

          <section className="panel">
            <div className="row">
              <h2>Recent runs</h2>
              <button type="button" className="ghost" onClick={() => void refresh()}>
                Refresh
              </button>
            </div>
            {runs.length === 0 ? (
              <p className="empty">No runs yet. Start a check above, or run <code>make check</code>.</p>
            ) : (
              <ul className="run-list">
                {runs.map((r) => (
                  <li key={r.id}>
                    <button type="button" className="run" onClick={() => setView({ name: 'run', id: r.id })}>
                      <span className={`verdict ${verdictClass(r.verdict)}`}>{r.verdict || '?'}</span>
                      <span className="meta">
                        <strong>
                          {r.repo}#{r.pr}
                        </strong>
                        <span>{r.title || r.id}</span>
                        <span className="when">{r.tested_at_ist}</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </main>
      )}

      {view.name === 'job' && job && (
        <main className="main job-main">
          <button type="button" className="ghost back" onClick={() => setView({ name: 'home' })}>
            ← Back
          </button>
          <p className="job-kicker">
            {job.repo}#{job.pr} · <strong>{job.status}</strong>
          </p>
          <h1>Agent swarm</h1>
          <p className="lede">
            {job.current_detail ||
              (job.status === 'running'
                ? 'Pipeline running — swarm stands by until the code verdict.'
                : job.status === 'done'
                  ? 'Check finished.'
                  : 'Waiting…')}
          </p>

          <SwarmTheater
            swarm={job.swarm}
            currentAgent={job.current_agent}
            detail={job.current_detail}
          />
          <StageRunway stages={job.stages || []} current={job.current_stage} />

          {job.error && <p className="banner err">{job.error}</p>}
          {job.run_id && (
            <p>
              <button type="button" className="linkish" onClick={() => setView({ name: 'run', id: job.run_id! })}>
                Open run {job.run_id}
              </button>
            </p>
          )}
          <button type="button" className="ghost log-toggle" onClick={() => setLogOpen((o) => !o)}>
            {logOpen ? 'Hide log' : 'Show log tail'}
          </button>
          {logOpen && job.log_tail && (
            <pre className="log" tabIndex={0}>
              {job.log_tail}
            </pre>
          )}
        </main>
      )}

      {view.name === 'run' && detail && (
        <main className="main narrow">
          <button type="button" className="ghost back" onClick={() => setView({ name: 'home' })}>
            ← Back
          </button>
          <h1 className={verdictClass(String(detail.record.verdict))}>
            {String(detail.record.verdict || '')}
          </h1>
          <p className="lede">{String(detail.record.reason || '')}</p>
          <p className="meta-line">
            {String(detail.record.repo)} · folder <code>{detail.folder}</code>
          </p>
          <BehaviorMap record={detail.record} />
          {detail.hosted_report && (
            <p className="meta-line">
              Hosted report file: <code>{detail.hosted_report}</code>
            </p>
          )}
        </main>
      )}
    </div>
  )
}

function SwarmTheater({
  swarm,
  currentAgent,
  detail,
}: {
  swarm?: SwarmStatus
  currentAgent?: string | null
  detail?: string | null
}) {
  const s = swarm || { ultra: 'idle', lightning: 'idle', super: 'idle' }
  return (
    <div className="swarm" aria-live="polite">
      {AGENTS.map((a) => {
        const st = s[a.key] || 'idle'
        const active = st === 'active' || currentAgent === a.key
        return (
          <article
            key={a.key}
            className={`agent ${st}${active && st === 'active' ? ' is-active' : ''}`}
            data-agent={a.key}
          >
            <header>
              <span className="agent-name">{a.name}</span>
              <span className={`agent-state ${st}`}>{st}</span>
            </header>
            <p className="agent-role">{a.role}</p>
            {active && st === 'active' && detail && <p className="agent-detail">{detail}</p>}
            {active && st === 'active' && <span className="agent-pulse" aria-hidden />}
          </article>
        )
      })}
    </div>
  )
}

function StageRunway({ stages, current }: { stages: StageEvent[]; current?: string | null }) {
  const seen = new Set(stages.map((e) => e.stage))
  const failed = seen.has('failed')
  return (
    <ol className="runway">
      {STAGE_ORDER.map((id) => {
        let state = 'pending'
        if (seen.has(id) && id !== current) state = 'done'
        if (current === id) state = 'current'
        if (failed && id === 'done') state = 'skipped'
        return (
          <li key={id} className={`runway-step ${state}`} data-stage={id}>
            <span className="dot" />
            <span className="label">{STAGE_LABEL[id] || id}</span>
          </li>
        )
      })}
      {failed && (
        <li className="runway-step current" data-stage="failed">
          <span className="dot" />
          <span className="label">Failed</span>
        </li>
      )}
    </ol>
  )
}

function BehaviorMap({ record }: { record: Record<string, unknown> }) {
  const claims = (record.behaviour_claims as Array<Record<string, unknown>>) || []
  const probes = ((record.probes as { items?: Array<Record<string, unknown>> }) || {}).items || []
  const expl = (record.explanation as { text?: string }) || {}
  return (
    <div className="map">
      <h2>Behavior map</h2>
      <h3>Claims</h3>
      {claims.length === 0 ? (
        <p className="empty">None</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Id</th>
              <th>Claim</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((c, i) => (
              <tr key={String(c.id ?? i)}>
                <td>{String(c.id ?? '')}</td>
                <td>{String(c.text || c.claim || '')}</td>
                <td>{String(c.status ?? '')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <h3>Probes</h3>
      {probes.length === 0 ? (
        <p className="empty">None</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Id</th>
              <th>About</th>
              <th>Labels</th>
            </tr>
          </thead>
          <tbody>
            {probes.slice(0, 40).map((p, i) => (
              <tr key={String(p.id ?? i)}>
                <td>{String(p.id ?? '')}</td>
                <td>{String(p.about ?? '')}</td>
                <td>{Array.isArray(p.labels) ? p.labels.join(', ') : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <h3>Summary</h3>
      <p>{expl.text || '(no AI summary)'}</p>
    </div>
  )
}
