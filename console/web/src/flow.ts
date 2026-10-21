import type { StageEvent } from './api'

export type NodeId =
  | 'intake'
  | 'checkout-base'
  | 'checkout-head'
  | 'install-base'
  | 'install-head'
  | 'existing-tests'
  | 'ai-write'
  | 'human-review'
  | 'before-after'
  | 'compare'
  | 'verifier'
  | 'verdict'
  | 'advice'

export type NodeState = 'pending' | 'running' | 'done' | 'failed' | 'skipped'

export type FlowNode = {
  id: NodeId
  label: string
  hint: string
  x: number
  y: number
  state: NodeState
  detail: string
  duration: string
}

export const FLOW_ORDER: NodeId[] = [
  'intake',
  'checkout-base',
  'checkout-head',
  'install-base',
  'install-head',
  'existing-tests',
  'ai-write',
  'human-review',
  'before-after',
  'compare',
  'verifier',
  'verdict',
  'advice',
]

const COPY: Record<NodeId, { label: string; hint: string; x: number; y: number }> = {
  intake: { label: 'PR intake', hint: 'Read the pull request.', x: 70, y: 150 },
  'checkout-base': { label: 'Checkout original', hint: 'The code before the change.', x: 250, y: 48 },
  'checkout-head': { label: 'Checkout the change', hint: 'The code the pull request adds.', x: 250, y: 252 },
  'install-base': { label: 'Install original', hint: 'Install the original side.', x: 460, y: 48 },
  'install-head': { label: 'Install the change', hint: 'Install the change in a sandbox.', x: 460, y: 252 },
  'existing-tests': { label: 'Run existing tests', hint: 'The project’s own tests, on both sides.', x: 700, y: 48 },
  'ai-write': { label: 'AI writes probes', hint: 'Behaviour probes written for this change.', x: 700, y: 252 },
  'human-review': {
    label: 'Human review',
    hint: 'You keep or drop each probe and add your own test ideas before anything runs.',
    x: 900,
    y: 252,
  },
  'before-after': { label: 'Run them on both sides', hint: 'The probes run before and after the change.', x: 1100, y: 252 },
  compare: { label: 'Compare and drop noise', hint: 'Keep differences that are not noise.', x: 1100, y: 48 },
  verifier: { label: 'Reviewer / verifier', hint: 'Plain code checks the comparison.', x: 1320, y: 150 },
  verdict: { label: 'Verdict and report', hint: 'The checker’s verdict and the report.', x: 1520, y: 150 },
  advice: { label: 'Reviewer notes', hint: "Doesn't change the verdict.", x: 1720, y: 150 },
}

export const FLOW_EDGES: [NodeId, NodeId][] = [
  ['intake', 'checkout-base'],
  ['intake', 'checkout-head'],
  ['checkout-base', 'install-base'],
  ['checkout-head', 'install-head'],
  ['install-base', 'existing-tests'],
  ['install-head', 'existing-tests'],
  ['install-base', 'ai-write'],
  ['checkout-head', 'ai-write'],
  ['ai-write', 'human-review'],
  ['human-review', 'before-after'],
  ['install-base', 'before-after'],
  ['install-head', 'before-after'],
  ['existing-tests', 'compare'],
  ['before-after', 'compare'],
  ['compare', 'verifier'],
  ['verifier', 'verdict'],
  ['verdict', 'advice'],
]

type Mark = { state: NodeState; detail: string }

function blank(): Record<NodeId, Mark> {
  return Object.fromEntries(FLOW_ORDER.map((id) => [id, { state: 'pending' as NodeState, detail: '' }])) as Record<NodeId, Mark>
}

function doneThrough(marks: Record<NodeId, Mark>, id: NodeId, detail = '') {
  const index = FLOW_ORDER.indexOf(id)
  for (let i = 0; i < index; i += 1) {
    const prev = FLOW_ORDER[i]
    if (marks[prev].state === 'pending' || marks[prev].state === 'running') marks[prev].state = 'done'
  }
  marks[id] = { state: 'running', detail }
}

function failRest(marks: Record<NodeId, Mark>, id: NodeId, detail: string) {
  marks[id] = { state: 'failed', detail }
  let after = false
  for (const node of FLOW_ORDER) {
    if (node === id) {
      after = true
      continue
    }
    if (after && marks[node].state === 'pending') marks[node].state = 'skipped'
  }
}

export function statesFromEvents(events: StageEvent[]): Record<NodeId, Mark> {
  const marks = blank()
  const sawReview = events.some((event) => event.stage === 'await_human')
  for (const event of events) {
    const stage = event.stage || ''
    const detail = event.detail || ''
    if (stage === 'queued' || stage === 'fetch_pr') doneThrough(marks, 'intake', detail)
    else if (stage === 'install_main') doneThrough(marks, 'install-base', detail)
    else if (stage === 'install_pr') doneThrough(marks, 'install-head', detail)
    else if (stage === 'claims') doneThrough(marks, 'ai-write', detail)
    else if (stage === 'await_human') doneThrough(marks, 'human-review', detail || 'Waiting for your review')
    else if (stage === 'probes') {
      if (!sawReview) marks['human-review'] = { state: 'skipped', detail: 'Review skipped for this check' }
      doneThrough(marks, 'before-after', detail)
    }
    else if (stage === 'pytest') {
      if (detail === 'before coverage') {
        marks['existing-tests'] = { state: 'done', detail }
        doneThrough(marks, 'compare', detail)
      } else {
        doneThrough(marks, 'existing-tests', detail)
      }
    } else if (stage === 'verdict' || stage === 'report') doneThrough(marks, 'verdict', detail)
    else if (stage === 'agent_judge' || stage === 'agent_helper' || stage === 'agent_summary') {
      doneThrough(marks, 'advice', detail)
    } else if (stage === 'done') {
      for (const id of FLOW_ORDER) {
        if (marks[id].state === 'pending' || marks[id].state === 'running') {
          marks[id] = { state: id === 'advice' && !events.some((item) => (item.stage || '').startsWith('agent_')) ? 'skipped' : 'done', detail: marks[id].detail }
        }
      }
    } else if (stage === 'failed') {
      const current = [...FLOW_ORDER].reverse().find((id) => marks[id].state === 'running') || 'intake'
      failRest(marks, current, detail || 'failed')
    }
  }
  return marks
}

