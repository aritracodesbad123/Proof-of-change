import { useState, type FormEvent } from 'react'

/** Password field for a judge's own Nebius key. The value is not written to browser storage. */
export function NebiusKeyField({
  stored,
  onSave,
}: {
  stored: boolean
  onSave: (value: string) => Promise<void>
}) {
  const [value, setValue] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setMessage(null)
    try {
      await onSave(value)
      setValue('')
      setMessage(value.trim() ? 'Saved for this session.' : 'Cleared for this session.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="key-form" onSubmit={(event) => void submit(event)}>
      <label htmlFor="nebius-key">Nebius API key (optional)</label>
      <div className="url-row">
        <input
          id="nebius-key"
          type="password"
          name="nebius-session-key"
          autoComplete="off"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder={stored ? 'A key is stored for this session' : 'Paste a key for this session only'}
        />
        <button type="submit" disabled={busy}>
          {busy ? 'Saving…' : 'Save key'}
        </button>
      </div>
      <p className="hint">
        The key stays in the server's memory for this sign-in. It is not saved to disk, logs, or the report. Leave it
        blank and save to clear it. Without a key, a live check uses the recorded AI answers.
      </p>
      {message ? <p className="hint">{message}</p> : null}
    </form>
  )
}

/** Hidden field for the judge's own Tavily key. The value is not written to browser storage. */
export function TavilyKeyField({
  stored,
  onSave,
}: {
  stored: boolean
  onSave: (value: string) => Promise<void>
}) {
  const [value, setValue] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setMessage(null)
    try {
      await onSave(value)
      setValue('')
      setMessage(value.trim() ? 'Saved for this session.' : 'Cleared for this session.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="key-form" onSubmit={(event) => void submit(event)}>
      <label htmlFor="tavily-key">Tavily API key</label>
      <div className="url-row">
        <input
          id="tavily-key"
          type="password"
          name="tavily-session-key"
          autoComplete="off"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder={stored ? 'A key is stored for this session' : 'Paste a key for this session only'}
        />
        <button type="submit" disabled={busy}>
          {busy ? 'Saving…' : 'Save key'}
        </button>
      </div>
      <p className="hint">
        The lookup needs your own key. This project does not ship one. Tavily keys are free at https://app.tavily.com/.
        The value stays in the server's memory for this sign-in and is sent only as TAVILY_API_KEY for that check. It
        is not saved to disk, logs, or the report. Without a key, the lookup is skipped. A Codespace asks for the same
        value as the recommended secret TAVILY_API_KEY.
      </p>
      {message ? <p className="hint">{message}</p> : null}
    </form>
  )
}
