import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { api, setCsrf, type Account } from './api'
import { AuthScreen } from './auth'
import './index.css'

function Root() {
  const [account, setAccount] = useState<Account | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let stop = false
    api
      .me()
      .then((me) => {
        if (stop) return
        setCsrf(me.csrf)
        setAccount(me)
      })
      .catch(() => {
        /* signed out, or the API is still starting */
      })
      .finally(() => {
        if (!stop) setReady(true)
      })
    return () => {
      stop = true
    }
  }, [])

  async function logout() {
    try {
      await api.logout()
    } catch {
      /* drop the local view even if the API is down */
    }
    setCsrf('')
    setAccount(null)
    if (window.location.hash !== '#/login') window.location.hash = '#/login'
  }

  if (!ready) {
    return (
      <div className="shell">
        <p className="hint">Loading…</p>
      </div>
    )
  }
  if (!account) {
    return (
      <AuthScreen
        onSignedIn={(next) => {
          setAccount(next)
          if (window.location.hash !== '#/') window.location.hash = '#/'
        }}
      />
    )
  }
  return <App account={account} onLogout={() => void logout()} />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
