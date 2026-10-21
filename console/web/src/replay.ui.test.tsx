import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { ReplayConsole } from './replay'
import type { ReplayCatalog } from './replayData'

const catalog: ReplayCatalog = {
  mode: 'replay',
  note: 'Finished checks stored in this folder.',
  checks: [
    {
      id: 'demo-1',
      kind: 'pull_request',
      repo: 'rasbt/mlxtend',
      pr: 1229,
      title: 'Fix feature groups',
      verdict: 'needs_attention',
      reason: 'probe differs',
      tested_at_ist: '2026-10-10 11:54 IST',
      record: 'checks/demo-1/record.json',
      report_html: 'checks/demo-1/REPORT.html',
    },
  ],
}

const record = {
  id: 'demo-1',
  repo: 'rasbt/mlxtend',
  verdict: 'needs_attention',
  reason: 'probe differs',
  pr: { number: 1229, url: 'https://github.com/rasbt/mlxtend/pull/1229', title: 'Fix feature groups' },
  per_run: [{ side: 'old', passed: 9 }],
  comparison: { same: 9 },
}

test('the replay page shows the flow chart and the report without calling fetch', () => {
  const html = renderToStaticMarkup(
    <ReplayConsole catalog={catalog} records={{ 'demo-1': record }} initialId="demo-1" />,
  )
  expect(html).toContain('How this check moves')
  expect(html).toContain('needs attention')
  expect(html).toContain('Report')
  expect(html).toContain('checks/demo-1/REPORT.html')
  expect(html).not.toContain('/api/')
})

test('the replay list shows a finished verdict', () => {
  const html = renderToStaticMarkup(<ReplayConsole catalog={catalog} records={{}} />)
  expect(html).toContain('mlxtend')
  expect(html).toContain('needs attention')
  expect(html).toContain('How this check moves')
})
