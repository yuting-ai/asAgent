export const AUTOMATION_HISTORY_REFRESH_INTERVAL_MS = 5_000

export function startAutomationHistoryPolling(
  refresh: () => Promise<void>,
  intervalMs = AUTOMATION_HISTORY_REFRESH_INTERVAL_MS
): () => void {
  if (intervalMs <= 0) throw new Error('Automation history refresh interval must be positive.')

  let stopped = false
  let timer: ReturnType<typeof setTimeout> | null = null

  const schedule = (): void => {
    timer = setTimeout(() => {
      void poll()
    }, intervalMs)
  }

  const poll = async (): Promise<void> => {
    try {
      await refresh()
    } catch {
      // Keep the last visible snapshot and retry after the next interval.
    } finally {
      if (!stopped) schedule()
    }
  }

  schedule()
  return () => {
    stopped = true
    if (timer !== null) clearTimeout(timer)
  }
}
