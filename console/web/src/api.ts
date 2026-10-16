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

export type Job = {
  id: string
  status: string
  pr_url: string
  repo?: string
  pr?: number
  exit?: number | null
  error?: string | null
  run_id?: string | null
  log_tail?: string
  stages?: StageEvent[]
  current_stage?: string | null
  current_agent?: string | null
  current_detail?: string | null
  swarm?: SwarmStatus
}

export const api = {
  health: () => json<{ ok: boolean }>('/api/health'),
  runs: () => json<{ runs: RunRow[] }>('/api/runs'),
  run: (id: string) =>
    json<{ record: Record<string, unknown>; folder: string; hosted_report: string | null }>(
      `/api/runs/${encodeURIComponent(id)}`,
    ),
  startCheck: (pr_url: string, model_provider = 'nebius') =>
    json<Job>('/api/checks', {
      method: 'POST',
      body: JSON.stringify({ pr_url, model_provider }),
    }),
  job: (id: string) => json<Job>(`/api/jobs/${encodeURIComponent(id)}`),
}
