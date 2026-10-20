import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { api, type AuthProviders } from './api'

const EMPTY_PROVIDERS: AuthProviders = {
  google: false,
  github: false,
  signup_disabled: false,
  invite_required: false,
}

export function LoginButtons({
  google,
  github,
  invite,
}: {
  google: boolean
  github: boolean
  invite?: string
}) {
  const query = invite ? `?invite_code=${encodeURIComponent(invite)}` : ''
  return (
    <div className="oauth-row">
      {google ? (
        <a className="oauth google" href={`/api/auth/google/start${query}`}>
          Sign in with Google
        </a>
      ) : null}
      {github ? (
        <a className="oauth github" href={`/api/auth/github/start${query}`}>
          Sign in with GitHub
        </a>
      ) : null}
    </div>
  )
}

type Mode = 'login' | 'signup' | 'code'

export default function AuthGate({ children }: { children: ReactNode }) {
  const [email, setEmail] = useState<string | null | undefined>(undefined)

  useEffect(() => {
    let live = true
    void api.me().then(
      (me) => {
        if (live) setEmail(me.email)
      },
      () => {
        if (live) setEmail(null)
      },
    )
    return () => {
      live = false
    }
  }, [])

  if (email === undefined) {
    return (
      <div className="shell">
        <p className="tag">Checking sign-in…</p>
      </div>
    )
  }
  if (email) return children
  return <AuthScreen onAuthed={setEmail} />
}

function AuthScreen({ onAuthed }: { onAuthed: (email: string) => void }) {
  const [mode, setMode] = useState<Mode>('login')
  const [providers, setProviders] = useState<AuthProviders>(EMPTY_PROVIDERS)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [invite, setInvite] = useState('')
  const [challengeId, setChallengeId] = useState('')
  const [purpose, setPurpose] = useState<'signup' | 'login'>('login')
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const authError = params.get('auth_error')
    if (authError) setError(authError)
    void api.providers().then(setProviders).catch(() => setProviders(EMPTY_PROVIDERS))
  }, [])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (mode === 'code') {
        const me = await api.verify(challengeId, code)
        onAuthed(me.email)
        return
      }
      const result = mode === 'signup'
        ? await api.signup(email, password, invite)
        : await api.login(email, password)
      setChallengeId(result.challenge_id)
      setPurpose(result.purpose)
      setCode('')
      setMode('code')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function onResend() {
    setBusy(true)
    setError(null)
    try {
      const result = await api.resend(challengeId)
      setChallengeId(result.challenge_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const showProviders = mode !== 'code' && (providers.google || providers.github)
  return (
    <div className="shell">
      <header className="top">
        <p className="brand">Proof-of-Change</p>
        <p className="tag">Sign in to see your own checks.</p>
      </header>
      <main className="main">
        <section className="panel start">
          <p className="kicker">Operator console</p>
          {mode === 'code' ? (
            <>
              <h1>Enter your code</h1>
              <p className="lede">
                We emailed a 6-digit code to {email || 'you'}. It expires in 10 minutes and works once.
                Nothing is signed in until the code matches.
              </p>
              <p className="auth-note">
                {purpose === 'signup'
                  ? 'This code confirms the email and activates the account.'
                  : 'This code is the second step after the password. It does not change a check.'}
              </p>
            </>
          ) : (
            <>
              <h1>{mode === 'signup' ? 'Create an account' : 'Sign in'}</h1>
              <p className="lede">
                Email and password always continue with a code we email you. Google and GitHub skip that code,
                because those providers already check that it is you.
              </p>
            </>
          )}
          {error ? (
            <p className="banner err" role="alert">
              {error}
            </p>
          ) : null}
          {showProviders ? (
            <>
              <LoginButtons google={providers.google} github={providers.github} invite={invite} />
              <p className="hint">The provider button is hidden when that provider is not configured.</p>
            </>
          ) : null}
          <form className="form" onSubmit={(event) => void onSubmit(event)}>
            {mode === 'code' ? (
              <label>
                6-digit code
                <input
                  className="code-input"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  value={code}
                  onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                  required
                  autoFocus
                />
              </label>
            ) : (
              <>
                <label>
                  Email
                  <input
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    required
                  />
                </label>
                <label>
                  Password
                  <input
                    type="password"
                    autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    minLength={8}
                    required
                  />
                </label>
                {providers.invite_required ? (
                  <label>
                    Invite code
                    <input value={invite} onChange={(event) => setInvite(event.target.value)} required />
                  </label>
                ) : null}
              </>
            )}
            <div className="cta-row">
              <button type="submit" disabled={busy}>
                {busy ? 'Working…' : mode === 'code' ? 'Confirm code' : mode === 'signup' ? 'Create account' : 'Continue'}
              </button>
              {mode === 'code' ? (
                <button type="button" className="ghost sample" disabled={busy} onClick={() => void onResend()}>
                  Email a new code
                </button>
              ) : null}
            </div>
          </form>
          {mode === 'code' ? (
            <button type="button" className="ghost" onClick={() => setMode(purpose === 'signup' ? 'signup' : 'login')}>
              Start over
            </button>
          ) : providers.signup_disabled ? null : (
            <button
              type="button"
              className="ghost"
              onClick={() => {
                setError(null)
                setMode(mode === 'login' ? 'signup' : 'login')
              }}
            >
              {mode === 'login' ? 'Create an account' : 'Have an account? Sign in'}
            </button>
          )}
        </section>
      </main>
    </div>
  )
}
