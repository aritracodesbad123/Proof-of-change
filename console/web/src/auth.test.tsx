import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { AuthScreen, LoginButtons } from './auth'

test('a provider button is omitted when that provider is not configured', () => {
  const html = renderToStaticMarkup(<LoginButtons google={false} github={true} />)
  expect(html).toContain('Sign in with GitHub')
  expect(html).not.toContain('Sign in with Google')
  expect(html).not.toContain('/api/auth/google/start')
})

test('a public port tells the reader to set it back to private', () => {
  const html = renderToStaticMarkup(
    <AuthScreen
      onAuthed={() => undefined}
      notice="Port 8787 is public. Set port 8787 back to private in the Ports panel, then start the console again. Sign-in stays required while that port is public."
    />,
  )
  expect(html).toContain('Set port 8787 back to private')
  expect(html).toContain('Sign-in stays required')
})

test('both provider buttons show when both providers are configured', () => {
  const html = renderToStaticMarkup(<LoginButtons google github />)
  expect(html.indexOf('Sign in with Google')).toBeGreaterThan(-1)
  expect(html.indexOf('Sign in with GitHub')).toBeGreaterThan(html.indexOf('Sign in with Google'))
})
