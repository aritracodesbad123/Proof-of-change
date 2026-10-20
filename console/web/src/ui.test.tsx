import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { illustrativeStates, timelineStates } from './present'
import { SwarmTheater, Timeline, VerdictBadge } from './ui'

test('verdict badges render the four code labels', () => {
  const html = renderToStaticMarkup(
    <div>
      <VerdictBadge verdict="verified" />
      <VerdictBadge verdict="needs_attention" />
      <VerdictBadge verdict="could_not_verify" />
      <VerdictBadge verdict="no_code_change" />
    </div>,
  )
  expect(html).toMatchSnapshot()
  expect(html).toContain('tone-verified')
  expect(html).toContain('needs attention')
  expect(html).toContain('could not verify')
  expect(html).toContain('no code change')
})

test('the swarm is labelled as advice that does not change the verdict', () => {
  const html = renderToStaticMarkup(
    <SwarmTheater swarm={{ ultra: 'active', lightning: 'idle', super: 'idle' }} currentAgent="ultra" detail="judging" />,
  )
  expect(html).toContain('Advice only')
  expect(html).toContain('doesn’t change the verdict')
  expect(html).toContain('Ultra')
})

test('a live timeline puts swarm stages on Advice, not Verdict', () => {
  const html = renderToStaticMarkup(
    <Timeline steps={timelineStates([{ stage: 'verdict' }, { stage: 'agent_judge' }], 'agent_judge')} />,
  )
  expect(html).toContain('Advice (swarm)')
  expect(html).toContain('Doesn&#x27;t change the verdict')
  expect(html.indexOf('Advice (swarm)')).toBeGreaterThan(html.indexOf('>Verdict<'))
  const current = html.slice(html.indexOf('aria-current="step"'))
  expect(current).toContain('Advice (swarm)')
  expect(current).not.toContain('>Verdict<')
})

test('a live timeline marks the current stage for assistive tech', () => {
  const html = renderToStaticMarkup(<Timeline steps={illustrativeStates(2)} />)
  expect(html).toContain('aria-current="step"')
  expect(html).toContain('Base vs PR tests')
})
