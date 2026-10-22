import type { StageEvent } from './api'

export type NodeId =
  | 'intake'
  | 'setup-lookup'
  | 'setup-python'
  | 'install-deps'
  | 'install-base'
  | 'install-head'
  | 'benchmark'
  | 'probes'
  | 'human-review'
  | 'tests'
  | 'retries'
  | 'swarm'
  | 'verdict'

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
  'setup-lookup',
  'setup-python',
  'install-deps',
  'install-base',
  'install-head',
  'benchmark',
  'probes',
  'human-review',
  'tests',
  'retries',
  'swarm',
  'verdict',
]

const COPY: Record<NodeId, { label: string; hint: string; x: number; y: number }> = {
  intake: { label: 'Read the PR', hint: 'Read the pull request and what it changes.', x: 30, y: 40 },
  'setup-lookup': {
    label: 'Setup lookup',
    hint: 'Look up how the project is set up (Python version, config, libraries) and write this run’s requirements.txt.',
    x: 230,
    y: 40,
  },
  'setup-python': { label: 'Set up Python', hint: 'Pick and prepare the Python version the project asks for.', x: 430, y: 40 },
  'install-deps': {
    label: 'Install dependencies',
    hint: 'Install this run’s requirements.txt, the same list on both sides.',
    x: 630,
    y: 40,
  },
  'install-base': { label: 'Install main', hint: 'Install the code before the change, in a sandbox.', x: 830, y: 0 },
  'install-head': { label: 'Install PR', hint: 'Install the code with the change, in a sandbox.', x: 830, y: 90 },
  benchmark: { label: 'Benchmark suite', hint: 'The project’s own tests, run on both sides.', x: 1030, y: 40 },
  probes: { label: 'Probes', hint: 'AI-written behaviour probes for this change.', x: 30, y: 220 },
  'human-review': {
    label: 'Review',
    hint: 'You keep or drop each probe and add your own test ideas before anything runs.',
    x: 230,
    y: 220,
  },
  tests: { label: 'Tests', hint: 'The probes and coverage run before and after the change.', x: 430, y: 220 },
  retries: {
    label: 'Retries',
    hint: 'A setup or import problem is looked up, fixed on both sides and rerun, up to 3 tries. A test the PR breaks is never retried.',
    x: 630,
    y: 220,
  },
  swarm: { label: 'Swarm report', hint: "The advisory agents write the report. They don't change the verdict.", x: 830, y: 220 },
  verdict: { label: 'Verdict', hint: 'The checker’s verdict and the report.', x: 1030, y: 220 },
}

export const FLOW_EDGES: [NodeId, NodeId][] = [
  ['intake', 'setup-lookup'],
  ['setup-lookup', 'setup-python'],
  ['setup-python', 'install-deps'],
  ['install-deps', 'install-base'],
  ['install-deps', 'install-head'],
  ['install-base', 'benchmark'],
  ['install-head', 'benchmark'],
  ['benchmark', 'probes'],
  ['probes', 'human-review'],
  ['human-review', 'tests'],
  ['tests', 'retries'],
  ['retries', 'swarm'],
  ['swarm', 'verdict'],
]

type Mark = { state: NodeState; detail: string }

function blank(): Record<NodeId, Mark> {
  return Object.fromEntries(FLOW_ORDER.map((id) => [id, { state: 'pending' as NodeState, detail: '' }])) as Record<NodeId, Mark>
}

// Steps do not always fire in chart order (probes are written before the PR side installs), so a new step
// closes whatever was running instead of everything to its left.
function start(marks: Record<NodeId, Mark>, id: NodeId, detail = '') {
  for (const node of FLOW_ORDER) {
    if (node !== id && marks[node].state === 'running') marks[node].state = 'done'
  }
  const keep = marks[id].detail
  const text = id === 'retries' && keep && detail ? `${keep}\n${detail}` : detail || keep
  marks[id] = { state: 'running', detail: text }
}

function failRest(marks: Record<NodeId, Mark>, id: NodeId, detail: string) {
  marks[id] = { state: 'failed', detail }
  for (const node of FLOW_ORDER) {
    if (marks[node].state === 'pending') marks[node].state = 'skipped'
  }
}

const OPTIONAL: NodeId[] = ['human-review', 'retries', 'swarm']
const SKIP_TEXT: Partial<Record<NodeId, string>> = {
  'human-review': 'Review skipped for this check',
  retries: 'No setup problems, nothing retried',
  swarm: "No advisory report for this check. It doesn't change the verdict.",
}

