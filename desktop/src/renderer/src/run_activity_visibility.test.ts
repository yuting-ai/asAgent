import { describe, expect, it } from 'vitest'

import { splitLiveAndPersistedRunHistory } from './run_activity_visibility'

describe('splitLiveAndPersistedRunHistory', () => {
  it('keeps the current live activity visible after its persisted run appears', () => {
    const activity = { runId: 'run-current', conversationId: 'conversation-browser' }
    const previous = { run: { run_id: 'run-previous' } }
    const current = { run: { run_id: 'run-current' } }

    expect(
      splitLiveAndPersistedRunHistory(activity, 'conversation-browser', [previous, current])
    ).toEqual({
      liveActivity: activity,
      persistedHistory: [previous]
    })
  })

  it('leaves history untouched when the live activity belongs to another conversation', () => {
    const history = [{ run: { run_id: 'run-current' } }]

    expect(
      splitLiveAndPersistedRunHistory(
        { runId: 'run-current', conversationId: 'conversation-other' },
        'conversation-browser',
        history
      )
    ).toEqual({
      liveActivity: null,
      persistedHistory: history
    })
  })
})
