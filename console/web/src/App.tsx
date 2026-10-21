import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  api,
  lostJobMessage,
  type Account,
  type HitlApprovalBody,
  type HitlDraft,
  type Job,
  type RunRow,
} from './api'
import { ProcessDag } from './dag'
import {
  TIMELINE_SPEC,
  costTime,
  filterRuns,
  illustrativeStates,
  prNumber,
  timelineStates,
  verdictPlain,
  verdictTone,
} from './present'
import {
  CostTimePanel,
  DetailRail,
  EvidenceLinks,
  HelperNotes,
  LiveLog,
  ReasonList,
  RunAnalysis,
  SwarmTheater,
  Timeline,
  VerdictBadge,
} from './ui'
import './App.css'

const MAX_SCENARIOS = 20
const SAMPLE_PR_URL = 'https://github.com/rasbt/mlxtend/pull/1229'
const SAMPLE_PROVIDER = 'recorded'
const VERDICT_FILTERS = ['all', 'verified', 'needs_attention', 'could_not_verify', 'no_code_change'] as const

type CachedRun = {
  id: string
  row: RunRow
  record: Record<string, unknown>
  folder: string
  saved_at: number
}

type View = { name: 'home' } | { name: 'run'; id: string } | { name: 'job'; id: string }

function runsStorageKey(accountId: string | null) {
  return accountId ? `poc-console-runs-v1:${accountId}` : 'poc-console-runs-v1:signed-out'
}

