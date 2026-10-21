import { expect, test } from 'vitest'
import { assertReplayUrl, fetchReplay, joinReplay } from './replayData'

const catalog = {
  mode: 'replay',
  note: 'Finished checks stored in this folder.',
  checks: [
    {
      id: 'demo-1',
      kind: 'pull_request',
      repo: 'rasbt/mlxtend',
      pr: 1229,
      title: 'sample',
      verdict: 'needs_attention',
      reason: 'probe differs',
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
  pr: { number: 1229, url: 'https://github.com/rasbt/mlxtend/pull/1229', title: 'sample' },
}

test('replay refuses API and network URLs', () => {
  expect(() => assertReplayUrl('/api/health')).toThrow(/live API/)
  expect(() => assertReplayUrl('https://api.github.com/repos/o/r')).toThrow(/network/)
  expect(() => assertReplayUrl('https://api.tokenfactory.nebius.com/v1')).toThrow(/network/)
  expect(() => assertReplayUrl('./replay/catalog.json')).not.toThrow()
  expect(() => assertReplayUrl('replay/checks/demo-1/record.json')).not.toThrow()
})

test('replay loads the catalog and records with no network URLs', async () => {
  const seen: string[] = []
  const fetchImpl = (async (url: string) => {
    seen.push(String(url))
    assertReplayUrl(String(url))
    if (String(url).endsWith('catalog.json')) {
      return { ok: true, json: async () => catalog }
    }
    return { ok: true, json: async () => record }
  }) as unknown as typeof fetch
  const loaded = await fetchReplay(fetchImpl, './')
  expect(seen).toEqual(['./replay/catalog.json', './replay/checks/demo-1/record.json'])
  expect(loaded.catalog.checks).toHaveLength(1)
  expect(loaded.records['demo-1'].verdict).toBe('needs_attention')
  expect(joinReplay('./', 'replay/catalog.json')).toBe('./replay/catalog.json')
})
