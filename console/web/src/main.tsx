import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import AuthGate from './auth'
import ReplayApp from './replay'
import { replayMode } from './replayData'
import './index.css'
import './App.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {replayMode ? (
      <ReplayApp />
    ) : (
      <AuthGate>
        <App />
      </AuthGate>
    )}
  </StrictMode>,
)
