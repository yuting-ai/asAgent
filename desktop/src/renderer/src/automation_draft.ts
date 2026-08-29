export type VersionedAutomation = {
  automation_id: string
  updated_at: string
}

export function isAwaitingAutomationInput(
  isCreatingTask: boolean,
  isPlanning: boolean,
  plannerFinishedWithoutSave: boolean
): boolean {
  return isCreatingTask && !isPlanning && plannerFinishedWithoutSave
}

export function plannerNeedsInputAfterRun(
  outcome: 'completed' | 'failed' | 'cancelled' | 'limit',
  automationWasSaved: boolean,
  lastMessageRole: 'user' | 'assistant' | null
): boolean {
  return outcome === 'completed' && !automationWasSaved && lastMessageRole === 'assistant'
}

export function findSavedAutomation<T extends VersionedAutomation>(
  automations: readonly T[],
  knownVersions: ReadonlyMap<string, string>,
  targetAutomationId: string | null
): T | undefined {
  if (targetAutomationId === null) {
    return automations.find((automation) => !knownVersions.has(automation.automation_id))
  }

  const target = automations.find((automation) => automation.automation_id === targetAutomationId)
  if (target === undefined || knownVersions.get(target.automation_id) === target.updated_at) {
    return undefined
  }
  return target
}