function loadLocalRuns(accountId: string | null): CachedRun[] {
  try {
    const raw = localStorage.getItem(runsStorageKey(accountId))
    const parsed = raw ? (JSON.parse(raw) as CachedRun[]) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveLocalRun(accountId: string | null, entry: CachedRun) {
  const rest = loadLocalRuns(accountId).filter((run) => run.id !== entry.id)
  localStorage.setItem(runsStorageKey(accountId), JSON.stringify([entry, ...rest].slice(0, 30)))
}

function mergeRunLists(apiRuns: RunRow[], local: CachedRun[]): RunRow[] {
  const seen = new Set(apiRuns.map((run) => run.id))
  const extra = local.filter((cached) => !seen.has(cached.id)).map((cached) => ({ ...cached.row, source: 'browser' }))
  return [...apiRuns, ...extra]
}

function viewFromHash(hash: string): View {
  const path = hash.replace(/^#/, '')
  const run = path.match(/^\/run\/([^/]+)$/)
  if (run) return { name: 'run', id: decodeURIComponent(run[1]) }
  const job = path.match(/^\/job\/([^/]+)$/)
  if (job) return { name: 'job', id: decodeURIComponent(job[1]) }
  return { name: 'home' }
}

function hashFor(view: View): string {
  if (view.name === 'run') return `#/run/${encodeURIComponent(view.id)}`
  if (view.name === 'job') return `#/job/${encodeURIComponent(view.id)}`
  return '#/'
}

function useIllustrativeFrame(active: boolean) {
  const [frame, setFrame] = useState(-1)
  useEffect(() => {
    if (!active) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const id = window.setInterval(() => {
      setFrame((current) => (current + 1) % (TIMELINE_SPEC.length + 2))
    }, 1400)
    return () => window.clearInterval(id)
  }, [active])
  return frame
}

function providerBadge(provider?: string) {
  if (provider === 'recorded') return { className: 'badge fixture', label: 'Prerecorded fixture (not blind)' }
  if (provider === 'none') return { className: 'badge muted', label: 'No AI (fixed probes only)' }
  if (provider === 'nebius') return { className: 'badge live', label: 'Live Nebius / Nemotron' }
  return null
}

export default function App() {
  const [account, setAccount] = useState<Account | null>(null)
  const [view, setView] = useState<View>(() => viewFromHash(window.location.hash))
  const [runs, setRuns] = useState<RunRow[]>([])
  const [query, setQuery] = useState('')
  const [verdictFilter, setVerdictFilter] = useState<(typeof VERDICT_FILTERS)[number]>('all')
  const [err, setErr] = useState<string | null>(null)
  const [apiOk, setApiOk] = useState<boolean | null>(null)
  const [healthNote, setHealthNote] = useState<string | null>(null)
  const [contreeReady, setContreeReady] = useState<boolean | null>(null)
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
  const frame = useIllustrativeFrame(view.name === 'home')

  const go = useCallback((next: View) => {
    setView(next)
    const hash = hashFor(next)
    if (window.location.hash !== hash) window.history.pushState(null, '', hash)
  }, [])

  useEffect(() => {
    const sync = () => setView(viewFromHash(window.location.hash))
    window.addEventListener('hashchange', sync)
    window.addEventListener('popstate', sync)
    return () => {
      window.removeEventListener('hashchange', sync)
      window.removeEventListener('popstate', sync)
    }
  }, [])

  const refresh = useCallback(async () => {
    setRefreshing(true)
    try {
      const health = await api.health()
      setApiOk(health.ok)
      setContreeReady(Boolean(health.contree_ready))
      setHealthNote(health.run_note || null)
      const remote = (await api.runs()).runs
      setRuns(mergeRunLists(remote, loadLocalRuns(account?.id || null)))
      setErr(null)
    } catch (error) {
      setApiOk(false)
      setHealthNote(null)
      setContreeReady(null)
      setRuns((prev) => (prev.length ? prev : mergeRunLists([], loadLocalRuns(account?.id || null))))
      setErr(error instanceof Error ? error.message : String(error))
    } finally {
      setRefreshing(false)
    }
  }, [account?.id])

  useEffect(() => {
    void api.me().then(setAccount).catch(() => setAccount(null))
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (view.name !== 'run') return
    setDetail((current) => (current && String(current.record.id || '') === view.id ? current : null))
    void api
      .run(view.id)
      .then((payload) => {
        setDetail({
          record: payload.record,
          folder: payload.folder,
          hosted_report: payload.hosted_report,
          report_pdf: payload.report_pdf,
          report_html: payload.report_html,
        })
        if (payload.record && payload.record.id) {
          const pr = payload.record.pr as { number?: number; url?: string; title?: string } | undefined
          saveLocalRun(account?.id || null, {
            id: String(payload.record.id),
            row: {
              id: String(payload.record.id),
              repo: String(payload.record.repo || ''),
              pr: pr?.number,
              url: pr?.url,
              title: pr?.title || String(payload.record.title || ''),
              verdict: String(payload.record.verdict || ''),
              reason: String(payload.record.reason || '').slice(0, 240),
              tested_at_ist: String(payload.record.tested_at_ist || payload.record.date_ist || ''),
              machine: String(payload.record.machine || 'local'),
              folder: payload.folder,
              report_pdf: payload.report_pdf,
              report_html: payload.report_html,
            },
            record: payload.record,
            folder: payload.folder,
            saved_at: Date.now(),
          })
        }
      })
      .catch((error) => {
        const cached = loadLocalRuns(account?.id || null).find((entry) => entry.id === view.id)
        if (cached) {
          setDetail({
            record: cached.record,
            folder: cached.folder,
            hosted_report: null,
            report_pdf: cached.row.report_pdf,
            report_html: cached.row.report_html,
          })
          setErr(null)
          return
        }
        setErr(error instanceof Error ? error.message : String(error))
      })
  }, [view, account?.id])

  useEffect(() => {
    if (view.name !== 'job') return
    setJob(null)
    let stop = false
    let retries = 0
    const tick = async () => {
      try {
        const next = await api.job(view.id)
        if (stop) return
        retries = 0
        setJob(next)
        setErr(null)
        if (next.status === 'done' || next.status === 'failed' || next.status === 'timed out') {
          if (next.record && next.run_id) {
            const pr = next.record.pr as { number?: number; url?: string; title?: string } | undefined
            saveLocalRun(account?.id || null, {
              id: next.run_id,
              row: {
                id: next.run_id,
                repo: String(next.record.repo || next.repo || ''),
                pr: pr?.number ?? next.pr,
                url: pr?.url || next.pr_url,
                title: pr?.title || String(next.record.title || ''),
                verdict: String(next.record.verdict || ''),
                reason: String(next.record.reason || '').slice(0, 240),
                tested_at_ist: String(next.record.tested_at_ist || ''),
                machine: String(next.record.machine || 'local'),
                folder: next.folder || '',
                report_pdf: next.report_pdf,
                report_html: next.report_html,
              },
              record: next.record,
              folder: next.folder || '',
              saved_at: Date.now(),
            })
          }
          void refresh()
          if (next.status === 'done' && next.run_id) {
            go({ name: 'run', id: next.run_id })
            if (next.record) {
              setDetail({
                record: next.record,
                folder: next.folder || '',
                hosted_report: null,
                report_pdf: next.report_pdf,
                report_html: next.report_html,
              })
            }
          }
          return
        }
        window.setTimeout(() => void tick(), 1500)
      } catch (error) {
        if (stop) return
        const lost = lostJobMessage(error)
        if (lost) {
          setErr(lost)
          go({ name: 'home' })
          return
        }
        retries += 1
        if (retries < 4) {
          window.setTimeout(() => void tick(), 1000 * retries)
          return
        }
        setErr(error instanceof Error ? error.message : String(error))
        window.setTimeout(() => void tick(), 4000)
      }
    }
    void tick()
    return () => {
      stop = true
    }
  }, [view, refresh, go, account?.id])

  async function refreshJob() {
    if (view.name !== 'job') return
    setJobRefreshing(true)
    try {
      setJob(await api.job(view.id))
      setErr(null)
    } catch (error) {
      const lost = lostJobMessage(error)
      if (lost) {
        setErr(lost)
        go({ name: 'home' })
        return
      }
      setErr(error instanceof Error ? error.message : String(error))
    } finally {
      setJobRefreshing(false)
    }
  }

  async function signOut() {
    try {
      await api.logout()
    } catch {
      /* the cookie is cleared when the server accepts it */
    }
    window.location.hash = '#/'
    window.location.reload()
  }

  async function startWith(url: string, prov: string) {
    setBusy(true)
    setErr(null)
    try {
      const started = await api.startCheck(url.trim(), prov)
      setJob(started)
      go({ name: 'job', id: started.id })
    } catch (error) {
      setErr(error instanceof Error ? error.message : String(error))
    } finally {
      setBusy(false)
    }
  }

  const visibleRuns = filterRuns(runs, query, verdictFilter)
  const jobBadge = providerBadge(job?.model_provider)

  return (
    <div className="shell">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="top">
        <div className="brand-block">
          <button type="button" className="brand" onClick={() => go({ name: 'home' })}>
            Proof-of-Change
          </button>
          <p className="tag">NVIDIA Nemotron on Nebius. Paste a pull request and watch the check.</p>
        </div>
        <div className="top-actions">
          {account?.email ? <span className="pill">{account.email}</span> : null}
          <button type="button" className="ghost" onClick={() => void signOut()}>
            Log out
          </button>
          <span className={`pill ${apiOk ? 'on' : 'off'}`}>{apiOk == null ? '…' : apiOk ? 'API up' : 'API down'}</span>
        </div>
      </header>

      {err ? (
        <p className="banner err" role="alert">
          {err}
          {apiOk === false ? ' — start the API with make console-api' : ''}
        </p>
      ) : null}
      {healthNote ? (
        <p className="banner warn" role="status">
          Sandbox: {healthNote}
          {contreeReady === false ? ' Contree is not ready.' : ''}
        </p>
      ) : null}

      <main id="main">
        {view.name === 'home' ? (
          <div className="home">
            <section className="panel start">
              <p className="kicker">Operator console</p>
              <h1>Check a pull request</h1>
              <p className="lede">
                The code verdict is computed by the checker. Ultra, Lightning and Super only advise — they do not
                change it.
              </p>
              <form
                onSubmit={(event) => {
                  event.preventDefault()
                  void startWith(prUrl, provider)
                }}
                className="form"
              >
                <label htmlFor="pr-url">Pull request URL</label>
                <div className="url-row">
                  <input
                    id="pr-url"
                    value={prUrl}
                    onChange={(event) => setPrUrl(event.target.value)}
                    placeholder="https://github.com/owner/repo/pull/123"
                    required
                    autoComplete="off"
                  />
                  <button type="submit" disabled={busy || !prUrl.trim()}>
                    {busy ? 'Starting…' : 'Run check'}
                  </button>
                </div>
                <label htmlFor="provider">Model provider</label>
                <select id="provider" value={provider} onChange={(event) => setProvider(event.target.value)}>
                  <option value="nebius">nebius (live Nemotron)</option>
                  <option value="none">none (no AI)</option>
                  <option value="recorded">recorded (prerecorded fixture)</option>
                </select>
                <button
                  type="button"
                  className="ghost sample"
                  disabled={busy}
                  onClick={() => {
                    setPrUrl(SAMPLE_PR_URL)
                    setProvider(SAMPLE_PROVIDER)
                    void startWith(SAMPLE_PR_URL, SAMPLE_PROVIDER)
                  }}
                >
                  Try sample (mlxtend#1229, prerecorded)
                </button>
              </form>
              <p className="hint">
                The sample uses a committed fixture and is labelled not blind. Live Nebius needs an API key.
              </p>
            </section>

            <section className="panel" aria-labelledby="how-heading">
              <ProcessDag />
              <h2 id="how-heading">How a check runs</h2>
              <p className="hint">An illustration of the stages. A live check replaces this with real progress.</p>
              <Timeline steps={illustrativeStates(frame)} illustrative />
            </section>

            <section className="panel runs-panel" aria-labelledby="runs-heading">
              <div className="row">
                <h2 id="runs-heading">{account?.role === 'admin' ? 'All runs' : 'My runs'}</h2>
                <button type="button" className="ghost" onClick={() => void refresh()} disabled={refreshing}>
                  {refreshing ? 'Refreshing…' : 'Refresh'}
                </button>
              </div>
              <div className="filters" role="toolbar" aria-label="Filter past runs">
                <label className="filter-search" htmlFor="run-filter">
                  Search
                  <input
                    id="run-filter"
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Repo, title, or number"
                  />
                </label>
                <div className="chips" role="group" aria-label="Verdict">
                  {VERDICT_FILTERS.map((value) => (
                    <button
                      key={value}
                      type="button"
                      className="chip"
                      aria-pressed={verdictFilter === value}
                      onClick={() => setVerdictFilter(value)}
                    >
                      {value === 'all' ? 'All' : value.replaceAll('_', ' ')}
                    </button>
                  ))}
                </div>
              </div>
              {runs.length === 0 ? (
                <p className="empty">
                  No runs yet. Finished checks are also kept in this browser, because a free host may wipe its disk
                  when it sleeps.
                </p>
              ) : visibleRuns.length === 0 ? (
                <p className="empty">No runs match that filter.</p>
              ) : (
                <ul className="run-cards">
                  {visibleRuns.map((run) => (
                    <li key={run.id}>
                      <article className={`run-card tone-${verdictTone(run.verdict)}`}>
                        <button type="button" className="run-open" onClick={() => go({ name: 'run', id: run.id })}>
                          <VerdictBadge verdict={run.verdict} />
                          <span className="run-title">
                            {run.repo}
                            {run.pr != null ? `#${run.pr}` : ''}
                          </span>
                          <span className="run-sub">{run.title || run.id}</span>
                          <span className="when">
                            {run.tested_at_ist || 'time not recorded'}
                            {run.source === 'browser' ? ' · saved in this browser' : ''}
                          </span>
                        </button>
                        {run.report_pdf ? (
                          <a className="pdf-link" href={run.report_pdf} download>
                            Download PDF
                          </a>
                        ) : null}
                      </article>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        ) : null}

        {view.name === 'job' && job ? (
          <div className="job">
            <div className="job-toolbar">
              <button type="button" className="ghost back" onClick={() => go({ name: 'home' })}>
                Back
              </button>
              <button type="button" className="ghost" onClick={() => void refreshJob()} disabled={jobRefreshing}>
                {jobRefreshing ? 'Refreshing…' : 'Refresh'}
              </button>
            </div>
            <p className="kicker">
              {job.repo}#{job.pr} · <strong>{job.status}</strong>
              {jobBadge ? <span className={jobBadge.className}>{jobBadge.label}</span> : null}
            </p>
            <h1>{job.model_provider === 'recorded' ? 'Prerecorded check' : job.model_provider === 'none' ? 'Check (AI off)' : 'Live check'}</h1>
            {(job.run_note || job.warning) && !job.error ? (
              <p className="banner warn" role="status">
                {job.run_note || job.warning}
              </p>
            ) : null}
            <ProcessDag events={job.stages} record={job.record} log={job.log_tail} />
            <Timeline
              steps={timelineStates(job.stages || [], job.current_stage)}
              caption={job.current_detail || job.status}
            />
            <HelperNotes notes={job.helper_notes} />
            <SwarmTheater swarm={job.swarm} currentAgent={job.current_agent} detail={job.current_detail} />
            {job.status === 'awaiting_human' && job.hitl_draft ? (
              <HitlPanel jobId={job.id} draft={job.hitl_draft} onSubmitted={(next) => setJob(next)} />
            ) : null}
            {job.error ? (
              <p className="banner err" role="alert">
                {job.error}
              </p>
            ) : null}
            {job.run_id ? (
              <p className="report-links">
                <button type="button" className="linkish" onClick={() => go({ name: 'run', id: job.run_id! })}>
                  Open analysis {job.run_id}
                </button>
                {job.report_pdf ? (
                  <a className="btn-report" href={job.report_pdf}>
                    Download PDF
                  </a>
                ) : null}
                {job.report_html ? (
                  <a className="btn-report ghost" href={job.report_html} target="_blank" rel="noreferrer">
                    Open HTML report
                  </a>
                ) : null}
              </p>
            ) : null}
            <section className="panel" aria-label="Live console log">
              <h2>Live log</h2>
              <LiveLog text={job.log_tail} running={job.status === 'running' || job.status === 'queued'} />
            </section>
            <details className="panel disclosure">
              <summary>All stages</summary>
              <DetailRail stages={job.stages || []} current={job.current_stage} />
            </details>
          </div>
        ) : null}

        {view.name === 'job' && !job ? <p className="empty">Loading the check…</p> : null}

        {view.name === 'run' && !detail ? <p className="empty">Loading the run…</p> : null}

        {view.name === 'run' && detail ? (
          <article className="verdict-page">
            <button type="button" className="ghost back" onClick={() => go({ name: 'home' })}>
              Back
            </button>
            <p className="kicker">
              {String(detail.record.repo)}
              {prNumber(detail.record) != null ? `#${prNumber(detail.record)}` : ''}
            </p>
            <div className="verdict-hero">
              <VerdictBadge verdict={String(detail.record.verdict || '')} large />
              <h1>{verdictPlain(String(detail.record.verdict || ''))}</h1>
            </div>
            <p className="lede code-owns">
              Code verdict <code>{String(detail.record.verdict || '')}</code>
              {detail.record.machine ? (
                <>
                  {' '}
                  · ran on <code>{String(detail.record.machine)}</code>
                </>
              ) : null}
            </p>
            <ProcessDag record={detail.record} />
            <ReasonList reason={String(detail.record.reason || '')} />
            <h2>Cost and time</h2>
            <CostTimePanel cost={costTime(detail.record)} />
            <h2>Evidence</h2>
            <EvidenceLinks record={detail.record} pdf={detail.report_pdf} html={detail.report_html} />
            <RunAnalysis record={detail.record} />
            {detail.hosted_report ? (
              <p className="meta-line">
                Hosted report file: <code>{detail.hosted_report}</code>
              </p>
            ) : null}
          </article>
        ) : null}
      </main>
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
  onSubmitted: (job: Job) => void
}) {
  const probeIds = (draft.probe_ids || (draft.probes || []).map((probe) => String(probe.id || '')).filter(Boolean)) as string[]
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

  async function onContinue(event: FormEvent) {
    event.preventDefault()
    setLocalErr(null)
    const extras = scenarios.map((row) => row.trim()).filter(Boolean)
    if (extras.length > MAX_SCENARIOS) {
      setLocalErr(`At most ${MAX_SCENARIOS} scenarios`)
      return
    }
    if (needsBiz) {
      const missing = questions.filter((question) => !String(answers[question.id] || '').trim())
      if (missing.length) {
        setLocalErr('Answer the business questions, or skip the follow-up')
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
      onSubmitted(await api.job(jobId))
    } catch (error) {
      setLocalErr(error instanceof Error ? error.message : String(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="hitl panel" aria-label="Human review">
      <h2>Human review</h2>
      <p className="hint">Approve or drop the drafted probes, add business scenarios, then continue.</p>
      {(draft.claims || []).length > 0 ? (
        <div className="hitl-claims">
          <h3>Claims</h3>
          <ul>
            {(draft.claims || []).map((claim) => (
              <li key={String(claim.id)}>
                <strong>{String(claim.id)}</strong> — {String(claim.text || '')}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <form onSubmit={(event) => void onContinue(event)} className="hitl-form">
        <h3>Draft probes</h3>
        {probeIds.length === 0 ? (
          <p className="empty">No draft probes. Add scenarios below, or continue with none.</p>
        ) : (
          <ul className="hitl-probes">
            {probeIds.map((id) => {
              const preview = (draft.probes || []).find((probe) => probe.id === id)
              return (
                <li key={id}>
                  <label className="hitl-probe-row">
                    <input
                      type="checkbox"
                      checked={Boolean(approve[id])}
                      onChange={(event) => setApprove((current) => ({ ...current, [id]: event.target.checked }))}
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
        <p className="hint">One scenario per row, up to {MAX_SCENARIOS}.</p>
        <div className="scenario-list">
          {scenarios.map((value, index) => (
            <div key={index} className="scenario-row">
              <input
                value={value}
                onChange={(event) =>
                  setScenarios((rows) => rows.map((row, rowIndex) => (rowIndex === index ? event.target.value : row)))
                }
                placeholder={`Scenario ${index + 1}`}
                aria-label={`Scenario ${index + 1}`}
              />
              <button
                type="button"
                className="ghost"
                disabled={scenarios.length <= 1}
                onClick={() => setScenarios((rows) => rows.filter((_, rowIndex) => rowIndex !== index))}
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
        {draft.needs_business_followup ? (
          <div className="hitl-biz">
            <h3>Business follow-up</h3>
            <label className="hitl-probe-row">
              <input type="checkbox" checked={skipBiz} onChange={(event) => setSkipBiz(event.target.checked)} />
              <span>Skip business follow-up</span>
            </label>
            {!skipBiz
              ? questions.map((question) => (
                  <label key={question.id}>
                    {question.prompt}
                    <input
                      value={answers[question.id] || ''}
                      onChange={(event) => setAnswers((current) => ({ ...current, [question.id]: event.target.value }))}
                      required={needsBiz}
                    />
                  </label>
                ))
              : null}
          </div>
        ) : null}
        {localErr ? (
          <p className="banner err" role="alert">
            {localErr}
          </p>
        ) : null}
        <button type="submit" disabled={busy}>
          {busy ? 'Submitting…' : 'Continue check'}
        </button>
      </form>
    </section>
  )
}
