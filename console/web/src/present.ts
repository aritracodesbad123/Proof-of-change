/** Presentation helpers. They format records the API already returned.
 * They never choose a verdict, a probe result, or a price. */

export type StepState = 'pending' | 'started' | 'current' | 'done' | 'failed' | 'skipped'

export type TimelineStep = {
  id: string
  label: string
  hint: string
  state: StepState
}

export const TIMELINE_SPEC = [
  { id: 'fetch', label: 'Fetch', hint: 'Load the pull request', stages: ['queued', 'fetch_pr'] },
  { id: 'sandbox', label: 'Sandbox', hint: 'Install the base and the pull request', stages: ['install_main', 'install_pr'] },
  { id: 'tests', label: 'Base vs PR tests', hint: 'Run the project tests on both sides', stages: ['pytest'] },
  { id: 'probes', label: 'AI probes', hint: 'Claims and behaviour probes', stages: ['claims', 'await_human', 'probes'] },
  { id: 'coverage', label: 'Coverage', hint: 'Check that changed lines actually ran', stages: [] as string[] },
  {
    id: 'verdict',
    label: 'Verdict',
    hint: 'The code publishes the verdict',
    stages: ['verdict'],
  },
  {
    id: 'advice',
    label: 'Advice (swarm)',
    hint: "Doesn't change the verdict",
    stages: ['agent_judge', 'agent_helper', 'agent_summary'],
  },
] as const

export const DETAIL_STAGES: { id: string; label: string }[] = [
  { id: 'queued', label: 'Queued' },
  { id: 'fetch_pr', label: 'Fetch PR' },
  { id: 'install_main', label: 'Install main' },
  { id: 'install_pr', label: 'Install PR' },
  { id: 'claims', label: 'Claims' },
  { id: 'await_human', label: 'Human review' },
  { id: 'probes', label: 'Probes' },
  { id: 'pytest', label: 'Pytest' },
  { id: 'verdict', label: 'Code verdict' },
  { id: 'agent_judge', label: 'Ultra judging' },
  { id: 'agent_helper', label: 'Lightning helping' },
  { id: 'agent_summary', label: 'Super summarizing' },
  { id: 'report', label: 'Report' },
  { id: 'done', label: 'Done' },
]

const VERDICT_TONES = ['verified', 'needs_attention', 'could_not_verify', 'no_code_change'] as const
export type VerdictTone = (typeof VERDICT_TONES)[number] | 'unknown'

const PAST_FETCH = new Set([
  'install_main', 'install_pr', 'claims', 'await_human', 'probes', 'pytest',
  'verdict', 'agent_judge', 'agent_helper', 'agent_summary', 'report', 'done',
])
const PAST_SANDBOX = new Set([
  'pytest', 'probes', 'verdict', 'agent_judge', 'agent_helper', 'agent_summary', 'report', 'done',
])
const PAST_PROBES = new Set([
  'verdict', 'agent_judge', 'agent_helper', 'agent_summary', 'report', 'done',
])
const VERDICT_REACHED = new Set([
  'verdict', 'agent_judge', 'agent_helper', 'agent_summary', 'report', 'done',
])
const PAST_VERDICT = new Set(['agent_judge', 'agent_helper', 'agent_summary', 'report', 'done'])
const SWARM_STAGES = ['agent_judge', 'agent_helper', 'agent_summary'] as const

function has(seen: Set<string>, names: Set<string>): boolean {
  for (const n of names) if (seen.has(n)) return true
  return false
}

export function timelineStates(
  events: { stage?: string | null }[],
  current?: string | null,
): TimelineStep[] {
  const seen = new Set(events.map((e) => e.stage).filter((s): s is string => Boolean(s)))
  const active = current || [...seen].at(-1) || null
  if (active) seen.add(active)
  const failed = seen.has('failed') || active === 'failed'

  const raw: TimelineStep[] = TIMELINE_SPEC.map((spec) => ({
    id: spec.id,
    label: spec.label,
    hint: spec.hint,
    state: stateFor(spec.id, seen, active),
  }))

  if (!failed) return raw

  let failAt = -1
  raw.forEach((step, i) => {
    if (step.state !== 'pending') failAt = i
  })
  if (failAt < 0) failAt = 0
  return raw.map((step, i) => {
    if (i < failAt) return { ...step, state: step.state === 'pending' ? 'skipped' : 'done' }
    if (i === failAt) return { ...step, state: 'failed' }
    return { ...step, state: 'skipped' }
  })
}

