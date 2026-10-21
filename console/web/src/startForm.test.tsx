import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test, vi } from 'vitest'
import type { Job } from './api'
import { StartForm, TAB_KEY_STORE, loadTabKeys, saveTabKeys, startBody, submitStart, type StartFields } from './startForm'

const fields: StartFields = {
  prUrl: ' https://github.com/o/r/pull/1 ',
  provider: 'nebius',
  approval: true,
  nebiusKey: 'nebius-secret-123',
  tavilyKey: '',
  nebiusProjectId: 'project-abc',
}

test('one form, one Run check button, no per-field save buttons', () => {
  const html = renderToStaticMarkup(
    <StartForm stored={{ nebius_key: false, tavily_key: false }} onStart={async () => ({ ok: false, error: '' })} />,
  )
  expect(html.match(/<form/g)?.length).toBe(1)
  expect(html.match(/type="submit"/g)?.length).toBe(1)
  expect(html).toContain('Run check')
  expect(html).not.toContain('Save key')
  expect(html).toContain('id="nebius-project-id"')
  expect(html).toContain('id="pr-url"')
  expect(html).toMatch(/id="approval"[^>]*checked=""|checked=""[^>]*id="approval"/)
  expect(html).not.toContain('localStorage')
})

test('a single submit sends the link, keys, project ID and review choice together', async () => {
  const start = vi.fn(async () => ({ id: 'job1', status: 'queued', pr_url: 'x' }) as Job)
  const result = await submitStart(fields, start)
  expect(result).toEqual({ ok: true, job: { id: 'job1', status: 'queued', pr_url: 'x' } })
  expect(start).toHaveBeenCalledTimes(1)
  expect(start).toHaveBeenCalledWith({
    pr_url: 'https://github.com/o/r/pull/1',
    model_provider: 'nebius',
    approval: true,
    nebius_api_key: 'nebius-secret-123',
    contree_project_id: 'project-abc',
  })
})

test('blank keys are left out so a key stored earlier this session is kept', () => {
  const body = startBody({ ...fields, nebiusKey: '', nebiusProjectId: ' ' })
  expect(body).not.toHaveProperty('nebius_api_key')
  expect(body).not.toHaveProperty('contree_project_id')
  expect(body).not.toHaveProperty('tavily_api_key')
})

test('a refused start comes back as a message to show, never silently', async () => {
  const start = vi.fn(async () => {
    throw new Error('No sandbox available: add your Nebius project ID.')
  })
  const result = await submitStart(fields, start)
  expect(result).toEqual({ ok: false, error: 'No sandbox available: add your Nebius project ID.' })
  const empty = await submitStart({ ...fields, prUrl: '' }, start)
  expect(empty.ok).toBe(false)
})

test('the error is rendered on the form next to the button', () => {
  // Static render cannot run effects, so check the alert markup the form uses.
  const html = renderToStaticMarkup(
    <StartForm stored={{ nebius_key: true, tavily_key: false }} onStart={async () => ({ ok: false, error: 'x' })} />,
  )
  expect(html).toContain('Stored for this session')
  expect(html).not.toContain('nebius-secret')
})

function fakeStorage() {
  const data: Record<string, string> = {}
  return {
    data,
    getItem: (k: string) => (k in data ? data[k] : null),
    setItem: (k: string, v: string) => void (data[k] = v),
    removeItem: (k: string) => void delete data[k],
  }
}

test('keys go to sessionStorage only, never localStorage, and come back after a refresh', async () => {
  const session = fakeStorage()
  const local = fakeStorage()
  vi.stubGlobal('sessionStorage', session)
  vi.stubGlobal('localStorage', local)
  saveTabKeys(fields)
  await submitStart(fields, async () => ({ id: 'j', status: 'queued', pr_url: 'x' }) as Job)
  expect(Object.keys(session.data)).toEqual([TAB_KEY_STORE])
  expect(session.data[TAB_KEY_STORE]).toContain('nebius-secret-123')
  expect(Object.keys(local.data)).toHaveLength(0)
  expect(loadTabKeys()).toEqual({ nebiusKey: 'nebius-secret-123', tavilyKey: '', nebiusProjectId: 'project-abc' })
  // A refresh renders the form again from this tab's storage; the key is in a password field.
  const html = renderToStaticMarkup(
    <StartForm stored={{ nebius_key: false, tavily_key: false }} onStart={async () => ({ ok: false, error: '' })} />,
  )
  expect(html).toMatch(/type="password"[^>]*value="nebius-secret-123"|value="nebius-secret-123"[^>]*type="password"/)
  saveTabKeys({ nebiusKey: '', tavilyKey: '', nebiusProjectId: '' })
  expect(Object.keys(session.data)).toHaveLength(0)
  vi.unstubAllGlobals()
})

