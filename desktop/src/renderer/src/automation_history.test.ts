import { afterEach, describe, expect, it, vi } from 'vitest'

import { startAutomationHistoryPolling } from './automation_history'

afterEach(() => {
  vi.useRealTimers()
})

describe('startAutomationHistoryPolling', () => {
  it('refreshes after the interval and waits for completion before scheduling again', async () => {
    vi.useFakeTimers()
    let finishRefresh = (): void => {
      throw new Error('Refresh did not start.')
    }
    const refresh = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          finishRefresh = resolve
        })
    )
    const stop = startAutomationHistoryPolling(refresh, 5_000)

    await vi.advanceTimersByTimeAsync(5_000)
    expect(refresh).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(10_000)
    expect(refresh).toHaveBeenCalledTimes(1)

    finishRefresh()
    await vi.advanceTimersByTimeAsync(5_000)
    expect(refresh).toHaveBeenCalledTimes(2)
    stop()
  })

  it('retries after a failed refresh and stops cleanly', async () => {
    vi.useFakeTimers()
    const refresh = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue(undefined)
    const stop = startAutomationHistoryPolling(refresh, 1_000)

    await vi.advanceTimersByTimeAsync(2_000)
    expect(refresh).toHaveBeenCalledTimes(2)

    stop()
    await vi.advanceTimersByTimeAsync(5_000)
    expect(refresh).toHaveBeenCalledTimes(2)
  })
})