function stateFor(id: string, seen: Set<string>, active: string | null): StepState {
  const on = (stages: readonly string[]) => Boolean(active && stages.includes(active))
  if (id === 'fetch') {
    if (on(['queued', 'fetch_pr'])) return 'current'
    if (has(seen, PAST_FETCH) || (seen.has('fetch_pr') && active !== 'queued' && active !== 'fetch_pr')) return 'done'
    if (seen.has('queued') || seen.has('fetch_pr')) return 'started'
    return 'pending'
  }
  if (id === 'sandbox') {
    if (on(['install_main', 'install_pr'])) return 'current'
    if (has(seen, PAST_SANDBOX) || (seen.has('install_pr') && active !== 'install_main' && active !== 'install_pr')) {
      return 'done'
    }
    if (seen.has('install_main') || seen.has('install_pr')) return 'started'
    return 'pending'
  }
  if (id === 'tests') {
    if (active === 'pytest') return 'current'
    if (seen.has('pytest') && active !== 'pytest') return 'done'
    return 'pending'
  }
  if (id === 'probes') {
    if (on(['claims', 'await_human', 'probes'])) return 'current'
    if (seen.has('probes') && has(seen, PAST_PROBES)) return 'done'
    if (seen.has('claims') || seen.has('await_human') || seen.has('probes')) return 'started'
    return 'pending'
  }
  if (id === 'coverage') {
    if (has(seen, VERDICT_REACHED)) return 'done'
    return 'pending'
  }
  if (id === 'verdict') {
    if (active === 'verdict') return 'current'
    if ((seen.has('verdict') && active !== 'verdict') || has(seen, PAST_VERDICT)) return 'done'
    return 'pending'
  }
  if (on(SWARM_STAGES)) return 'current'
  const swarmSeen = SWARM_STAGES.some((stage) => seen.has(stage))
  if (active === 'report' || active === 'done' || seen.has('report') || seen.has('done')) {
    return swarmSeen ? 'done' : 'skipped'
  }
  if (swarmSeen) return 'started'
  return 'pending'
}

/** Frames for the landing illustration. Not a live check. */
export function illustrativeStates(frame: number): TimelineStep[] {
  const n = TIMELINE_SPEC.length
  const resting = frame < 0 || frame >= n
  return TIMELINE_SPEC.map((spec, i) => ({
    id: spec.id,
    label: spec.label,
    hint: spec.hint,
    state: resting ? 'pending' : i < frame ? 'done' : i === frame ? 'current' : 'pending',
  }))
}

export function verdictTone(verdict?: string | null): VerdictTone {
  if (verdict && (VERDICT_TONES as readonly string[]).includes(verdict)) return verdict as VerdictTone
  return 'unknown'
}

export function verdictLabel(verdict?: string | null): string {
  const tone = verdictTone(verdict)
  if (tone === 'unknown') return verdict?.trim() || 'No verdict'
  return tone.replaceAll('_', ' ')
}

export function verdictPlain(verdict?: string | null): string {
  switch (verdictTone(verdict)) {
    case 'verified':
      return 'Verified — the behaviour matches the claims'
    case 'needs_attention':
      return 'Needs attention — review the findings'
    case 'could_not_verify':
      return 'Could not verify — the check finished without enough evidence'
    case 'no_code_change':
      return 'No code change — nothing in the library code to prove'
    default:
      return verdict?.trim() || 'No verdict yet'
  }
}

export function reasonPoints(reason?: string | null): string[] {
  const raw = (reason || '').trim()
  if (!raw) return []
  return raw
    .split(/\s*;\s*/)
    .map((part) => plainClause(part.trim()))
    .filter((part) => part.length > 0)
}

function plainClause(clause: string): string {
  if (!clause) return ''
  const lower = clause.toLowerCase()
  if (lower.startsWith('probe:')) {
    const rest = clause.slice(clause.indexOf(':') + 1).trim()
    if (/need attention/i.test(rest)) {
      const detail = rest.replace(/^.*?need attention:\s*/i, '')
      return `A probe found a difference that needs a look: ${detail}`
    }
    if (/proven/i.test(rest)) return `A probe proved ${rest.replace(/^claim\(s\)\s*/i, 'claims ')}`
    if (/identical/i.test(rest)) return `A probe saw the same result on both sides (${rest}).`
    return `Probe result: ${rest}`
  }
  if (lower.startsWith('tests:')) return `Project tests: ${clause.slice(clause.indexOf(':') + 1).trim()}`
  if (lower.startsWith('not fully verified:')) {
    return `Coverage did not fully verify this change: ${clause.slice(clause.indexOf(':') + 1).trim()}`
  }
  return clause.charAt(0).toUpperCase() + clause.slice(1)
}

