import { createElement, type ComponentProps } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { RunActivityCard } from './App'

type Activity = ComponentProps<typeof RunActivityCard>['activity']
const activity: Activity = {
  runId: 'run-1',
  conversationId: 'chat-1',
  phase: 'live',
  outcome: null,
  startedAt: 0,
  endedAt: null,
  steps: [
    { id: 'model:1', label: 'Preparing a response…', detail: null, status: 'completed' },
    { id: 'tool:1', label: 'Reading the page…', detail: null, status: 'running' }
  ]
}
function render(value: Activity, expanded = false): string {
  return renderToStaticMarkup(
    createElement(RunActivityCard, {
      activity: value,
      expanded,
      onExpandedChange: () => undefined
    })
  )
}

describe('compact run activity card', () => {
  it('shows only the current action until details are expanded', () => {
    const html = render(activity)
    expect(html).toContain('Reading the page…')
    expect(html).toContain('aria-expanded="false"')
    expect(html).toContain('role="status"')
    expect(html).not.toContain('activity-list')
    expect(html).not.toContain('Preparing a response…')
  })
  it('shows all steps and a collapse control while running', () => {
    const html = render(activity, true)
    expect(html).toContain('activity-list')
    expect(html).toContain('Preparing a response…')
    expect(html).toContain('Hide details')
    expect(html).toContain('aria-expanded="true"')
  })
  it('keeps approval waiting visible without expanding details', () => {
    expect(
      render({
        ...activity,
        steps: [
          {
            id: 'approval',
            label: 'Waiting for approval: Read file',
            detail: null,
            status: 'waiting'
          }
        ]
      })
    ).toContain('Waiting for approval: Read file')
  })
  it.each(['completed', 'failed', 'cancelled', 'limit'] as const)(
    'preserves the %s terminal summary',
    (outcome) => {
      const value: Activity = { ...activity, phase: 'done', outcome, endedAt: 1000 }
      const html = render(value)
      expect(html).toContain(`outcome-${outcome}`)
      expect(html).not.toContain('activity-spinner')
      expect(html).not.toContain('activity-list')
      expect(render(value, true)).toContain('activity-list')
    }
  )
})
