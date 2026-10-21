import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { NebiusKeyField } from './sessionKey'

test('the Nebius key field is a password and does not echo a stored key', () => {
  const html = renderToStaticMarkup(<NebiusKeyField stored onSave={async () => undefined} />)
  expect(html).toContain('type="password"')
  expect(html).toContain('not saved to disk')
  expect(html).toContain('recorded AI answers')
  expect(html).not.toContain('localStorage')
  expect(html).not.toMatch(/nf-|sk-|ghp_/)
})
