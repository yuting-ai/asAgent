export type ModelProviderPreset = {
  id: string
  name: string
  location: 'local' | 'external'
  defaultBaseUrl: string
  placeholderModel: string
  description: string
  descriptionZh?: string
}

export const MODEL_PROVIDER_PRESETS: ModelProviderPreset[] = [
  {
    id: 'deepseek',
    name: 'DeepSeek',
    location: 'external',
    defaultBaseUrl: 'https://api.deepseek.com',
    placeholderModel: 'deepseek-chat',
    description: 'DeepSeek official OpenAI-compatible API.',
    descriptionZh: 'DeepSeek 官方 OpenAI 兼容 API 接口。'
  },
  {
    id: 'openai',
    name: 'OpenAI',
    location: 'external',
    defaultBaseUrl: 'https://api.openai.com/v1',
    placeholderModel: 'gpt-4o',
    description: 'OpenAI official API endpoint.',
    descriptionZh: 'OpenAI 官方 API 接口服务。'
  },
  {
    id: 'ollama',
    name: 'Ollama (Local)',
    location: 'local',
    defaultBaseUrl: 'http://127.0.0.1:11434/v1',
    placeholderModel: 'qwen2.5:7b',
    description: 'Local Ollama server running on your machine.',
    descriptionZh: '运行在您电脑本地的 Ollama 服务。'
  },
  {
    id: 'lmstudio',
    name: 'LM Studio (Local)',
    location: 'local',
    defaultBaseUrl: 'http://127.0.0.1:1234/v1',
    placeholderModel: 'local-model',
    description: 'Local LM Studio OpenAI-compatible server.',
    descriptionZh: '运行在您电脑本地的 LM Studio 服务。'
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    location: 'external',
    defaultBaseUrl: 'https://openrouter.ai/api/v1',
    placeholderModel: 'deepseek/deepseek-chat',
    description: 'Unified gateway for multiple model providers.',
    descriptionZh: '多模型统一聚合与路由网关。'
  },
  {
    id: 'siliconflow',
    name: 'SiliconFlow (硅基流动)',
    location: 'external',
    defaultBaseUrl: 'https://api.siliconflow.cn/v1',
    placeholderModel: 'deepseek-ai/DeepSeek-V3',
    description: 'High-speed cloud inference platform.',
    descriptionZh: '高并发云端模型推理服务平台。'
  },
  {
    id: 'custom',
    name: 'Custom / Other',
    location: 'external',
    defaultBaseUrl: '',
    placeholderModel: 'custom-model',
    description: 'Any custom OpenAI-compatible endpoint.',
    descriptionZh: '任意自定义 OpenAI 兼容接口地址。'
  }
]

export function getProviderPreset(presetId: string): ModelProviderPreset {
  const found = MODEL_PROVIDER_PRESETS.find((preset) => preset.id === presetId)
  return found ?? MODEL_PROVIDER_PRESETS[0]
}

export function getProviderPresetDescription(presetId: string, lang: 'en' | 'zh-Hans'): string {
  const preset = getProviderPreset(presetId)
  if (lang === 'zh-Hans' && preset.descriptionZh) {
    return preset.descriptionZh
  }
  return preset.description
}

function normalizeUrl(url: string): string {
  return url.trim().toLowerCase().replace(/\/+$/, '')
}

export function detectProviderPreset(
  baseUrl: string | null,
  location: 'local' | 'external' | null
): string {
  if (baseUrl === null || baseUrl.trim() === '') {
    return location === 'local' ? 'ollama' : 'deepseek'
  }

  const normalized = normalizeUrl(baseUrl)

  for (const preset of MODEL_PROVIDER_PRESETS) {
    if (preset.id === 'custom') {
      continue
    }
    const presetUrl = normalizeUrl(preset.defaultBaseUrl)
    if (
      normalized === presetUrl ||
      (preset.id === 'deepseek' && normalized === 'https://api.deepseek.com/v1')
    ) {
      return preset.id
    }
  }

  return 'custom'
}
