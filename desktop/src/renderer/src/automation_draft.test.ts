import { describe, expect, it } from 'vitest'

import {
  findSavedAutomation,
  isAwaitingAutomationInput,
  plannerNeedsInputAfterRun
} from './automation_draft'

const existing = {
  automation_id: 'automation-existing',
  updated_at: '2026-08-29T01:00:00Z'
}

describe('findSavedAutomation', () => {
  it('selects only a newly allocated id for a new draft', () => {
    const newAutomation = {
      automation_id: 'automation-new',
      updated_at: '2026-08-29T02:00:00Z'
    }
    const result = findSavedAutomation(
      [{ ...existing, updated_at: '2026-08-29T03:00:00Z' }, newAutomation],
      new Map([[existing.automation_id, existing.updated_at]]),
      null
    )

    expect(result).toEqual(newAutomation)
  })

  it('selects only the explicitly bound edit target', () => {
    const updatedTarget = { ...existing, updated_at: '2026-08-29T03:00:00Z' }
    const result = findSavedAutomation(
      [{ automation_id: 'automation-other', updated_at: '2026-08-29T04:00:00Z' }, updatedTarget],
      new Map([
        [existing.automation_id, existing.updated_at],
        ['automation-other', '2026-08-29T01:00:00Z']
      ]),
      existing.automation_id
    )

    expect(result).toEqual(updatedTarget)
  })

  it('does not report a save when the expected stable id did not change', () => {
    const result = findSavedAutomation(
      [existing],
      new Map([[existing.automation_id, existing.updated_at]]),
      existing.automation_id
    )

    expect(result).toBeUndefined()
  })
})

describe('isAwaitingAutomationInput', () => {
  it('shows an input-needed state after an agent follow-up question', () => {
    expect(isAwaitingAutomationInput(true, false, true)).toBe(true)
  })

  it('does not show the state while planning or after a user reply', () => {
    expect(isAwaitingAutomationInput(true, true, true)).toBe(false)
    expect(isAwaitingAutomationInput(true, false, false)).toBe(false)
  })
})

describe('plannerNeedsInputAfterRun', () => {
  it('requires a reply only after a completed planner run that did not save', () => {
    expect(plannerNeedsInputAfterRun('completed', false, 'assistant')).toBe(true)
    expect(plannerNeedsInputAfterRun('completed', true, 'assistant')).toBe(false)
    expect(plannerNeedsInputAfterRun('failed', false, 'assistant')).toBe(false)
    expect(plannerNeedsInputAfterRun('completed', false, 'user')).toBe(false)
  })
})
