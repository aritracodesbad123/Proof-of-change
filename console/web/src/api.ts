const BASE = import.meta.env.VITE_API_BASE ?? ''

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error((data as { error?: string }).error || res.statusText)
  return data as T
}

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

export type HitlApprovalBody = {
  approve: string[]
  extra_scenarios: string[]
  business_answers: Record<string, string>
  skip_business_followup: boolean
}

export type Health = {
  ok: boolean
  service?: string
  contree_ready?: boolean
  run_flags?: string[]
  run_note?: string | null
  github_token?: boolean
  chrome?: boolean
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
  report_html?: string | null
  stages?: StageEvent[]
  current_stage?: string | null
  current_agent?: string | null
  current_detail?: string | null
  swarm?: SwarmStatus
  hitl_draft?: HitlDraft | null
  hitl_approval?: HitlApprovalBody | null
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
      report_html?: string | null
    }>(`/api/runs/${encodeURIComponent(id)}`),
  startCheck: (pr_url: string, model_provider = 'nebius') =>
    json<Job>('/api/checks', {
      method: 'POST',
      body: JSON.stringify({ pr_url, model_provider }),
    }),
  job: (id: string) => json<Job>(`/api/jobs/${encodeURIComponent(id)}`),
  submitScenarios: (id: string, body: HitlApprovalBody) =>
    json<{ ok: boolean; approval: HitlApprovalBody }>(
      `/api/jobs/${encodeURIComponent(id)}/scenarios`,
      { method: 'POST', body: JSON.stringify(body) },
    ),
}
