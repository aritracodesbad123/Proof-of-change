import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { NebiusKeyField, TavilyKeyField } from './sessionKey'

test('the Nebius key field is a password and does not echo a stored key', () => {
  const html = renderToStaticMarkup(<NebiusKeyField stored onSave={async () => undefined} />)
  expect(html).toContain('type="password"')
  expect(html).toContain('not saved to disk')
  expect(html).toContain('recorded AI answers')
  expect(html).not.toContain('localStorage')
  expect(html).not.toMatch(/nf-|sk-|ghp_|tvly-/)
})

test('the Tavily key field is a hidden optional secret and does not echo a key', () => {
  const html = renderToStaticMarkup(<TavilyKeyField stored={false} onSave={async () => undefined} />)
  expect(html).toContain('type="password"')
  expect(html).toContain('Tavily API key (optional)')
  expect(html).toContain('TAVILY_API_KEY')
  expect(html).toContain('not saved to disk')
  expect(html).toContain('lookup is skipped')
  expect(html).not.toContain('localStorage')
  expect(html).not.toMatch(/tvly-/)
})
