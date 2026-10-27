import type { StartBody } from './startForm'

const BASE = import.meta.env.VITE_API_BASE ?? ''

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export const LOST_JOB = 'This check was lost because the server restarted. Please start it again.'

export function lostJobMessage(error: unknown): string | null {
  return error instanceof ApiError && error.status === 404 ? LOST_JOB : null
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new ApiError((data as { error?: string }).error || res.statusText, res.status)
  return data as T
}

export type Account = { email: string; id: string; role: 'admin' | 'user' | string }

export type AuthProviders = {
  google: boolean
  github: boolean
  signup_disabled: boolean
  invite_required: boolean
}

export type Challenge = { challenge_id: string; purpose: 'signup' | 'login' }

export type RunRow = {
  id: string
  repo?: string
  pr?: number
  url?: string
  title?: string
  verdict?: string
  reason?: string
  tested_at_ist?: string
  machine?: string
  folder?: string
  source?: string
  report_pdf?: string | null
  report_pdf_status?: string | null
  report_html?: string | null
}

export type StageEvent = {
  at: number
  stage: string
  agent?: string | null
  detail?: string | null
}

export type SwarmStatus = {
  ultra: string
  lightning: string
  super: string
}

export type HitlQuestion = {
  id: string
  prompt: string
}

export type HitlProbePreview = {
  id?: string
  about?: string
  claims?: unknown[]
  code_preview?: string
}

export type HitlDraft = {
  claims?: Array<Record<string, unknown>>
  probes?: HitlProbePreview[]
  probe_ids?: string[]
  needs_business_followup?: boolean
  business_questions?: HitlQuestion[]
  rejected_claims?: unknown[]
}

export type HitlApprovalBody =
  | {
      approve: string[]
      extra_scenarios: string[]
      business_answers: Record<string, string>
      skip_business_followup: boolean
    }
  | { cancel: true }

export type Health = {
  ok: boolean
  service?: string
  contree_ready?: boolean
  run_flags?: string[]
  run_note?: string | null
  warning?: string | null
  refused?: boolean
  approval_default?: boolean
  github_token?: boolean
  chrome?: boolean
  /** True only on a local or Codespace console, which still asks for a Tavily key. */
  tavily_key_field?: boolean
}

export type Job = {
  id: string
  status: string
  pr_url: string
  repo?: string
  pr?: number
  model_provider?: string
  run_flags?: string[]
  run_note?: string | null
  exit?: number | null
  error?: string | null
  warning?: string | null
  run_id?: string | null
  log_tail?: string
  folder?: string
  record?: Record<string, unknown>
  report_pdf?: string | null
  report_pdf_status?: string | null
  report_html?: string | null
  stages?: StageEvent[]
  current_stage?: string | null
  current_agent?: string | null
  current_detail?: string | null
  swarm?: SwarmStatus
  hitl_draft?: HitlDraft | null
  hitl_approval?: HitlApprovalBody | null
  helper_notes?: string[]
}

export const api = {
  health: () => json<Health>('/api/health'),
  runs: () => json<{ runs: RunRow[] }>('/api/runs'),
  run: (id: string) =>
    json<{
      record: Record<string, unknown>
      folder: string
      hosted_report: string | null
      report_pdf?: string | null
  report_pdf_status?: string | null
      report_html?: string | null
    }>(`/api/runs/${encodeURIComponent(id)}`),
  startCheck: (pr_url: string, model_provider = 'nebius', approval = true) =>
    json<Job>('/api/checks', {
      method: 'POST',
      body: JSON.stringify({ pr_url, model_provider, approval }),
    }),
  /** One request with the link, review choice and any keys typed into the start form. */
  startWithFields: (body: StartBody) =>
    json<Job>('/api/checks', { method: 'POST', body: JSON.stringify(body) }),
  sessionKey: () => json<{ nebius_key: boolean; tavily_key: boolean; contree_project?: boolean }>('/api/session/key'),
  setSessionKey: (nebius_api_key: string) =>
    json<{ ok: boolean; nebius_key: boolean; tavily_key: boolean }>('/api/session/key', {
      method: 'POST',
      body: JSON.stringify({ nebius_api_key }),
    }),
  setTavilyKey: (tavily_api_key: string) =>
    json<{ ok: boolean; nebius_key: boolean; tavily_key: boolean }>('/api/session/key', {
      method: 'POST',
      body: JSON.stringify({ tavily_api_key }),
    }),
  job: (id: string) => json<Job>(`/api/jobs/${encodeURIComponent(id)}`),
  me: () => json<Account>('/api/auth/me'),
  providers: () => json<AuthProviders>('/api/auth/providers'),
  signup: (email: string, password: string, invite_code = '') =>
    json<Challenge>('/api/auth/signup', { method: 'POST', body: JSON.stringify({ email, password, invite_code }) }),
  login: (email: string, password: string) =>
    json<Challenge>('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  verify: (challenge_id: string, code: string) =>
    json<{ email: string }>('/api/auth/verify', { method: 'POST', body: JSON.stringify({ challenge_id, code }) }),
  resend: (challenge_id: string) =>
    json<Challenge>('/api/auth/resend', { method: 'POST', body: JSON.stringify({ challenge_id }) }),
  consoleCode: (code: string) =>
    json<Account>('/api/auth/console-code', { method: 'POST', body: JSON.stringify({ code }) }),
  logout: () => json<{ ok: boolean }>('/api/auth/logout', { method: 'POST', body: '{}' }),
  submitScenarios: (id: string, body: HitlApprovalBody) =>
    json<{ ok: boolean; approval: HitlApprovalBody }>(
      `/api/jobs/${encodeURIComponent(id)}/scenarios`,
      { method: 'POST', body: JSON.stringify(body) },
    ),
}