export type CostTime = {
  ai: string | null
  computer: string | null
  total: string | null
  swarm: string | null
  tokens: string | null
  complete: boolean | null
  wall: string | null
  tests: string | null
}

function money(value: unknown): string | null {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null
  if (value === 0) return '$0.00'
  if (Math.abs(value) < 0.01) return `$${value.toFixed(4)}`
  return `$${value.toFixed(2)}`
}

export function formatDuration(seconds: unknown): string | null {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds < 0) return null
  const whole = Math.round(seconds)
  if (whole < 90) return `${whole}s`
  const minutes = Math.floor(whole / 60)
  const rest = whole % 60
  if (minutes < 90) return rest ? `${minutes}m ${rest}s` : `${minutes}m`
  const hours = Math.floor(minutes / 60)
  const min = minutes % 60
  return min ? `${hours}h ${min}m` : `${hours}h`
}

/** Read cost and time fields already stored on the record. Do not add them up. */
export function costTime(record: Record<string, unknown>): CostTime {
  const cost = record.cost && typeof record.cost === 'object' ? (record.cost as Record<string, unknown>) : {}
  const swarm = cost.swarm && typeof cost.swarm === 'object' ? (cost.swarm as Record<string, unknown>) : null
  const dur = record.duration_s
  let wall: unknown = null
  let tests: unknown = null
  if (typeof dur === 'number') wall = dur
  else if (dur && typeof dur === 'object') {
    const d = dur as Record<string, unknown>
    wall = d.total_wall
    tests = d.tests
  }
  const input = cost.input_tokens
  const output = cost.output_tokens
  const tokens =
    typeof input === 'number' || typeof output === 'number'
      ? `${typeof input === 'number' ? input : 0} in / ${typeof output === 'number' ? output : 0} out`
      : null
  return {
    ai: money(cost.ai_cost_usd ?? cost.cost_usd),
    computer: money(cost.computer_cost_usd),
    total: money(cost.total_cost_usd),
    swarm: swarm ? money(swarm.ai_cost_usd ?? swarm.cost_usd) : null,
    tokens,
    complete: typeof cost.cost_complete === 'boolean' ? cost.cost_complete : null,
    wall: formatDuration(wall),
    tests: formatDuration(tests),
  }
}

export function coveragePlain(record: Record<string, unknown>): string | null {
  const cov = record.coverage
  if (!cov || typeof cov !== 'object') return null
  const c = cov as Record<string, unknown>
  if (c.status === 'measured' && typeof c.changed_lines_total === 'number') {
    const total = c.changed_lines_total
    const hit = typeof c.changed_lines_covered === 'number' ? c.changed_lines_covered : 0
    if (!total) return 'No changed executable lines to measure.'
    return `${hit} of ${total} changed executable lines ran (${Math.round((100 * hit) / total)}%).`
  }
  if (c.status === 'not needed') return 'Coverage was not needed for this change.'
  if (typeof c.why === 'string' && c.why.trim()) return `Coverage was not measured: ${c.why.trim()}`
  if (typeof c.status === 'string' && c.status.trim()) return `Coverage status: ${c.status}`
  return null
}

export type LogSection = { id: string; title: string; body: string }

