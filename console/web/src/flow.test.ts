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
