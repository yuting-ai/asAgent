import { describe, expect, it } from 'vitest'

import { TOOL_APPROVAL_BANNER_ACTIONS } from './tool_approval'

describe('tool approval banner actions', () => {
  it('maps the three renderer operations to API decisions', () => {
    expect(TOOL_APPROVAL_BANNER_ACTIONS.map((action) => action.decision)).toEqual([
      'deny',
      'allow_conversation',
      'allow_once'
    ])
  })
})
