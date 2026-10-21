import { useEffect, useState } from 'react'
import { ProcessDag } from './dag'
import { costTime, filterRuns, prNumber, verdictPlain, verdictTone } from './present'
import { fetchReplay, replayFile, type ReplayCatalog, type ReplayCheck } from './replayData'
import { CostTimePanel, EvidenceLinks, ReasonList, RunAnalysis, VerdictBadge } from './ui'

type Records = Record<string, Record<string, unknown>>

function rowOf(check: ReplayCheck) {
  return {
    id: check.id,
    repo: check.repo,
    pr: check.pr ?? undefined,
    url: check.url ?? undefined,
    title: check.title,
    verdict: check.verdict,
    reason: check.reason,
    tested_at_ist: check.tested_at_ist,
  }
}

export function ReplayConsole({
  catalog,
  records,
  initialId = null,
}: {
  catalog: ReplayCatalog
  records: Records
  initialId?: string | null
}) {
  const [current, setCurrent] = useState<string | null>(initialId)
  const [query, setQuery] = useState('')
  const checks = catalog.checks || []
  const visible = filterRuns(checks.map(rowOf), query, 'all')
  const selected = checks.find((check) => check.id === current) || null
  const record = selected ? records[selected.id] : null
  const reportHref = selected?.report_html ? replayFile(import.meta.env.BASE_URL || './', selected.report_html) : null

  useEffect(() => {
    if (initialId) return
    const apply = () => {
      const match = window.location.hash.match(/^#\/run\/([^/]+)$/)
      setCurrent(match ? decodeURIComponent(match[1]) : null)
    }
    apply()
    window.addEventListener('hashchange', apply)
    return () => window.removeEventListener('hashchange', apply)
  }, [initialId])

  function openRun(id: string | null) {
    setCurrent(id)
    const hash = id ? `#/run/${encodeURIComponent(id)}` : '#/'
    if (typeof window !== 'undefined' && window.location.hash !== hash) {
      window.history.pushState(null, '', hash)
    }
  }

  return (
    <div className="shell">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="top">
        <div className="brand-block">
          <button type="button" className="brand" onClick={() => openRun(null)}>
            Proof-of-Change
          </button>
          <p className="tag">Finished checks. Nothing is installed and no API is called.</p>
        </div>
        <div className="top-actions">
          <span className="pill on">Replay</span>
        </div>
      </header>
      <p className="banner note" role="status">
        {catalog.note || 'This page replays finished checks.'} To ask for a new check, open a Request a check issue.
        To run one yourself, open a GitHub Codespace. Live checks need Linux.
      </p>
      <main id="main">
        {selected && record ? (
          <article className="verdict-page">
            <button type="button" className="ghost back" onClick={() => openRun(null)}>
              Back
            </button>
            <p className="kicker">
              {String(record.repo || selected.repo || '')}
              {prNumber(record) != null ? `#${prNumber(record)}` : ''}
              {selected.kind === 'release' ? ' · release comparison' : ''}
            </p>
            <div className="verdict-hero">
              <VerdictBadge verdict={String(record.verdict || selected.verdict || '')} large />
              <h1>{verdictPlain(String(record.verdict || selected.verdict || ''))}</h1>
            </div>
            <p className="lede code-owns">
              Code verdict <code>{String(record.verdict || selected.verdict || '')}</code>
            </p>
            <ProcessDag record={record} />
            <ReasonList reason={String(record.reason || selected.reason || '')} />
            <h2>Cost and time</h2>
            <CostTimePanel cost={costTime(record)} />
            <h2>Evidence</h2>
            <EvidenceLinks record={record} html={reportHref} />
            <RunAnalysis record={record} />
            {reportHref ? (
              <section className="panel" aria-label="Report">
                <h2>Report</h2>
                <iframe className="report-frame" title="Report" src={reportHref} sandbox="" />
              </section>
            ) : null}
          </article>
        ) : (
          <div className="home">
            <section className="panel" aria-labelledby="how-heading">
              <ProcessDag />
              <h2 id="how-heading">How a check runs</h2>
              <p className="hint">The same stages as a live check. These cards are already finished.</p>
            </section>
            <section className="panel runs-panel" aria-labelledby="runs-heading">
              <h2 id="runs-heading">Finished checks</h2>
              <div className="filters">
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
              </div>
              {visible.length === 0 ? (
                <p className="empty">No finished checks match that filter.</p>
              ) : (
                <ul className="run-cards">
                  {visible.map((run) => (
                    <li key={run.id}>
                      <article className={`run-card tone-${verdictTone(run.verdict)}`}>
                        <button type="button" className="run-open" onClick={() => openRun(run.id)}>
                          <VerdictBadge verdict={run.verdict} />
                          <span className="run-title">
                            {run.repo}
                            {run.pr != null ? `#${run.pr}` : ''}
                          </span>
                          <span className="run-sub">{run.title || run.id}</span>
                          <span className="when">{run.tested_at_ist || 'time not recorded'}</span>
                        </button>
                      </article>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  )
}

export default function ReplayApp() {
  const [loaded, setLoaded] = useState<{ catalog: ReplayCatalog; records: Records } | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    void fetchReplay(fetch)
      .then((payload) => {
        if (live) setLoaded(payload)
      })
      .catch((error: unknown) => {
        if (live) setErr(error instanceof Error ? error.message : String(error))
      })
    return () => {
      live = false
    }
  }, [])
  if (err) {
    return (
      <p className="banner err" role="alert">
        {err}
      </p>
    )
  }
  if (!loaded) return <p className="empty">Loading finished checks…</p>
  return <ReplayConsole catalog={loaded.catalog} records={loaded.records} />
}
