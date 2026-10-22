import type { StageEvent } from './api'

export type NodeId =
  | 'intake'
  | 'checkout-base'
  | 'checkout-head'
  | 'setup-python'
  | 'install-base'
  | 'install-head'
  | 'install-deps'
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
  'setup-python',
  'install-base',
  'install-head',
  'install-deps',
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
  intake: { label: 'PR intake', hint: 'Read the pull request.', x: 40, y: 150 },
  'checkout-base': { label: 'Checkout original', hint: 'The code before the change.', x: 220, y: 48 },
  'checkout-head': { label: 'Checkout the change', hint: 'The code the pull request adds.', x: 220, y: 252 },
  'setup-python': {
    label: 'Set up Python',
    hint: 'The Python version the project asks for, installed in the sandbox and the same on both sides.',
    x: 400,
    y: 150,
  },
  'install-base': { label: 'Install original', hint: 'Install the original side.', x: 580, y: 48 },
  'install-head': { label: 'Install the change', hint: 'Install the change in a sandbox.', x: 580, y: 252 },
  'install-deps': {
    label: 'Install dependencies',
    hint: 'Every library the project lists, the same on both sides. Tests start only after this succeeds.',
    x: 760,
    y: 150,
  },
  'existing-tests': { label: 'Run existing tests', hint: 'The project’s own tests, on both sides.', x: 940, y: 48 },
  'ai-write': { label: 'AI writes probes', hint: 'Behaviour probes written for this change.', x: 940, y: 252 },
  'human-review': {
    label: 'Human review',
    hint: 'You keep or drop each probe and add your own test ideas before anything runs.',
    x: 1120,
    y: 252,
  },
  'before-after': { label: 'Run them on both sides', hint: 'The probes run before and after the change.', x: 1300, y: 252 },
  compare: { label: 'Compare and drop noise', hint: 'Keep differences that are not noise.', x: 1300, y: 48 },
  verifier: { label: 'Reviewer / verifier', hint: 'Plain code checks the comparison.', x: 1480, y: 150 },
  verdict: { label: 'Verdict and report', hint: 'The checker’s verdict and the report.', x: 1660, y: 150 },
  advice: { label: 'Reviewer notes', hint: "Doesn't change the verdict.", x: 1840, y: 150 },
}

export const FLOW_EDGES: [NodeId, NodeId][] = [
  ['intake', 'checkout-base'],
  ['intake', 'checkout-head'],
  ['checkout-base', 'setup-python'],
  ['checkout-head', 'setup-python'],
  ['setup-python', 'install-base'],
  ['setup-python', 'install-head'],
  ['install-base', 'install-deps'],
  ['install-head', 'install-deps'],
  ['install-deps', 'existing-tests'],
  ['install-deps', 'ai-write'],
  ['checkout-head', 'ai-write'],
  ['ai-write', 'human-review'],
  ['human-review', 'before-after'],
  ['install-deps', 'before-after'],
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
    else if (stage === 'setup_python') {
      if (detail.startsWith('failed')) failRest(marks, 'setup-python', detail.replace(/^failed:\s*/, ''))
      else doneThrough(marks, 'setup-python', detail)
    } else if (stage === 'install_deps') {
      if (marks['install-deps'].state === 'pending') marks['install-deps'] = { state: 'running', detail }
      else marks['install-deps'].detail = detail
    }
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
  const helper = (record.demo_helper && typeof record.demo_helper === 'object' ? record.demo_helper : {}) as Record<string, unknown>
  const plan = (helper.setup_plan && typeof helper.setup_plan === 'object' ? helper.setup_plan : {}) as Record<string, unknown>
  const python = (plan.python && typeof plan.python === 'object' ? plan.python : {}) as Record<string, unknown>
  const fixes = Array.isArray(helper.auto_fixes) ? (helper.auto_fixes as string[]) : []
  if (python.requested) {
    const why = [String(python.reason || ''), ...fixes.filter((line) => /python/i.test(line))].filter(Boolean).join(' ')
    if (python.gate_failed) {
      set('setup-python', 'failed', why)
      for (const id of FLOW_ORDER.slice(FLOW_ORDER.indexOf('install-base'))) set(id, 'skipped')
      return marks
    }
    set('setup-python', python.applied ? 'done' : 'skipped', why)
  } else if (has(record, 'tested') || has(record, 'sides')) {
    set('setup-python', 'done', 'The sandbox Python already meets the project')
  }
  if (has(record, 'freeze') || has(record, 'main_side')) set('install-base', 'done')
  const setup = (helper.setup && typeof helper.setup === 'object' ? helper.setup : {}) as Record<string, unknown>
  if (setup.counts_as_verdict === false) {
    set('install-deps', 'failed', `setup problem: ${String(setup.detail || setup.step || 'install failed')}`)
    for (const id of FLOW_ORDER.slice(FLOW_ORDER.indexOf('existing-tests'))) set(id, 'skipped')
    return marks
  }
  if (buildFailed) {
    set('install-head', 'failed', String(prSide.why))
    set('install-deps', 'failed', String(prSide.why))
    for (const id of ['existing-tests', 'ai-write', 'human-review', 'before-after', 'compare', 'verifier', 'verdict', 'advice'] as NodeId[]) {
      set(id, 'skipped')
    }
    return marks
  }
  if (has(record, 'pr_side') || has(record, 'freeze')) {
    set('install-head', 'done')
    const installs = Array.isArray(helper.installs) ? (helper.installs as Array<Record<string, unknown>>) : []
    const reqs = Array.isArray(plan.extra_reqs) ? (plan.extra_reqs as string[]) : []
    const listed = installs.length
      ? installs.map((row) => `${row.package} ${row.version}`).join(', ')
      : reqs.join(', ')
    const other = fixes.filter((line) => !/python/i.test(line))
    set('install-deps', 'done', [listed ? `Installed on both sides: ${listed}` : 'Installed the project and its declared dependencies on both sides', ...other].join(' '))
  }
  if (has(record, 'per_run') || has(record, 'comparison')) set('existing-tests', 'done')
  if (has(record, 'behaviour_claims') || has(record, 'probe_plan') || has(record, 'probes')) {
    set('ai-write', 'done')
    set('human-review', record.operator_approval === 'on' || has(record, 'human_review') || has(record, 'hitl_approval') ? 'done' : 'skipped')
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
  const version = pythonVersion(events, record)
  return FLOW_ORDER.map((id) => ({
    id,
    ...COPY[id],
    label: id === 'setup-python' && version ? `Set up Python ${version}` : COPY[id].label,
    state: marks[id].state,
    detail: marks[id].detail,
    duration: durations[id] || '',
  }))
}

export function pythonVersion(
  events: StageEvent[] | null | undefined,
  record: Record<string, unknown> | null | undefined,
): string {
  const helper = (record?.demo_helper && typeof record.demo_helper === 'object' ? record.demo_helper : {}) as Record<string, unknown>
  const plan = (helper.setup_plan && typeof helper.setup_plan === 'object' ? helper.setup_plan : {}) as Record<string, unknown>
  const python = (plan.python && typeof plan.python === 'object' ? plan.python : {}) as Record<string, unknown>
  if (typeof python.requested === 'string' && /^\d+\.\d+$/.test(python.requested)) return python.requested
  for (const event of events || []) {
    const match = event.stage === 'setup_python' ? /Python (\d+\.\d+)/.exec(event.detail || '') : null
    if (match) return match[1]
  }
  return ''
}

export function edgeActive(from: NodeState, to: NodeState) {
  return from === 'done' || from === 'running' || to === 'running' || to === 'done'
}
