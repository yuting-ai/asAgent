import { describe, expect, it } from 'vitest'

import { detectProviderPreset, getProviderPreset, MODEL_PROVIDER_PRESETS } from './model_presets'

describe('model_presets', () => {
  it('defines all expected presets with valid configurations', () => {
    expect(MODEL_PROVIDER_PRESETS.length).toBeGreaterThanOrEqual(7)
    const deepseek = getProviderPreset('deepseek')
    expect(deepseek.name).toBe('DeepSeek')
    expect(deepseek.location).toBe('external')
    expect(deepseek.defaultBaseUrl).toBe('https://api.deepseek.com')

    const ollama = getProviderPreset('ollama')
    expect(ollama.name).toBe('Ollama (Local)')
    expect(ollama.location).toBe('local')
    expect(ollama.defaultBaseUrl).toBe('http://127.0.0.1:11434/v1')
  })

  it('falls back to default preset for unknown preset id', () => {
    const fallback = getProviderPreset('unknown-provider')
    expect(fallback.id).toBe('deepseek')
  })

  it('detects known provider presets by Base URL', () => {
    expect(detectProviderPreset('https://api.deepseek.com', 'external')).toBe('deepseek')
    expect(detectProviderPreset('https://api.deepseek.com/v1', 'external')).toBe('deepseek')
    expect(detectProviderPreset('https://api.deepseek.com/', 'external')).toBe('deepseek')
    expect(detectProviderPreset('https://api.openai.com/v1', 'external')).toBe('openai')
    expect(detectProviderPreset('http://127.0.0.1:11434/v1', 'local')).toBe('ollama')
    expect(detectProviderPreset('http://127.0.0.1:1234/v1', 'local')).toBe('lmstudio')
    expect(detectProviderPreset('https://openrouter.ai/api/v1', 'external')).toBe('openrouter')
    expect(detectProviderPreset('https://api.siliconflow.cn/v1', 'external')).toBe('siliconflow')
  })

  it('classifies unknown base URLs as custom', () => {
    expect(detectProviderPreset('https://custom-proxy.internal.net/v1', 'external')).toBe('custom')
    expect(detectProviderPreset('http://192.168.1.50:8000/v1', 'local')).toBe('custom')
  })

  it('defaults to sensible presets when base URL is empty or null', () => {
    expect(detectProviderPreset('', 'local')).toBe('ollama')
    expect(detectProviderPreset(null, 'local')).toBe('ollama')
    expect(detectProviderPreset('', 'external')).toBe('deepseek')
    expect(detectProviderPreset(null, 'external')).toBe('deepseek')
    expect(detectProviderPreset(null, null)).toBe('deepseek')
  })
})
