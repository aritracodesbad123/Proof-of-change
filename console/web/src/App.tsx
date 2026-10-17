import { useCallback, useEffect, useState } from 'react'
import {
  api,
  type HitlApprovalBody,
  type HitlDraft,
  type Job,
  type RunRow,
  type StageEvent,
  type SwarmStatus,
} from './api'
import './App.css'

const LOCAL_RUNS_KEY = 'poc-console-runs-v1'

type CachedRun = {
  id: string
  row: RunRow
  record: Record<string, unknown>
  folder: string
  saved_at: number
}

function loadLocalRuns(): CachedRun[] {
  try {
    const raw = localStorage.getItem(LOCAL_RUNS_KEY)
    const parsed = raw ? (JSON.parse(raw) as CachedRun[]) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveLocalRun(entry: CachedRun) {
  const rest = loadLocalRuns().filter((r) => r.id !== entry.id)
  const next = [entry, ...rest].slice(0, 30)
  localStorage.setItem(LOCAL_RUNS_KEY, JSON.stringify(next))
}

function mergeRunLists(apiRuns: RunRow[], local: CachedRun[]): RunRow[] {
  const seen = new Set(apiRuns.map((r) => r.id))
  const extra = local.filter((c) => !seen.has(c.id)).map((c) => ({ ...c.row, source: 'browser' }))
  return [...apiRuns, ...extra]
}

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
  'await_human',
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
  await_human: 'Human review',
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

const MAX_SCENARIOS = 20

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
    report_pdf?: string | null
    report_html?: string | null
  } | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [jobRefreshing, setJobRefreshing] = useState(false)

  const refresh = useCallback(async () => {
    setRefreshing(true)
    try {
      setApiOk((await api.health()).ok)
      const remote = (await api.runs()).runs
      setRuns(mergeRunLists(remote, loadLocalRuns()))
      setErr(null)
    } catch (e) {
      setApiOk(false)
      // Keep prior runs on failure; only fill from browser cache when we have none yet.
      setRuns((prev) => (prev.length ? prev : mergeRunLists([], loadLocalRuns())))
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (view.name !== 'run') return
    void api
      .run(view.id)
      .then((d) => {
        setDetail({
          record: d.record,
          folder: d.folder,
          hosted_report: d.hosted_report,
          report_pdf: d.report_pdf,
          report_html: d.report_html,
        })
        if (d.record && d.record.id) {
          const pr = d.record.pr as { number?: number; url?: string; title?: string } | undefined
          saveLocalRun({
            id: String(d.record.id),
            row: {
              id: String(d.record.id),
              repo: String(d.record.repo || ''),
              pr: pr?.number,
              url: pr?.url,
              title: pr?.title || String(d.record.title || ''),
              verdict: String(d.record.verdict || ''),
              reason: String(d.record.reason || '').slice(0, 240),
              tested_at_ist: String(d.record.tested_at_ist || d.record.date_ist || ''),
              machine: String(d.record.machine || 'local'),
              folder: d.folder,
            },
            record: d.record,
            folder: d.folder,
            saved_at: Date.now(),
          })
        }
      })
      .catch((e) => {
        const cached = loadLocalRuns().find((c) => c.id === view.id)
        if (cached) {
          setDetail({ record: cached.record, folder: cached.folder, hosted_report: null })
          setErr(null)
          return
        }
        setErr(e instanceof Error ? e.message : String(e))
      })
  }, [view])

  useEffect(() => {
    if (view.name !== 'job') return
    let stop = false
    let retries = 0
    const tick = async () => {
      try {
        const j = await api.job(view.id)
        if (stop) return
        retries = 0
        setJob(j)
        setErr(null)
        if (j.status === 'done' || j.status === 'failed') {
          if (j.record && j.run_id) {
            const pr = j.record.pr as { number?: number; url?: string; title?: string } | undefined
            saveLocalRun({
              id: j.run_id,
              row: {
                id: j.run_id,
                repo: String(j.record.repo || j.repo || ''),
                pr: pr?.number ?? j.pr,
                url: pr?.url || j.pr_url,
                title: pr?.title || String(j.record.title || ''),
                verdict: String(j.record.verdict || ''),
                reason: String(j.record.reason || '').slice(0, 240),
                tested_at_ist: String(j.record.tested_at_ist || ''),
                machine: String(j.record.machine || 'local'),
                folder: j.folder || '',
              },
              record: j.record,
              folder: j.folder || '',
              saved_at: Date.now(),
            })
          }
          void refresh()
          if (j.status === 'done' && j.run_id) {
            setView({ name: 'run', id: j.run_id })
            if (j.record) {
              setDetail({
                record: j.record,
                folder: j.folder || '',
                hosted_report: null,
                report_pdf: j.report_pdf,
                report_html: j.report_html,
              })
            }
          }
          return
        }
        window.setTimeout(() => void tick(), 1500)
      } catch (e) {
        if (stop) return
        retries += 1
        if (retries < 4) {
          window.setTimeout(() => void tick(), 1000 * retries)
          return
        }
        setErr(e instanceof Error ? e.message : String(e))
        window.setTimeout(() => void tick(), 4000)
      }
    }
    void tick()
    return () => {
      stop = true
    }
  }, [view, refresh])

  async function refreshJob() {
    if (view.name !== 'job') return
    setJobRefreshing(true)
    try {
      const j = await api.job(view.id)
      setJob(j)
      setErr(null)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setJobRefreshing(false)
    }
  }

  async function onStart(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setErr(null)
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
              <button type="button" className="ghost" onClick={() => void refresh()} disabled={refreshing}>
                {refreshing ? 'Refreshing…' : 'Refresh'}
              </button>
            </div>
            {runs.length === 0 ? (
              <p className="empty">
                No runs yet. Start a check above. Finished analyses are kept in this browser too — Render
                free disk is wiped when the service sleeps.
              </p>
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
          <div className="job-toolbar">
            <button type="button" className="ghost back" onClick={() => setView({ name: 'home' })}>
              ← Back
            </button>
            <button type="button" className="ghost" onClick={() => void refreshJob()} disabled={jobRefreshing}>
              {jobRefreshing ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>
          <p className="job-kicker">
            {job.repo}#{job.pr} · <strong>{job.status}</strong>
          </p>
          <h1>Live check</h1>
          <p className="lede">
            {job.current_detail ||
              (job.status === 'awaiting_human'
                ? 'AI drafted claims and probes — approve, drop, or add business scenarios to continue.'
                : job.status === 'running'
                  ? 'Pipeline running — swarm stands by until the code verdict.'
                  : job.status === 'done'
                    ? 'Check finished — opening the analysis…'
                    : job.status === 'failed'
                      ? 'Check failed before a full analysis was saved.'
                      : 'Waiting…')}
          </p>

          <div className="job-grid">
            <div className="job-left">
              <SwarmTheater
                swarm={job.swarm}
                currentAgent={job.current_agent}
                detail={job.current_detail}
              />
              {job.status === 'awaiting_human' && job.hitl_draft && (
                <HitlPanel jobId={job.id} draft={job.hitl_draft} onSubmitted={(j) => setJob(j)} />
              )}
              {job.error && (
                <p className="banner err" role="alert">
                  {job.error}
                </p>
              )}
              {job.warning && !job.error && (
                <p className="banner warn" role="status">
                  {job.warning}
                </p>
              )}
              {job.run_id && (
                <p className="report-links">
                  <button type="button" className="linkish" onClick={() => setView({ name: 'run', id: job.run_id! })}>
                    Open analysis {job.run_id}
                  </button>
                  {job.report_pdf ? (
                    <a className="btn-report" href={job.report_pdf} target="_blank" rel="noreferrer">
                      Open PDF report
                    </a>
                  ) : null}
                  {job.report_html ? (
                    <a className="btn-report ghost" href={job.report_html} target="_blank" rel="noreferrer">
                      Open HTML report
                    </a>
                  ) : null}
                </p>
              )}
            </div>
            <aside className="job-right">
              <ProcessFlow stages={job.stages || []} current={job.current_stage} />
            </aside>
          </div>

          <section className="live-log" aria-label="Live console log">
            <h2>Live log</h2>
            {job.log_tail ? (
              <pre className="log always-on" tabIndex={0}>
                {job.log_tail}
              </pre>
            ) : (
              <p className="empty">Waiting for process output…</p>
            )}
          </section>
        </main>
      )}

      {view.name === 'run' && detail && (
        <main className="main narrow">
          <button type="button" className="ghost back" onClick={() => setView({ name: 'home' })}>
            ← Back
          </button>
          <p className="job-kicker">
            {String(detail.record.repo)}
            {prNumber(detail.record) != null ? `#${prNumber(detail.record)}` : ''} ·{" "}
            {String(
              (detail.record.pr as { title?: string } | undefined)?.title ||
                detail.record.title ||
                detail.record.id ||
                '',
            )}
          </p>
          <h1 className={verdictClass(String(detail.record.verdict))}>
            {plainVerdict(String(detail.record.verdict || ''))}
          </h1>
          <p className="lede">{String(detail.record.reason || '')}</p>
          <p className="meta-line">
            Code verdict <code>{String(detail.record.verdict || '')}</code>
            {detail.record.machine ? <> · ran on <code>{String(detail.record.machine)}</code></> : null}
            {' · '}
            folder <code>{detail.folder}</code>
          </p>
          {(detail.report_pdf || detail.report_html) && (
            <p className="report-links">
              {detail.report_pdf ? (
                <a className="btn-report" href={detail.report_pdf} target="_blank" rel="noreferrer">
                  Open PDF report
                </a>
              ) : null}
              {detail.report_html ? (
                <a className="btn-report ghost" href={detail.report_html} target="_blank" rel="noreferrer">
                  Open HTML report
                </a>
              ) : null}
            </p>
          )}
          <RunAnalysis record={detail.record} />
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

function ProcessFlow({ stages, current }: { stages: StageEvent[]; current?: string | null }) {
  const seen = new Set(stages.map((e) => e.stage))
  const failed = seen.has('failed')
  const orderIdx = current ? STAGE_ORDER.indexOf(current as (typeof STAGE_ORDER)[number]) : -1
  return (
    <div className="process-flow" aria-label="Process flow">
      <h2>Process flow</h2>
      <ol className="flow-rail">
        {STAGE_ORDER.map((id, i) => {
          let state = 'pending'
          if (seen.has(id) && id !== current) state = 'done'
          if (current === id) state = 'current'
          if (orderIdx >= 0 && i < orderIdx && !seen.has(id)) state = 'done'
          if (failed && id === 'done') state = 'skipped'
          return (
            <li key={id} className={`flow-step ${state}`} data-stage={id}>
              <span className="flow-marker" aria-hidden />
              <span className="flow-label">{STAGE_LABEL[id] || id}</span>
            </li>
          )
        })}
        {failed && (
          <li className="flow-step current" data-stage="failed">
            <span className="flow-marker" aria-hidden />
            <span className="flow-label">Failed</span>
          </li>
        )}
      </ol>
    </div>
  )
}

function HitlPanel({
  jobId,
  draft,
  onSubmitted,
}: {
  jobId: string
  draft: HitlDraft
  onSubmitted: (j: Job) => void
}) {
  const probeIds = (draft.probe_ids || (draft.probes || []).map((p) => String(p.id || '')).filter(Boolean)) as string[]
  const [approve, setApprove] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(probeIds.map((id) => [id, true])),
  )
  const [scenarios, setScenarios] = useState<string[]>([''])
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [skipBiz, setSkipBiz] = useState(false)
  const [busy, setBusy] = useState(false)
  const [localErr, setLocalErr] = useState<string | null>(null)

  const questions = draft.business_questions || []
  const needsBiz = Boolean(draft.needs_business_followup) && !skipBiz

  async function onContinue(e: React.FormEvent) {
    e.preventDefault()
    setLocalErr(null)
    const extras = scenarios.map((s) => s.trim()).filter(Boolean)
    if (extras.length > MAX_SCENARIOS) {
      setLocalErr(`At most ${MAX_SCENARIOS} scenarios`)
      return
    }
    if (needsBiz) {
      const missing = questions.filter((q) => !String(answers[q.id] || '').trim())
      if (missing.length) {
        setLocalErr('Answer business questions or skip follow-up')
        return
      }
    }
    const body: HitlApprovalBody = {
      approve: probeIds.filter((id) => approve[id]),
      extra_scenarios: extras,
      business_answers: answers,
      skip_business_followup: skipBiz,
    }
    setBusy(true)
    try {
      await api.submitScenarios(jobId, body)
      const j = await api.job(jobId)
      onSubmitted(j)
    } catch (ex) {
      setLocalErr(ex instanceof Error ? ex.message : String(ex))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="hitl panel" aria-label="Human review">
      <h2>Human review</h2>
      <p className="hint">
        Approve or drop drafted probes, add business scenarios, then continue. Freeze happens after you
        submit.
      </p>

      {(draft.claims || []).length > 0 && (
        <div className="hitl-claims">
          <h3>Claims</h3>
          <ul>
            {(draft.claims || []).map((c) => (
              <li key={String(c.id)}>
                <strong>{String(c.id)}</strong> — {String(c.text || '')}
              </li>
            ))}
          </ul>
        </div>
      )}

      <form onSubmit={(e) => void onContinue(e)} className="hitl-form">
        <h3>Draft probes</h3>
        {probeIds.length === 0 ? (
          <p className="empty">No draft probes — add scenarios below or continue empty.</p>
        ) : (
          <ul className="hitl-probes">
            {probeIds.map((id) => {
              const preview = (draft.probes || []).find((p) => p.id === id)
              return (
                <li key={id}>
                  <label className="hitl-probe-row">
                    <input
                      type="checkbox"
                      checked={Boolean(approve[id])}
                      onChange={(e) => setApprove((a) => ({ ...a, [id]: e.target.checked }))}
                    />
                    <span>
                      <code>{id}</code>
                      {preview?.about ? <> — {preview.about}</> : null}
                    </span>
                  </label>
                </li>
              )
            })}
          </ul>
        )}

        <h3>Business scenarios</h3>
        <p className="hint">Add one or more scenarios the probes should cover (max {MAX_SCENARIOS}).</p>
        <div className="scenario-list">
          {scenarios.map((s, i) => (
            <div key={i} className="scenario-row">
              <input
                value={s}
                onChange={(e) =>
                  setScenarios((rows) => rows.map((x, j) => (j === i ? e.target.value : x)))
                }
                placeholder={`Scenario ${i + 1}`}
                aria-label={`Scenario ${i + 1}`}
              />
              <button
                type="button"
                className="ghost"
                disabled={scenarios.length <= 1}
                onClick={() => setScenarios((rows) => rows.filter((_, j) => j !== i))}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
        <button
          type="button"
          className="ghost"
          disabled={scenarios.length >= MAX_SCENARIOS}
          onClick={() => setScenarios((rows) => (rows.length >= MAX_SCENARIOS ? rows : [...rows, '']))}
        >
          Add another
        </button>

        {Boolean(draft.needs_business_followup) && (
          <div className="hitl-biz">
            <h3>Business follow-up</h3>
            <label className="hitl-probe-row">
              <input type="checkbox" checked={skipBiz} onChange={(e) => setSkipBiz(e.target.checked)} />
              <span>Skip business follow-up</span>
            </label>
            {!skipBiz &&
              questions.map((q) => (
                <label key={q.id}>
                  {q.prompt}
                  <input
                    value={answers[q.id] || ''}
                    onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                    required={needsBiz}
                  />
                </label>
              ))}
          </div>
        )}

        {localErr && (
          <p className="banner err" role="alert">
            {localErr}
          </p>
        )}
        <button type="submit" disabled={busy}>
          {busy ? 'Submitting…' : 'Continue check'}
        </button>
      </form>
    </section>
  )
}

function prNumber(record: Record<string, unknown>): number | null {
  const pr = record.pr
  if (typeof pr === 'number') return pr
  if (pr && typeof pr === 'object' && typeof (pr as { number?: unknown }).number === 'number') {
    return (pr as { number: number }).number
  }
  return null
}

function plainVerdict(v: string): string {
  if (v === 'verified') return 'Verified — behaviour matches the claims'
  if (v === 'needs_attention') return 'Needs attention — review the findings below'
  if (v === 'could_not_verify') return 'Could not verify — the check could not finish safely'
  return v || 'No verdict'
}

type ClaimRow = {
  id: string
  text: string
  expect?: string
  source_quote?: string
  source?: string
}

type ObsRow = {
  name?: string
  state?: string
  label?: string
  claim?: string | null
}

function claimsFromRecord(record: Record<string, unknown>): ClaimRow[] {
  const plan = record.probe_plan as { model_claims?: ClaimRow[] } | undefined
  if (Array.isArray(plan?.model_claims) && plan!.model_claims!.length) {
    return plan!.model_claims!.map((c) => ({
      id: String(c.id || ''),
      text: String(c.text || ''),
      expect: c.expect ? String(c.expect) : undefined,
      source_quote: c.source_quote ? String(c.source_quote) : undefined,
      source: c.source ? String(c.source) : undefined,
    }))
  }
  const top = record.behaviour_claims as ClaimRow[] | undefined
  if (Array.isArray(top) && top.length) {
    return top.map((c) => ({
      id: String(c.id || ''),
      text: String(c.text || ''),
      expect: c.expect ? String(c.expect) : undefined,
      source_quote: c.source_quote ? String(c.source_quote) : undefined,
      source: c.source ? String(c.source) : undefined,
    }))
  }
  const seen = new Map<string, ClaimRow>()
  for (const p of probeItems(record)) {
    for (const c of (p.claims as ClaimRow[] | undefined) || []) {
      const id = String(c.id || '')
      if (!id || seen.has(id)) continue
      seen.set(id, {
        id,
        text: String(c.text || ''),
        expect: c.expect ? String(c.expect) : undefined,
        source: c.source ? String(c.source) : undefined,
      })
    }
  }
  return [...seen.values()]
}

function probeItems(record: Record<string, unknown>): Array<Record<string, unknown>> {
  return ((record.probes as { items?: Array<Record<string, unknown>> }) || {}).items || []
}

function observationsForClaim(record: Record<string, unknown>, claimId: string): ObsRow[] {
  const out: ObsRow[] = []
  for (const p of probeItems(record)) {
    for (const o of (p.observations as ObsRow[] | undefined) || []) {
      if (String(o.claim || '') === claimId) out.push(o)
    }
  }
  return out
}

function claimResultLabel(obs: ObsRow[]): string {
  if (!obs.length) return 'not probed'
  if (obs.some((o) => ['needs_attention', 'needs_human', 'false'].includes(String(o.label || '')))) {
    return 'needs attention'
  }
  if (obs.some((o) => o.label === 'proven')) return 'proven'
  return String(obs[0]?.label || obs[0]?.state || 'checked')
}

function agentRoles(record: Record<string, unknown>): Array<Record<string, unknown>> {
  return ((record.agents as { roles?: Array<Record<string, unknown>> }) || {}).roles || []
}

function unwrapSummary(raw: string): string {
  const t = raw.trim()
  if (!t.startsWith('{')) return t
  try {
    const inner = JSON.parse(t) as { summary?: unknown; text?: unknown }
    const s = inner.summary ?? inner.text
    if (typeof s === 'string' && s.trim()) return s.trim()
  } catch {
    /* keep raw */
  }
  return t
}

function summaryText(record: Record<string, unknown>): string {
  const expl = (record.explanation as { text?: string }) || {}
  if (typeof expl.text === 'string' && expl.text.trim()) return unwrapSummary(expl.text)
  const helper = agentRoles(record).find((r) => r.role === 'helper')
  const notes = Array.isArray(helper?.notes) ? (helper!.notes as string[]) : []
  const claims = claimsFromRecord(record)
  const lines = [
    `Code verdict: ${String(record.verdict || 'unknown')}.`,
    String(record.reason || '').trim(),
  ]
  if (claims.length) {
    lines.push('Claims under test:')
    for (const c of claims) {
      const obs = observationsForClaim(record, c.id)
      lines.push(`• ${c.id} (${claimResultLabel(obs)}): ${c.text}`)
    }
  }
  if (notes.length) {
    lines.push('Lightning notes:')
    for (const n of notes.slice(0, 5)) lines.push(`• ${n}`)
  }
  return lines.filter(Boolean).join('\n')
}

function testGlance(record: Record<string, unknown>): string[] {
  const c = (record.comparison as Record<string, unknown>) || {}
  const rows: string[] = []
  const n = (k: string) => (Array.isArray(c[k]) ? (c[k] as unknown[]).length : 0)
  if (n('new_tests_passing')) rows.push(`${n('new_tests_passing')} new test(s) passed on the PR`)
  if (n('new_tests_failing')) rows.push(`${n('new_tests_failing')} new test(s) failed on the PR`)
  if (n('regressions')) rows.push(`${n('regressions')} regression(s) vs main`)
  if (n('fixed')) rows.push(`${n('fixed')} previously failing test(s) now pass`)
  if (n('reparametrized')) rows.push(`${n('reparametrized')} re-parametrized test(s)`)
  if (n('same_skipped_both')) rows.push(`${n('same_skipped_both')} skipped on both sides`)
  const dur = record.duration_s as { total_wall?: number; tests?: number } | undefined
  if (dur?.total_wall) rows.push(`Wall time ~${Math.round(Number(dur.total_wall) / 60)} min`)
  return rows
}

function RunAnalysis({ record }: { record: Record<string, unknown> }) {
  const claims = claimsFromRecord(record)
  const probes = probeItems(record)
  const roles = agentRoles(record)
  const judge = roles.find((r) => r.role === 'judge')
  const helper = roles.find((r) => r.role === 'helper')
  const labels = (Array.isArray(judge?.labels) ? judge!.labels : []) as Array<Record<string, unknown>>
  const notes = (Array.isArray(helper?.notes) ? helper!.notes : []) as string[]
  const glance = testGlance(record)
  const summary = summaryText(record)

  return (
    <div className="map analysis">
      <section>
        <h2>In plain English</h2>
        <pre className="summary-block">{summary}</pre>
      </section>

      <section>
        <h2>Claims under test</h2>
        <p className="hint">
          Each claim (C1, C2, …) is a behaviour statement extracted from the PR. Probes check whether
          main vs PR match what the claim says should stay the same or change.
        </p>
        {claims.length === 0 ? (
          <p className="empty">No claims were extracted for this run.</p>
        ) : (
          <ul className="claim-list">
            {claims.map((c) => {
              const obs = observationsForClaim(record, c.id)
              return (
                <li key={c.id} className="claim-card">
                  <header>
                    <strong>{c.id}</strong>
                    <span className={`claim-badge ${claimResultLabel(obs).replace(/\s+/g, '-')}`}>
                      {claimResultLabel(obs)}
                    </span>
                    {c.expect ? <span className="claim-expect">expect: {c.expect}</span> : null}
                  </header>
                  <p className="claim-text">{c.text}</p>
                  {c.source_quote ? (
                    <blockquote className="claim-quote">From the PR: {c.source_quote}</blockquote>
                  ) : null}
                  {obs.length > 0 && (
                    <ul className="obs-list">
                      {obs.map((o, i) => (
                        <li key={`${o.name}-${i}`}>
                          <code>{String(o.name || 'observation')}</code>
                          {' — '}
                          {String(o.label || o.state || '')}
                          {o.state ? ` (state: ${o.state})` : ''}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </section>

      <section>
        <h2>Probes (how claims were checked)</h2>
        <p className="hint">
          A probe is a small dual-run script: same inputs on main and on the PR. The observation says
          whether the result differed.
        </p>
        {probes.length === 0 ? (
          <p className="empty">No probes ran.</p>
        ) : (
          <ul className="probe-list">
            {probes.map((p, i) => (
              <li key={String(p.id ?? i)} className="probe-card">
                <header>
                  <code>{String(p.id ?? '')}</code>
                  <span className="muted">{String(p.status ?? '')}</span>
                </header>
                <p>{String(p.about ?? '')}</p>
                {Array.isArray(p.claims) && (p.claims as ClaimRow[]).length > 0 && (
                  <p className="probe-claims">
                    Covers{' '}
                    {(p.claims as ClaimRow[]).map((c) => c.id).filter(Boolean).join(', ')}
                  </p>
                )}
                {Array.isArray(p.observations) && (p.observations as ObsRow[]).length > 0 && (
                  <ul className="obs-list">
                    {(p.observations as ObsRow[]).map((o, j) => (
                      <li key={`${String(p.id)}-${j}`}>
                        <code>{String(o.name || '')}</code>
                        {o.claim ? <> · claim {String(o.claim)}</> : null}
                        {' — '}
                        <strong>{String(o.label || o.state || '')}</strong>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {glance.length > 0 && (
        <section>
          <h2>Project tests</h2>
          <ul className="glance-list">
            {glance.map((g) => (
              <li key={g}>{g}</li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h2>Agent swarm (advisory)</h2>
        <p className="hint">Ultra / Lightning / Super do not change the code verdict; they explain it.</p>
        {labels.length > 0 && (
          <>
            <h3>Ultra (judge)</h3>
            <ul className="agent-findings">
              {labels.map((lab, i) => (
                <li key={String(lab.id ?? i)}>
                  <strong>{String(lab.label ?? '')}</strong> on <code>{String(lab.id ?? '')}</code>
                  {lab.reason ? <> — {String(lab.reason)}</> : null}
                </li>
              ))}
            </ul>
          </>
        )}
        {notes.length > 0 && (
          <>
            <h3>Lightning (helper)</h3>
            <ul className="agent-findings">
              {notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </>
        )}
        {labels.length === 0 && notes.length === 0 && (
          <p className="empty">No agent notes recorded for this run.</p>
        )}
      </section>
    </div>
  )
}
