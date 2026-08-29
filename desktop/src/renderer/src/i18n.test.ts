import { describe, expect, it } from 'vitest'

import { getStoredAppLanguage, t, TRANSLATIONS } from './i18n'

describe('i18n', () => {
  it('contains matching keys in English and Chinese dictionaries', () => {
    const enKeys = Object.keys(TRANSLATIONS.en)
    const zhKeys = Object.keys(TRANSLATIONS['zh-Hans'])

    expect(enKeys.length).toBeGreaterThan(30)
    expect(zhKeys.length).toBe(enKeys.length)
    expect(zhKeys.sort()).toEqual(enKeys.sort())
  })

  it('translates known keys correctly according to language', () => {
    expect(t('en', 'newChat')).toBe('New chat')
    expect(t('zh-Hans', 'newChat')).toBe('新建对话')

    expect(t('en', 'settings')).toBe('Settings')
    expect(t('zh-Hans', 'settings')).toBe('设置')

    expect(t('en', 'browserAssistant')).toBe('Browser Assistant')
    expect(t('zh-Hans', 'browserAssistant')).toBe('浏览器助手')

    expect(t('en', 'newScheduledTask')).toBe('New scheduled task')
    expect(t('zh-Hans', 'newScheduledTask')).toBe('新建定时任务')
    expect(t('en', 'planningScheduledTask')).toBe('Planning…')
    expect(t('zh-Hans', 'planningScheduledTask')).toBe('规划中…')
    expect(t('en', 'needsYourInput')).toBe('Needs your input')
    expect(t('zh-Hans', 'needsYourInput')).toBe('需要你的补充')
    expect(t('en', 'savedScheduledTask')).toBe('Saved scheduled task')
    expect(t('zh-Hans', 'savedScheduledTask')).toBe('已保存定时任务')
  })

  it('defaults to english when given unknown language', () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(t('fr' as any, 'newChat')).toBe('New chat')
  })

  it('reads stored language or defaults to English', () => {
    expect(getStoredAppLanguage()).toBe('en')
  })
})
