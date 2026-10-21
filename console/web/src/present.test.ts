import { readFileSync } from 'node:fs'
import { describe, expect, test } from 'vitest'
import {
  behaviourMap,
  costTime,
  coveragePlain,
  filterRuns,
  illustrativeStates,
  logSections,
  reasonPoints,
  demoHelperLines,
  TIMELINE_SPEC,
  timelineStates,
  verdictLabel,
  verdictPlain,
  verdictTone,
} from './present'

describe('demo helper notes stay background', () => {
  test('lines come from the record and an empty record stays empty', () => {
    expect(demoHelperLines({})).toEqual([])
    expect(
      demoHelperLines({
        demo_helper: { notes: ['Looked up with Tavily: 1 results', 'Setup plan: install pytest on main and pr'] },
        verdict: 'verified',
      }),
    ).toEqual(['Looked up with Tavily: 1 results', 'Setup plan: install pytest on main and pr'])
  })
})

describe('verdict badges stay labels for the code verdict', () => {
  test('four tones keep their words', () => {
    expect(verdictTone('verified')).toBe('verified')
    expect(verdictTone('needs_attention')).toBe('needs_attention')
    expect(verdictTone('could_not_verify')).toBe('could_not_verify')
    expect(verdictTone('no_code_change')).toBe('no_code_change')
    expect(verdictLabel('needs_attention')).toBe('needs attention')
    expect(verdictPlain('verified')).toMatch(/Verified/)
    expect(verdictTone('something_else')).toBe('unknown')
    expect(verdictLabel('something_else')).toBe('something_else')
  })

  test('a record verdict is shown as stored, not replaced', () => {
    const record = { verdict: 'needs_attention', reason: 'probe: claim(s) C1 proven' }
    expect(record.verdict).toBe('needs_attention')
    expect(verdictLabel(record.verdict)).toBe('needs attention')
    expect(verdictPlain(record.verdict)).not.toMatch(/Verified —/)
  })
})

describe('timeline follows real stage events', () => {
  test('starts pending', () => {
    expect(timelineStates([], null).map((step) => step.state)).toEqual([
      'pending', 'pending', 'pending', 'pending', 'pending', 'pending', 'pending',
    ])
  })

  test('claims between installs do not pretend tests already ran', () => {
    const steps = timelineStates(
      [{ stage: 'fetch_pr' }, { stage: 'install_main' }, { stage: 'claims' }],
      'claims',
    )
    const byId = Object.fromEntries(steps.map((step) => [step.id, step.state]))
    expect(byId.fetch).toBe('done')
    expect(byId.sandbox).toBe('started')
    expect(byId.tests).toBe('pending')
    expect(byId.probes).toBe('current')
    expect(byId.coverage).toBe('pending')
    expect(byId.verdict).toBe('pending')
  })

  test('coverage is done once the code verdict stage is reached', () => {
    const steps = timelineStates(
      [{ stage: 'fetch_pr' }, { stage: 'pytest' }, { stage: 'probes' }, { stage: 'verdict' }],
      'verdict',
    )
    const byId = Object.fromEntries(steps.map((step) => [step.id, step.state]))
    expect(byId.tests).toBe('done')
    expect(byId.probes).toBe('done')
    expect(byId.coverage).toBe('done')
    expect(byId.verdict).toBe('current')
    expect(byId.advice).toBe('pending')
  })

  test('a failure marks the last reached stage and skips the rest', () => {
    const steps = timelineStates(
      [{ stage: 'fetch_pr' }, { stage: 'install_pr' }, { stage: 'pytest' }, { stage: 'failed' }],
      'failed',
    )
    const byId = Object.fromEntries(steps.map((step) => [step.id, step.state]))
    expect(byId.fetch).toBe('done')
    expect(byId.sandbox).toBe('done')
    expect(byId.tests).toBe('failed')
    expect(byId.probes).toBe('skipped')
    expect(byId.verdict).toBe('skipped')
    expect(byId.advice).toBe('skipped')
  })

  test('swarm stages land under Advice and never under Verdict', () => {
    const verdict = TIMELINE_SPEC.find((step) => step.id === 'verdict')
    const advice = TIMELINE_SPEC.find((step) => step.id === 'advice')
    expect(advice?.label).toBe('Advice (swarm)')
    expect(TIMELINE_SPEC.findIndex((step) => step.id === 'advice')).toBeGreaterThan(
      TIMELINE_SPEC.findIndex((step) => step.id === 'verdict'),
    )
    for (const stage of ['agent_judge', 'agent_helper', 'agent_summary'] as const) {
      expect(verdict?.stages).not.toContain(stage)
      expect(advice?.stages).toContain(stage)
      const steps = timelineStates([{ stage: 'verdict' }, { stage }], stage)
      expect(steps.find((step) => step.id === 'verdict')?.state).toBe('done')
      expect(steps.find((step) => step.id === 'advice')?.state).toBe('current')
      expect(steps.find((step) => step.label === 'Verdict')?.state).not.toBe('current')
    }
  })

  test('the landing illustration walks every stage then rests', () => {
    expect(illustrativeStates(0).map((step) => step.state)[0]).toBe('current')
    expect(illustrativeStates(5).find((step) => step.id === 'verdict')?.state).toBe('current')
    expect(illustrativeStates(8).every((step) => step.state === 'pending')).toBe(true)
  })
})

