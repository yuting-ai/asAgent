type LiveRunActivity = {
  runId: string
  conversationId: string
}

type PersistedRunHistory = {
  run: {
    run_id: string
  }
}

export function splitLiveAndPersistedRunHistory<
  Activity extends LiveRunActivity,
  History extends PersistedRunHistory
>(
  activity: Activity | null,
  selectedConversationId: string | null,
  history: History[]
): { liveActivity: Activity | null; persistedHistory: History[] } {
  if (activity === null || activity.conversationId !== selectedConversationId) {
    return { liveActivity: null, persistedHistory: history }
  }

  return {
    liveActivity: activity,
    persistedHistory: history.filter((item) => item.run.run_id !== activity.runId)
  }
}
