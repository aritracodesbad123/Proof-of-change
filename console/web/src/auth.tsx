import { useEffect, useState, type FormEvent } from 'react'
import { api, setCsrf, type Account } from './api'

type Mode = 'login' | 'signup'

function useTheme() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    if (typeof document === 'undefined') return 'dark'
    return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark'
  })
  useEffect(() => {
    if (typeof document === 'undefined') return
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('poc-console-theme', theme)
    } catch {
      /* private mode */
    }
  }, [theme])
  return { theme, toggle: () => setTheme((current) => (current === 'dark' ? 'light' : 'dark')) }
}

function modeFromHash(): Mode {
  if (typeof window === 'undefined') return 'login'
  return window.location.hash === '#/signup' ? 'signup' : 'login'
}

export function AuthScreen({ onSignedIn }: { onSignedIn: (account: Account) => void }) {
  const { theme, toggle } = useTheme()
  const [mode, setMode] = useState<Mode>(modeFromHash)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [invite, setInvite] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const sync = () => setMode(modeFromHash())
    window.addEventListener('hashchange', sync)
    return () => window.removeEventListener('hashchange', sync)
  }, [])

  useEffect(() => {
    let stop = false
    setReady(false)
    api
      .csrf()
      .then((body) => {
        if (stop) return
        setCsrf(body.csrf)
        setReady(true)
      })
      .catch((error: unknown) => {
        if (stop) return
        setErr(error instanceof Error ? error.message : String(error))
      })
    return () => {
      stop = true
    }
  }, [mode])

  function go(next: Mode) {
    const hash = next === 'signup' ? '#/signup' : '#/login'
    if (window.location.hash !== hash) window.location.hash = hash
    setMode(next)
    setErr(null)
    setPassword('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      const account =
        mode === 'signup' ? await api.signup(email.trim(), password, invite.trim()) : await api.login(email.trim(), password)
      setPassword('')
      setCsrf(account.csrf)
      onSignedIn(account)
    } catch (error) {
      setErr(error instanceof Error ? error.message : String(error))
    } finally {
      setBusy(false)
    }
  }

  const signingUp = mode === 'signup'

  return (
    <div className="shell">
      <a className="skip" href="#auth-main">
        Skip to content
      </a>
      <header className="top">
        <div className="brand-block">
          <p className="brand">Proof-of-Change</p>
          <p className="tag">NVIDIA Nemotron on Nebius. Sign in to see the checks you started.</p>
        </div>
        <div className="top-actions">
          <button type="button" className="theme-toggle" aria-pressed={theme === 'light'} onClick={toggle}>
            {theme === 'light' ? 'Dark theme' : 'Light theme'}
          </button>
        </div>
      </header>
      <main id="auth-main" className="auth-layout">
        <section className="panel auth-card">
          <p className="kicker">Operator console</p>
          <h1>{signingUp ? 'Create an account' : 'Sign in'}</h1>
          <p className="lede">
            {signingUp
              ? 'A new account only sees the checks it starts.'
              : 'You only see the checks this account started.'}
          </p>
          {err ? (
            <p className="banner err" role="alert">
              {err}
            </p>
          ) : null}
          <form className="form" onSubmit={(event) => void submit(event)}>
            <label htmlFor="email">
              Email
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label htmlFor="password">
              Password
              <input
                id="password"
                name="password"
                type="password"
                autoComplete={signingUp ? 'new-password' : 'current-password'}
                required
                minLength={8}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            {signingUp ? (
              <label htmlFor="invite">
                Invite code
                <input
                  id="invite"
                  name="invite"
                  autoComplete="off"
                  value={invite}
                  onChange={(event) => setInvite(event.target.value)}
                />
              </label>
            ) : null}
            {signingUp ? <p className="hint">Leave the invite code blank unless this demo asked for one.</p> : null}
            <button type="submit" disabled={busy || !ready}>
              {busy ? 'Please wait…' : signingUp ? 'Create account' : 'Sign in'}
            </button>
          </form>
          {signingUp ? (
            <button type="button" className="text-link" onClick={() => go('login')}>
              Already have an account? Sign in
            </button>
          ) : (
            <button type="button" className="text-link" onClick={() => go('signup')}>
              Need an account? Sign up
            </button>
          )}
        </section>
      </main>
    </div>
  )
}