function has(record: Record<string, unknown>, key: string) {
  const value = record[key]
  return value != null && value !== '' && !(Array.isArray(value) && value.length === 0)
}

export function statesFromRecord(record: Record<string, unknown>): Record<NodeId, Mark> {
  const marks = blank()
  const prSide = (record.pr_side && typeof record.pr_side === 'object' ? record.pr_side : {}) as Record<string, unknown>
  const buildFailed = typeof prSide.why === 'string' && /fail|error|timed out/i.test(prSide.why)
  const set = (id: NodeId, state: NodeState, detail = '') => {
    marks[id] = { state, detail }
  }
  if (has(record, 'repo') || has(record, 'pr')) set('intake', 'done')
  if (has(record, 'tested') || has(record, 'sides')) {
    set('checkout-base', 'done')
    set('checkout-head', 'done')
  }
  if (has(record, 'freeze') || has(record, 'main_side')) set('install-base', 'done')
  if (buildFailed) {
    set('install-head', 'failed', String(prSide.why))
    for (const id of ['existing-tests', 'ai-write', 'human-review', 'before-after', 'compare', 'verifier', 'verdict', 'advice'] as NodeId[]) {
      set(id, 'skipped')
    }
    return marks
  }
  if (has(record, 'pr_side') || has(record, 'freeze')) set('install-head', 'done')
  if (has(record, 'per_run') || has(record, 'comparison')) set('existing-tests', 'done')
  if (has(record, 'behaviour_claims') || has(record, 'probe_plan') || has(record, 'probes')) {
    set('ai-write', 'done')
    set('human-review', record.operator_approval === 'on' || has(record, 'hitl_approval') ? 'done' : 'skipped')
  }
  const probes = record.probes as { items?: Array<{ observations?: unknown[] }> } | undefined
  if (probes?.items?.some((item) => (item.observations || []).length > 0)) set('before-after', 'done')
  if (has(record, 'comparison')) set('compare', 'done')
  if (typeof record.verdict === 'string' && record.verdict) {
    set('verifier', 'done', 'Plain code checks the comparison')
    set('verdict', 'done', record.verdict)
  }
  const agents = (record.agents && typeof record.agents === 'object' ? record.agents : {}) as { status?: string; roles?: unknown }
  if (record.model_skipped || agents.status === 'skipped') set('advice', 'skipped', "Doesn't change the verdict")
  else if (agents.roles && typeof agents.roles === 'object' && Object.keys(agents.roles as object).length > 0) {
    set('advice', 'done', "Doesn't change the verdict")
  }
  return marks
}

function durationText(record: Record<string, unknown> | null | undefined): Partial<Record<NodeId, string>> {
  if (!record) return {}
  const duration = (record.duration_s && typeof record.duration_s === 'object' ? record.duration_s : {}) as Record<string, unknown>
  const cost = (record.cost && typeof record.cost === 'object' ? record.cost : {}) as { compute_seconds?: Record<string, unknown> }
  const seconds = cost.compute_seconds || {}
  const tests = duration.tests ?? seconds.tests
  const wall = duration.total_wall ?? seconds.total_wall
  const prSide = (record.pr_side && typeof record.pr_side === 'object' ? record.pr_side : {}) as Record<string, unknown>
  const build = duration.build ?? prSide.build_seconds
  const fmt = (value: unknown) => (typeof value === 'number' && value > 0 ? `${Math.round(value)}s` : '')
  return {
    'existing-tests': fmt(tests),
    'install-head': fmt(build),
    verdict: fmt(wall),
  }
}

export function flowNodes(
  events: StageEvent[] | null | undefined,
  record: Record<string, unknown> | null | undefined,
): FlowNode[] {
  const marks = record && (!events || events.length === 0) ? statesFromRecord(record) : statesFromEvents(events || [])
  if (record && events && events.length > 0) {
    const fromRecord = statesFromRecord(record)
    for (const id of FLOW_ORDER) {
      if (marks[id].state === 'pending' && fromRecord[id].state !== 'pending') marks[id] = fromRecord[id]
    }
  }
  const durations = durationText(record)
  return FLOW_ORDER.map((id) => ({
    id,
    ...COPY[id],
    state: marks[id].state,
    detail: marks[id].detail,
    duration: durations[id] || '',
  }))
}

export function edgeActive(from: NodeState, to: NodeState) {
  return from === 'done' || from === 'running' || to === 'running' || to === 'done'
}