export function statesFromEvents(events: StageEvent[]): Record<NodeId, Mark> {
  const marks = blank()
  let last: NodeId = 'intake'
  for (const event of events) {
    const stage = event.stage || ''
    const detail = event.detail || ''
    let id: NodeId | null = null
    if (stage === 'queued' || stage === 'fetch_pr') id = 'intake'
    else if (stage === 'setup_lookup') id = 'setup-lookup'
    else if (stage === 'setup_python') id = 'setup-python'
    else if (stage === 'install_deps') id = 'install-deps'
    else if (stage === 'install_main') id = 'install-base'
    else if (stage === 'install_pr') id = 'install-head'
    else if (stage === 'claims') id = 'probes'
    else if (stage === 'await_human') id = 'human-review'
    else if (stage === 'probes') id = /^running/i.test(detail) ? 'tests' : 'probes'
    else if (stage === 'pytest') id = /coverage/i.test(detail) ? 'tests' : 'benchmark'
    else if (stage === 'retry') id = 'retries'
    else if (stage.startsWith('agent_')) id = 'swarm'
    else if (stage === 'verdict' || stage === 'report') id = 'verdict'
    if (id) {
      if (id === 'tests' && marks['human-review'].state === 'pending') {
        marks['human-review'] = { state: 'skipped', detail: SKIP_TEXT['human-review'] || '' }
      }
      start(marks, id, detail || (id === 'human-review' ? 'Waiting for your review' : ''))
      last = id
    } else if (stage === 'done') {
      for (const node of FLOW_ORDER) {
        if (marks[node].state === 'running') marks[node].state = 'done'
        else if (marks[node].state === 'pending') {
          marks[node] = OPTIONAL.includes(node)
            ? { state: 'skipped', detail: SKIP_TEXT[node] || '' }
            : { state: 'done', detail: marks[node].detail }
        }
      }
    } else if (stage === 'failed') {
      const current = [...FLOW_ORDER].reverse().find((node) => marks[node].state === 'running') || last
      failRest(marks, current, detail || 'failed')
    }
  }
  return marks
}

function has(record: Record<string, unknown>, key: string) {
  const value = record[key]
  return value != null && value !== '' && !(Array.isArray(value) && value.length === 0)
}

function obj(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {}
}

export function statesFromRecord(record: Record<string, unknown>): Record<NodeId, Mark> {
  const marks = blank()
  const prSide = obj(record.pr_side)
  const helper = obj(record.demo_helper)
  const steps = obj(helper.steps)
  const buildFailed = typeof prSide.why === 'string' && /fail|error|timed out/i.test(prSide.why)
  const set = (id: NodeId, state: NodeState, detail = '') => {
    marks[id] = { state, detail }
  }
  if (has(record, 'repo') || has(record, 'pr')) set('intake', 'done')
  if (has(helper, 'setup_plan') || has(helper, 'tavily')) {
    set('setup-lookup', 'done', String(steps.setup_lookup || 'Looked up the project setup'))
    set('setup-python', 'done', String(steps.setup_python || (record.python ? `Python ${record.python}` : '')))
    set('install-deps', 'done', String(steps.install_deps || ''))
  } else if (has(record, 'main_side') || has(record, 'freeze')) {
    set('setup-lookup', 'skipped', 'No setup lookup on this run')
    set('setup-python', 'done', record.python ? `Python ${record.python}` : '')
    set('install-deps', 'skipped', 'Installed with the project only')
  }
  if (has(record, 'freeze') || has(record, 'main_side')) set('install-base', 'done')
  if (buildFailed) {
    set('install-head', 'failed', String(prSide.why))
    for (const id of FLOW_ORDER.slice(FLOW_ORDER.indexOf('benchmark'))) set(id, 'skipped')
    if (typeof record.verdict === 'string' && record.verdict) set('verdict', 'done', record.verdict)
    return marks
  }
  if (has(record, 'pr_side') || has(record, 'freeze')) set('install-head', 'done')
  if (has(record, 'per_run') || has(record, 'comparison')) set('benchmark', 'done')
  if (has(record, 'behaviour_claims') || has(record, 'probe_plan') || has(record, 'probes')) {
    set('probes', 'done')
    set('human-review', record.operator_approval === 'on' || has(record, 'human_review') || has(record, 'hitl_approval') ? 'done' : 'skipped')
  }
  const probes = record.probes as { items?: Array<{ observations?: unknown[] }> } | undefined
  if (probes?.items?.some((item) => (item.observations || []).length > 0)) set('tests', 'done')
  const gap = obj(helper.gap_retry)
  const tries = Array.isArray(gap.tries) ? (gap.tries as Array<Record<string, unknown>>) : []
  if (tries.length > 0) {
    const lines = tries.map((t) => {
      const installed = Array.isArray(t.installed) && t.installed.length ? `installed ${(t.installed as string[]).join(', ')}` : 'nothing installed'
      return `Try ${t.try}: ${t.problem}: ${installed}; ${t.result || ''}`
    })
    set('retries', 'done', lines.join('\n'))
  } else if (typeof record.verdict === 'string' && record.verdict) {
    set('retries', 'skipped', SKIP_TEXT.retries || '')
  }
  const agents = obj(record.agents)
  if (record.model_skipped || agents.status === 'skipped') set('swarm', 'skipped', SKIP_TEXT.swarm || '')
  else if (Object.keys(obj(agents.roles)).length > 0) set('swarm', 'done', "Report written. It doesn't change the verdict.")
  if (typeof record.verdict === 'string' && record.verdict) set('verdict', 'done', record.verdict)
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
    benchmark: fmt(tests),
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
