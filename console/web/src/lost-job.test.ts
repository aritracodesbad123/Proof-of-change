import { expect, test } from 'vitest'
import { ApiError, lostJobMessage } from './api'

test('a missing job says the server restarted', () => {
  expect(lostJobMessage(new ApiError('not found', 404))).toBe(
    'This check was lost because the server restarted. Please start it again.',
  )
  expect(lostJobMessage(new ApiError('nope', 500))).toBeNull()
  expect(lostJobMessage(new Error('not found'))).toBeNull()
})
