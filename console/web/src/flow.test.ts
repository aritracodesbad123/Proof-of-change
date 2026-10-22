import { expect, test } from 'vitest'
import { FLOW_ORDER, flowNodes, statesFromEvents, statesFromRecord } from './flow'

test('the chart has every step of the check as its own node, in order', () => {
  const labels = flowNodes([], null).map((node) => node.label)
  expect(labels).toEqual([
    'Read the PR',
    'Setup lookup',
    'Set up Python',
    'Install dependencies',
    'Install main',
    'Install PR',
    'Benchmark suite',
    'Probes',
    'Review',
    'Tests',
    'Retries',
    'Swarm report',
    'Verdict',
  ])
  expect(FLOW_ORDER.length).toBe(13)
})

test('setup steps show what was found and installed in plain words', () => {
  const marks = statesFromEvents([
    { at: 1, stage: 'fetch_pr', detail: 'a/b#1' },
    { at: 2, stage: 'setup_lookup', detail: 'Found 3 setup item(s)' },
    { at: 3, stage: 'setup_python', detail: 'Using Python 3.12' },
    { at: 4, stage: 'install_deps', detail: 'Wrote requirements.txt and installed it on main and pr: numpy.' },
  ])
  expect(marks.intake.state).toBe('done')
  expect(marks['setup-lookup'].detail).toContain('Found 3')
  expect(marks['setup-python'].state).toBe('done')
  expect(marks['install-deps'].state).toBe('running')
  expect(marks['install-deps'].detail).toContain('requirements.txt')
})

test('probes written before the PR installs do not close later steps early', () => {
  const marks = statesFromEvents([
    { at: 1, stage: 'install_main', detail: '' },
    { at: 2, stage: 'claims', detail: 'planning' },
    { at: 3, stage: 'install_pr', detail: 'installing PR side' },
  ])
  expect(marks.probes.state).toBe('done')
  expect(marks['install-head'].state).toBe('running')
  expect(marks.benchmark.state).toBe('pending')
})

test('the project tests are the benchmark suite and coverage belongs to tests', () => {
  const marks = statesFromEvents([
    { at: 1, stage: 'pytest', detail: 'dual-run pytest on main and PR' },
    { at: 2, stage: 'pytest', detail: 'after run 1/1' },
  ])
  expect(marks.benchmark.state).toBe('running')
  const later = statesFromEvents([
    { at: 1, stage: 'pytest', detail: 'dual-run pytest on main and PR' },
    { at: 2, stage: 'probes', detail: 'running behaviour probes' },
    { at: 3, stage: 'pytest', detail: 'before coverage' },
  ])
  expect(later.benchmark.state).toBe('done')
  expect(later.tests.state).toBe('running')
  expect(later['human-review'].state).toBe('skipped')
})

test('every retry is listed and a clean check marks retries skipped', () => {
  const marks = statesFromEvents([
    { at: 1, stage: 'verdict', detail: '' },
    { at: 2, stage: 'retry', detail: 'Try 1 of 3: installed foo 1.0 on main and pr; rerunning' },
    { at: 3, stage: 'retry', detail: 'Try 2 of 3: installed bar 2.0 on main and pr; rerunning' },
    { at: 4, stage: 'done', detail: '' },
  ])
  expect(marks.retries.state).toBe('done')
  expect(marks.retries.detail).toContain('Try 1 of 3')
  expect(marks.retries.detail).toContain('Try 2 of 3')
  const clean = statesFromEvents([
    { at: 1, stage: 'verdict', detail: '' },
    { at: 2, stage: 'done', detail: '' },
  ])
  expect(clean.retries.state).toBe('skipped')
  expect(clean.swarm.state).toBe('skipped')
})

test('the swarm report says it does not change the verdict', () => {
  const nodes = flowNodes([{ at: 1, stage: 'agent_judge', detail: 'notes' }], null)
  const swarm = nodes.find((node) => node.id === 'swarm')
  expect(swarm?.state).toBe('running')
  expect(swarm?.hint).toContain("don't change the verdict")
})

test('a failed PR install skips later steps; a stored record fills in the steps', () => {
  const failed = statesFromRecord({
    repo: 'numpy/numpy',
    pr: { number: 1 },
    pr_side: { why: 'source build of PR head failed' },
    verdict: 'could_not_verify',
  })
  expect(failed['install-head'].state).toBe('failed')
  expect(failed.benchmark.state).toBe('skipped')
  const marks = statesFromRecord({
    repo: 'rasbt/mlxtend',
    pr: { number: 1229 },
    main_side: {},
    pr_side: {},
    per_run: [{}],
    comparison: {},
    probes: { items: [{ observations: [{ name: 'cols' }] }] },
    verdict: 'could_not_verify',
    agents: { status: 'skipped' },
    demo_helper: {
      setup_plan: { packages: [] },
      steps: { setup_lookup: 'Found 2', setup_python: 'Kept the default Python', install_deps: 'Nothing extra' },
      gap_retry: { tries: [{ try: 1, problem: 'foo', installed: ['foo 1.0'], result: 'still a setup gap: foo' }] },
    },
  })
  expect(marks.verdict.state).toBe('done')
  expect(marks.swarm.state).toBe('skipped')
  expect(marks['setup-lookup'].detail).toBe('Found 2')
  expect(marks.retries.detail).toContain('installed foo 1.0')
})