test('reasons become short sentences without dropping the evidence', () => {
  const points = reasonPoints(
    'probe: 2 observation(s) need attention: caller column differs; probe: claim(s) C1, C2 proven; tests: 1 new test(s) pass',
  )
  expect(points[0]).toMatch(/needs a look/)
  expect(points[0]).toMatch(/caller column differs/)
  expect(points[1]).toMatch(/C1, C2/)
  expect(points[2]).toMatch(/Project tests/)
})

test('cost and time are read from the record and not added up', () => {
  const shown = costTime({
    cost: { ai_cost_usd: 0.002891, computer_cost_usd: 0.157573, input_tokens: 10, output_tokens: 20, cost_complete: false },
    duration_s: { total_wall: 2363.6, tests: 610.6 },
  })
  expect(shown.ai).toBe('$0.0029')
  expect(shown.computer).toBe('$0.16')
  expect(shown.total).toBeNull()
  expect(shown.wall).toBe('39m 24s')
  expect(shown.tests).toBe('10m 11s')
  expect(shown.complete).toBe(false)
})

test('coverage text uses the stored counts', () => {
  expect(coveragePlain({ coverage: { status: 'measured', changed_lines_total: 18, changed_lines_covered: 14 } }))
    .toBe('14 of 18 changed executable lines ran (78%).')
})

test('logs split into collapsible sections', () => {
  const sections = logSections('--- stderr ---\nboom\n--- stdout ---\nhello\n')
  expect(sections.map((section) => section.title)).toEqual(['stderr', 'stdout'])
  const long = logSections(Array.from({ length: 30 }, (_, i) => `line ${i}`).join('\n'))
  expect(long.length).toBeGreaterThan(1)
  expect(long[0].title).toMatch(/Lines/)
})

test('run cards filter by verdict and text', () => {
  const runs = [
    { id: 'a', repo: 'rasbt/mlxtend', pr: 1229, title: 'groups', verdict: 'needs_attention' },
    { id: 'b', repo: 'pandas-dev/pandas', pr: 1, title: 'dtype', verdict: 'verified' },
  ]
  expect(filterRuns(runs, 'mlxtend', 'all')).toHaveLength(1)
  expect(filterRuns(runs, '', 'verified').map((run) => run.id)).toEqual(['b'])
  expect(filterRuns(runs, 'dtype', 'needs_attention')).toHaveLength(0)
})

test('behaviour map links claims to the probes that name them', () => {
  const map = behaviourMap({
    probe_plan: { model_claims: [{ id: 'C1', text: 'Groups shuffle together', expect: 'change' }] },
    probes: { items: [{ id: 'probe-groups', about: 'shuffle', claims: [{ id: 'C1' }], observations: [{ name: 'cols', label: 'proven', claim: 'C1' }] }] },
  })
  expect(map.claims[0].probeIds).toEqual(['probe-groups'])
  expect(map.claims[0].result).toBe('proven')
})

test('the stylesheet is the light console, with the green accent and reduced motion', () => {
  const css = readFileSync(new URL('./App.css', import.meta.url), 'utf8') + readFileSync(new URL('./index.css', import.meta.url), 'utf8')
  expect(css).toContain('--nvidia-green: #76b900')
  expect(css).toContain('--paper: #f4f6ef')
  expect(css).toContain('--link: #3d6200')
  expect(css).not.toContain("data-theme='dark'")
  expect(css).toContain('prefers-reduced-motion')
  expect(css).toContain('.tone-verified')
  expect(css).toContain('.tone-needs_attention')
  expect(css).toContain('.tone-could_not_verify')
  expect(css).toContain('.tone-no_code_change')
})
