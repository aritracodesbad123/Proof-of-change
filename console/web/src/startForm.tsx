import { useState, type FormEvent } from 'react'
import type { Job } from './api'

/** Everything the start form sends in one request. Keys are blank unless the user typed one. */
export type StartFields = {
  prUrl: string
  provider: string
  approval: boolean
  nebiusKey: string
  tavilyKey: string
  /** Nebius project ID, used by the cloud sandbox. Shared with the Codespace sandbox routing. */
  nebiusProjectId: string
}

export type StartBody = {
  pr_url: string
  model_provider: string
  approval: boolean
  nebius_api_key?: string
  tavily_api_key?: string
  contree_project_id?: string
}

/** Request body for POST /api/checks. Blank keys are left out, so a key stored earlier this session is kept. */
export function startBody(fields: StartFields): StartBody {
  const body: StartBody = {
    pr_url: fields.prUrl.trim(),
    model_provider: fields.provider,
    approval: fields.approval,
  }
  if (fields.nebiusKey.trim()) body.nebius_api_key = fields.nebiusKey
  if (fields.tavilyKey.trim()) body.tavily_api_key = fields.tavilyKey
  if (fields.nebiusProjectId.trim()) body.contree_project_id = fields.nebiusProjectId
  return body
}

export type StartResult = { ok: true; job: Job } | { ok: false; error: string }

/** Submit the whole form once. Never throws: a failure always comes back as a message to show. */
export async function submitStart(
  fields: StartFields,
  start: (body: StartBody) => Promise<Job>,
): Promise<StartResult> {
  if (!fields.prUrl.trim()) return { ok: false, error: 'Add a pull request link.' }
  try {
    const job = await start(startBody(fields))
    if (!job || !job.id) return { ok: false, error: 'The check did not start. The server sent no check id.' }
    return { ok: true, job }
  } catch (error) {
    const text = error instanceof Error ? error.message : String(error)
    return { ok: false, error: text || 'The check did not start.' }
  }
}

/** Keys survive a refresh in this tab only: sessionStorage clears when the tab closes. Never localStorage or cookies. */
export const TAB_KEY_STORE = 'poc-start-keys'
type TabKeys = Pick<StartFields, 'nebiusKey' | 'tavilyKey' | 'nebiusProjectId'>

function tabStorage(): Storage | null {
  try {
    return typeof sessionStorage === 'undefined' ? null : sessionStorage
  } catch {
    return null
  }
}

export function loadTabKeys(): TabKeys {
  const empty = { nebiusKey: '', tavilyKey: '', nebiusProjectId: '' }
  try {
    const raw = tabStorage()?.getItem(TAB_KEY_STORE)
    if (!raw) return empty
    const v = JSON.parse(raw) as Partial<TabKeys>
    return {
      nebiusKey: typeof v.nebiusKey === 'string' ? v.nebiusKey : '',
      tavilyKey: typeof v.tavilyKey === 'string' ? v.tavilyKey : '',
      nebiusProjectId: typeof v.nebiusProjectId === 'string' ? v.nebiusProjectId : '',
    }
  } catch {
    return empty
  }
}

export function saveTabKeys(fields: TabKeys): void {
  const store = tabStorage()
  if (!store) return
  const keep = { nebiusKey: fields.nebiusKey, tavilyKey: fields.tavilyKey, nebiusProjectId: fields.nebiusProjectId }
  if (!keep.nebiusKey && !keep.tavilyKey && !keep.nebiusProjectId) store.removeItem(TAB_KEY_STORE)
  else store.setItem(TAB_KEY_STORE, JSON.stringify(keep))
}

export type StoredStatus = { nebius_key: boolean; tavily_key: boolean; contree_project?: boolean }

