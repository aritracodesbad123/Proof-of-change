import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { LoginButtons } from './auth'

test('a provider button is omitted when that provider is not configured', () => {
  const html = renderToStaticMarkup(<LoginButtons google={false} github={true} />)
  expect(html).toContain('Sign in with GitHub')
  expect(html).not.toContain('Sign in with Google')
  expect(html).not.toContain('/api/auth/google/start')
})

test('both provider buttons show when both providers are configured', () => {
  const html = renderToStaticMarkup(<LoginButtons google github />)
  expect(html.indexOf('Sign in with Google')).toBeGreaterThan(-1)
  expect(html.indexOf('Sign in with GitHub')).toBeGreaterThan(html.indexOf('Sign in with Google'))
})
