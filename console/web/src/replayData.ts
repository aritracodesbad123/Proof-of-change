/** Replay mode reads finished checks from static files. It does not call the live API. */

export type ReplayCheck = {
  id: string
  kind?: string
  repo?: string
  pr?: number | null
  url?: string | null
  title?: string
  verdict?: string
  reason?: string
  tested_at_ist?: string
  record: string
  report_html?: string | null
}

export type ReplayCatalog = {
  mode: string
  note?: string
  checks: ReplayCheck[]
}

export const replayMode = import.meta.env.VITE_REPLAY === '1'

export function assertReplayUrl(url: string): void {
  const trimmed = url.trim()
  if (/^[a-z][a-z0-9+.-]*:/i.test(trimmed) || trimmed.startsWith('//')) {
    throw new Error('replay does not use the network')
  }
  if (trimmed.includes('/api/') || /api\.github\.com|tokenfactory|nebius\.com/i.test(trimmed)) {
    throw new Error('replay does not call the live API')
  }
}

export function joinReplay(base: string, path: string): string {
  const prefix = base.endsWith('/') ? base : `${base}/`
  return `${prefix}${path.replace(/^\//, '')}`
}

export function replayFile(base: string, path: string): string {
  return joinReplay(joinReplay(base, 'replay/'), path)
}

export async function fetchReplay(
  fetchImpl: typeof fetch,
  base = import.meta.env.BASE_URL || './',
): Promise<{ catalog: ReplayCatalog; records: Record<string, Record<string, unknown>> }> {
  const catalogUrl = replayFile(base, 'catalog.json')
  assertReplayUrl(catalogUrl)
  const response = await fetchImpl(catalogUrl)
  if (!response.ok) throw new Error('The finished checks could not be loaded.')
  const catalog = (await response.json()) as ReplayCatalog
  const records: Record<string, Record<string, unknown>> = {}
  for (const row of catalog.checks || []) {
    const recordUrl = replayFile(base, row.record)
    assertReplayUrl(recordUrl)
    const body = await fetchImpl(recordUrl)
    if (!body.ok) throw new Error(`The record for ${row.id} is missing.`)
    records[row.id] = (await body.json()) as Record<string, unknown>
  }
  return { catalog, records }
}