export function StartForm({
  stored,
  onStart,
  onSample,
  initialUrl = '',
}: {
  stored: StoredStatus
  onStart: (fields: StartFields) => Promise<StartResult>
  onSample?: () => void
  initialUrl?: string
}) {
  const [fields, setFields] = useState<StartFields>(() => ({
    prUrl: initialUrl,
    provider: 'nebius',
    approval: true,
    ...loadTabKeys(),
  }))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = <K extends keyof StartFields>(k: K, v: StartFields[K]) =>
    setFields((f) => {
      const next = { ...f, [k]: v }
      if (k === 'nebiusKey' || k === 'tavilyKey' || k === 'nebiusProjectId') saveTabKeys(next)
      return next
    })

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    const result = await onStart(fields)
    setBusy(false)
    if (!result.ok) {
      setError(result.error)
    }
  }

  const keyHint = (has: boolean | undefined) =>
    has ? 'Stored for this session. Leave blank to keep it.' : 'Paste for this session only'

  return (
    <form className="form" onSubmit={(event) => void submit(event)} aria-label="Start a check">
      <label htmlFor="pr-url">Pull request URL</label>
      <input
        id="pr-url"
        value={fields.prUrl}
        onChange={(event) => set('prUrl', event.target.value)}
        placeholder="https://github.com/owner/repo/pull/123"
        autoComplete="off"
      />
      <label htmlFor="nebius-key">Nebius API key (optional)</label>
      <input
        id="nebius-key"
        type="password"
        name="nebius-session-key"
        autoComplete="new-password"
        value={fields.nebiusKey}
        onChange={(event) => set('nebiusKey', event.target.value)}
        placeholder={keyHint(stored.nebius_key)}
      />
      <label htmlFor="nebius-project-id">Nebius project ID (optional, for the cloud sandbox)</label>
      <input
        id="nebius-project-id"
        type="password"
        name="nebius-project-id"
        autoComplete="new-password"
        value={fields.nebiusProjectId}
        onChange={(event) => set('nebiusProjectId', event.target.value)}
        placeholder={keyHint(stored.contree_project)}
      />
      <label htmlFor="tavily-key">Tavily API key (optional)</label>
      <input
        id="tavily-key"
        type="password"
        name="tavily-session-key"
        autoComplete="new-password"
        value={fields.tavilyKey}
        onChange={(event) => set('tavilyKey', event.target.value)}
        placeholder={keyHint(stored.tavily_key)}
      />
      <p className="hint">
        Keys are kept only in this browser tab and survive a page refresh; closing the tab clears them. They are
        sent with Run check, kept in the server's memory for the session, and never saved to disk, logs, or the
        report. Pull-request code never sees them. A check needs your own Nebius API key;
        only the saved sample runs without one. Without a Tavily key, the lookup is skipped. Tavily keys are free at
        https://app.tavily.com/. A Nebius project ID lets the check run in a Nebius cloud sandbox, billed to your
        own Nebius account.
      </p>
      <label htmlFor="provider">Model provider</label>
      <select id="provider" value={fields.provider} onChange={(event) => set('provider', event.target.value)}>
        <option value="nebius">nebius (live Nemotron)</option>
        <option value="none">none (no AI)</option>
        <option value="recorded">recorded (prerecorded fixture)</option>
      </select>
      <label className="check-row" htmlFor="approval">
        <input
          id="approval"
          type="checkbox"
          checked={fields.approval}
          onChange={(event) => set('approval', event.target.checked)}
        />
        Review the AI's probes before tests run (recommended)
      </label>
      <p className="hint">
        On by default. The AI drafts behaviour probes, you keep or drop each one and add your own test ideas, then the
        tests run. Untick it to skip the review for this check.
      </p>
      {error ? (
        <p className="banner err start-error" role="alert">
          {error}
        </p>
      ) : null}
      <button type="submit" disabled={busy}>
        {busy ? 'Starting…' : 'Run check'}
      </button>
      {onSample ? (
        <button type="button" className="ghost sample" disabled={busy} onClick={onSample}>
          Try sample (mlxtend#1229, prerecorded)
        </button>
      ) : null}
    </form>
  )
}
