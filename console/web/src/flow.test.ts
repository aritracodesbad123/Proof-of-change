import { expect, test } from 'vitest'
import { flowNodes, statesFromEvents, statesFromRecord } from './flow'

test('pytest progress keeps existing tests running until coverage', () => {
  const marks = statesFromEvents([
    { at: 1, stage: 'pytest', detail: 'before run 1/1' },
    { at: 2, stage: 'pytest', detail: 'still running (30s)' },
    { at: 3, stage: 'pytest', detail: 'after run 1/1' },
  ])
  expect(marks['existing-tests'].state).toBe('running')
  expect(marks.compare.state).toBe('pending')
  const covered = statesFromEvents([{ at: 4, stage: 'pytest', detail: 'before coverage' }])
  expect(covered['existing-tests'].state).toBe('done')
  expect(covered.compare.state).toBe('running')
})

test('advice stays after the verdict and a failed install skips later steps', () => {
  const nodes = flowNodes(
    [
      { at: 1, stage: 'verdict', detail: 'computing code verdict' },
      { at: 2, stage: 'agent_judge', detail: 'notes' },
    ],
    null,
  )
  const verdict = nodes.find((node) => node.id === 'verdict')
  const advice = nodes.find((node) => node.id === 'advice')
  expect(verdict && advice && nodes.indexOf(verdict) < nodes.indexOf(advice)).toBe(true)
  expect(advice?.hint).toContain("Doesn't change the verdict")
  const failed = statesFromRecord({
    repo: 'numpy/numpy',
    pr: { number: 1 },
    pr_side: { why: 'source build of PR head failed' },
    verdict: 'could_not_verify',
  })
  expect(failed['install-head'].state).toBe('failed')
  expect(failed['existing-tests'].state).toBe('skipped')
  expect(failed.verdict.state).toBe('skipped')
})

test('a stored verdict is not treated as a failed node by itself', () => {
  const marks = statesFromRecord({
    repo: 'rasbt/mlxtend',
    pr: { number: 1229 },
    tested: { main: 'a', pr: 'b' },
    main_side: {},
    pr_side: {},
    per_run: [{}],
    comparison: {},
    probes: { items: [{ observations: [{ name: 'cols' }] }] },
    verdict: 'could_not_verify',
    agents: { status: 'skipped' },
  })
  expect(marks.verdict.state).toBe('done')
  expect(marks.advice.state).toBe('skipped')
  expect(marks['install-head'].state).toBe('done')
})

test('human review is its own step between the AI probes and running them', () => {
  const nodes = flowNodes(
    [
      { at: 1, stage: 'claims', detail: 'drafting' },
      { at: 2, stage: 'await_human', detail: 'waiting for operator approval' },
    ],
    null,
  )
  const ids = nodes.map((node) => node.id)
  expect(ids.indexOf('ai-write')).toBeLessThan(ids.indexOf('human-review'))
  expect(ids.indexOf('human-review')).toBeLessThan(ids.indexOf('before-after'))
  expect(nodes.find((node) => node.id === 'ai-write')?.state).toBe('done')
  expect(nodes.find((node) => node.id === 'human-review')?.state).toBe('running')
  expect(nodes.find((node) => node.id === 'before-after')?.state).toBe('pending')
})

test('a check that skipped the review shows that step as skipped', () => {
  const marks = statesFromEvents([
    { at: 1, stage: 'claims', detail: '' },
    { at: 2, stage: 'probes', detail: '' },
  ])
  expect(marks['human-review'].state).toBe('skipped')
  const reviewed = statesFromRecord({ repo: 'a/b', probes: { items: [] }, behaviour_claims: [1], operator_approval: 'on' })
  expect(reviewed['human-review'].state).toBe('done')
})

test('python setup and dependency install are their own steps before the tests', () => {
  const nodes = flowNodes(
    [
      { at: 1, stage: 'fetch_pr', detail: '' },
      { at: 2, stage: 'setup_python', detail: 'Python 3.14: auto-fix: installed in the sandbox' },
      { at: 3, stage: 'install_deps', detail: 'main install: installing the project' },
      { at: 4, stage: 'install_main', detail: 'installing main side' },
    ],
    null,
  )
  const ids = nodes.map((node) => node.id)
  expect(ids.indexOf('setup-python')).toBeLessThan(ids.indexOf('install-deps'))
  expect(ids.indexOf('install-deps')).toBeLessThan(ids.indexOf('existing-tests'))
  const py = nodes.find((node) => node.id === 'setup-python')
  expect(py?.label).toBe('Set up Python 3.14')
  expect(py?.state).toBe('done')
  expect(nodes.find((node) => node.id === 'install-deps')?.state).toBe('running')
})

test('a failed python setup stops everything after it', () => {
  const marks = statesFromEvents([
    { at: 1, stage: 'fetch_pr', detail: '' },
    { at: 2, stage: 'setup_python', detail: 'failed: Python 3.14: not applied' },
  ])
  expect(marks['setup-python'].state).toBe('failed')
  expect(marks['install-deps'].state).toBe('skipped')
  expect(marks['existing-tests'].state).toBe('skipped')
  const rec = statesFromRecord({
    repo: 'a/b', pr: { number: 1 }, tested: { main: 'a', pr: 'b' },
    demo_helper: { setup_plan: { python: { requested: '3.14', gate_failed: true, reason: 'not applied' } } },
  })
  expect(rec['setup-python'].state).toBe('failed')
  expect(rec.verdict.state).toBe('skipped')
})

test('the dependency step lists what was installed and fixed', () => {
  const marks = statesFromRecord({
    repo: 'a/b', pr: { number: 1 }, tested: { main: 'a', pr: 'b' }, main_side: {}, pr_side: {}, freeze: {},
    demo_helper: {
      setup_plan: { python: { requested: '3.14', applied: true, reason: 'auto-fix: installed' }, extra_reqs: ['pytest>=7'] },
      installs: [{ package: 'pytest', version: '8.3.0' }],
      auto_fixes: ['Auto-fix: Python 3.14 was missing'],
    },
  })
  expect(marks['setup-python'].state).toBe('done')
  expect(marks['setup-python'].detail).toContain('Auto-fix')
  expect(marks['install-deps'].state).toBe('done')
  expect(marks['install-deps'].detail).toContain('pytest 8.3.0')
})

test('a setup problem fails the dependency step and skips the tests', () => {
  const marks = statesFromRecord({
    repo: 'a/b', pr: { number: 1 }, tested: { main: 'a', pr: 'b' }, main_side: {},
    demo_helper: { setup: { counts_as_verdict: false, step: 'main install', detail: 'install failed' } },
  })
  expect(marks['install-deps'].state).toBe('failed')
  expect(marks['install-deps'].detail).toContain('setup problem')
  expect(marks['existing-tests'].state).toBe('skipped')
})