export function logSections(text?: string | null): LogSection[] {
  const raw = (text || '').replace(/\r\n/g, '\n').trim()
  if (!raw) return []
  const chunks: { title: string; lines: string[] }[] = []
  let current = { title: 'Output', lines: [] as string[] }
  for (const line of raw.split('\n')) {
    const banner = line.match(/^---\s+(.+?)\s+---\s*$/) || line.match(/^={3,}\s*(.+?)\s*=*\s*$/)
    if (banner) {
      chunks.push(current)
      current = { title: banner[1].trim() || 'Section', lines: [] }
    } else {
      current.lines.push(line)
    }
  }
  chunks.push(current)
  let sections = chunks
    .map((chunk, i) => ({
      id: `${i}-${chunk.title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
      title: chunk.title,
      body: chunk.lines.join('\n').trim(),
    }))
    .filter((section) => section.body.length > 0)

  if (sections.length === 1 && sections[0].body.split('\n').length > 28) {
    const lines = sections[0].body.split('\n')
    const size = 24
    sections = []
    for (let i = 0; i < lines.length; i += size) {
      const slice = lines.slice(i, i + size)
      const start = i + 1
      const end = i + slice.length
      sections.push({
        id: `lines-${start}-${end}`,
        title: `Lines ${start}–${end}`,
        body: slice.join('\n'),
      })
    }
  }
  return sections
}

export type RunLike = {
  id?: string
  repo?: string
  pr?: number
  title?: string
  verdict?: string
  reason?: string
}

export function filterRuns<T extends RunLike>(runs: T[], query: string, verdict: string): T[] {
  const q = query.trim().toLowerCase()
  return runs.filter((run) => {
    if (verdict && verdict !== 'all' && (run.verdict || '') !== verdict) return false
    if (!q) return true
    const hay = [run.repo, run.title, run.id, run.pr, run.verdict, run.reason]
      .filter((part) => part !== undefined && part !== null)
      .join(' ')
      .toLowerCase()
    return hay.includes(q)
  })
}

export type ClaimRow = {
  id: string
  text: string
  expect?: string
  source_quote?: string
  source?: string
}

export type ObsRow = {
  name?: string
  state?: string
  label?: string
  claim?: string | null
}

export function probeItems(record: Record<string, unknown>): Array<Record<string, unknown>> {
  const probes = record.probes
  if (!probes || typeof probes !== 'object') return []
  const items = (probes as { items?: unknown }).items
  return Array.isArray(items) ? (items as Array<Record<string, unknown>>) : []
}

export function claimsFromRecord(record: Record<string, unknown>): ClaimRow[] {
  const plan = record.probe_plan as { model_claims?: ClaimRow[] } | undefined
  if (Array.isArray(plan?.model_claims) && plan.model_claims.length) {
    return plan.model_claims.map(asClaim)
  }
  const top = record.behaviour_claims as ClaimRow[] | undefined
  if (Array.isArray(top) && top.length) return top.map(asClaim)
  const seen = new Map<string, ClaimRow>()
  for (const probe of probeItems(record)) {
    const nested = probe.claims
    if (!Array.isArray(nested)) continue
    for (const claim of nested as ClaimRow[]) {
      const row = asClaim(claim)
      if (!row.id || seen.has(row.id)) continue
      seen.set(row.id, row)
    }
  }
  return [...seen.values()]
}

function asClaim(claim: ClaimRow | Record<string, unknown>): ClaimRow {
  const c = claim as Record<string, unknown>
  return {
    id: String(c.id || ''),
    text: String(c.text || c.claim || ''),
    expect: c.expect ? String(c.expect) : undefined,
    source_quote: c.source_quote ? String(c.source_quote) : undefined,
    source: c.source ? String(c.source) : undefined,
  }
}

export function observationsForClaim(record: Record<string, unknown>, claimId: string): ObsRow[] {
  const out: ObsRow[] = []
  for (const probe of probeItems(record)) {
    const observations = probe.observations
    if (!Array.isArray(observations)) continue
    for (const obs of observations as ObsRow[]) {
      if (String(obs.claim || '') === claimId) out.push(obs)
    }
  }
  return out
}

export function claimResultLabel(obs: ObsRow[]): string {
  if (!obs.length) return 'not probed'
  if (obs.some((o) => ['needs_attention', 'needs_human', 'false', 'false_claim', 'unmentioned'].includes(String(o.label || '')))) {
    return 'needs attention'
  }
  if (obs.some((o) => o.label === 'proven')) return 'proven'
  return String(obs[0]?.label || obs[0]?.state || 'checked')
}

export type MapProbe = {
  id: string
  about: string
  status: string
  claimIds: string[]
  observations: ObsRow[]
}

export type BehaviourMap = {
  claims: Array<ClaimRow & { result: string; probeIds: string[] }>
  probes: MapProbe[]
}

export function behaviourMap(record: Record<string, unknown>): BehaviourMap {
  const claims = claimsFromRecord(record)
  const probes: MapProbe[] = probeItems(record).map((probe, index) => {
    const nested = Array.isArray(probe.claims) ? (probe.claims as ClaimRow[]) : []
    const observations = Array.isArray(probe.observations) ? (probe.observations as ObsRow[]) : []
    const claimIds = [
      ...nested.map((c) => String(c.id || '')).filter(Boolean),
      ...observations.map((o) => String(o.claim || '')).filter(Boolean),
    ]
    return {
      id: String(probe.id || `probe-${index + 1}`),
      about: String(probe.about || ''),
      status: String(probe.status || ''),
      claimIds: [...new Set(claimIds)],
      observations,
    }
  })
  return {
    claims: claims.map((claim) => ({
      ...claim,
      result: claimResultLabel(observationsForClaim(record, claim.id)),
      probeIds: probes.filter((probe) => probe.claimIds.includes(claim.id)).map((probe) => probe.id),
    })),
    probes,
  }
}

export function evidenceLinks(
  record: Record<string, unknown>,
  extras: { pdf?: string | null; html?: string | null },
): { href: string; label: string; external: boolean }[] {
  const links: { href: string; label: string; external: boolean }[] = []
  const pr = record.pr
  if (pr && typeof pr === 'object' && typeof (pr as { url?: unknown }).url === 'string') {
    links.push({ href: (pr as { url: string }).url, label: 'Pull request', external: true })
  }
  if (extras.pdf) links.push({ href: extras.pdf, label: 'PDF report', external: true })
  if (extras.html) links.push({ href: extras.html, label: 'HTML report', external: true })
  links.push({ href: '#behaviour-map', label: 'Behaviour map', external: false })
  links.push({ href: '#claims', label: 'Claims', external: false })
  links.push({ href: '#probes', label: 'Probes', external: false })
  if (coveragePlain(record)) links.push({ href: '#coverage', label: 'Coverage', external: false })
  return links
}

export function detailStageState(
  id: string,
  events: { stage?: string | null }[],
  current?: string | null,
): StepState {
  const seen = new Set(events.map((e) => e.stage).filter((s): s is string => Boolean(s)))
  const failed = seen.has('failed') || current === 'failed'
  const order = DETAIL_STAGES.map((s) => s.id)
  const currentIdx = current ? order.indexOf(current) : -1
  const idx = order.indexOf(id)
  if (failed && id === 'done') return 'skipped'
  if (current === id) return failed ? 'failed' : 'current'
  if (seen.has(id) && id !== current) return 'done'
  if (currentIdx >= 0 && idx >= 0 && idx < currentIdx && !seen.has(id)) return 'done'
  return 'pending'
}

export function prNumber(record: Record<string, unknown>): number | null {
  const pr = record.pr
  if (typeof pr === 'number') return pr
  if (pr && typeof pr === 'object' && typeof (pr as { number?: unknown }).number === 'number') {
    return (pr as { number: number }).number
  }
  return null
}

export function unwrapSummary(raw: string): string {
  const t = raw.trim()
  if (!t.startsWith('{')) return t
  try {
    const inner = JSON.parse(t) as { summary?: unknown; text?: unknown }
    const s = inner.summary ?? inner.text
    if (typeof s === 'string' && s.trim()) return s.trim()
  } catch {
    /* keep the original text */
  }
  return t
}

export function agentRoles(record: Record<string, unknown>): Array<Record<string, unknown>> {
  const agents = record.agents
  if (!agents || typeof agents !== 'object') return []
  const roles = (agents as { roles?: unknown }).roles
  return Array.isArray(roles) ? (roles as Array<Record<string, unknown>>) : []
}

export function summaryText(record: Record<string, unknown>): string {
  const expl = (record.explanation as { text?: string } | undefined) || {}
  if (typeof expl.text === 'string' && expl.text.trim()) return unwrapSummary(expl.text)
  const helper = agentRoles(record).find((role) => role.role === 'helper')
  const notes = Array.isArray(helper?.notes) ? (helper.notes as string[]) : []
  const claims = claimsFromRecord(record)
  const lines = [`Code verdict: ${String(record.verdict || 'unknown')}.`, String(record.reason || '').trim()]
  if (claims.length) {
    lines.push('Claims under test:')
    for (const claim of claims) {
      lines.push(`• ${claim.id} (${claimResultLabel(observationsForClaim(record, claim.id))}): ${claim.text}`)
    }
  }
  if (notes.length) {
    lines.push('Lightning notes:')
    for (const note of notes.slice(0, 5)) lines.push(`• ${note}`)
  }
  return lines.filter(Boolean).join('\n')
}

export function testGlance(record: Record<string, unknown>): string[] {
  const comparison = (record.comparison as Record<string, unknown> | undefined) || {}
  const rows: string[] = []
  const count = (key: string) => (Array.isArray(comparison[key]) ? (comparison[key] as unknown[]).length : 0)
  if (count('new_tests_passing')) rows.push(`${count('new_tests_passing')} new test(s) passed on the PR`)
  if (count('new_tests_failing')) rows.push(`${count('new_tests_failing')} new test(s) failed on the PR`)
  if (count('regressions')) rows.push(`${count('regressions')} regression(s) vs main`)
  if (count('fixed')) rows.push(`${count('fixed')} previously failing test(s) now pass`)
  if (count('reparametrized')) rows.push(`${count('reparametrized')} re-parametrized test(s)`)
  if (count('same_skipped_both')) rows.push(`${count('same_skipped_both')} skipped on both sides`)
  return rows
}
