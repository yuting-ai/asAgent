export type AppLanguage = 'en' | 'zh-Hans'

export const LANGUAGE_STORAGE_KEY = 'asagent:app_language'

export function getStoredAppLanguage(): AppLanguage {
  try {
    const saved = window.localStorage.getItem(LANGUAGE_STORAGE_KEY)
    if (saved === 'zh-Hans' || saved === 'en') {
      return saved
    }
  } catch {
    // Ignore storage read error
  }
  return 'en'
}

export const TRANSLATIONS = {
  en: {
    // Rail
    newChat: 'New chat',
    newBrowser: 'New browser',
    recents: 'Recents',
    noRecents: 'No recent conversations yet.',
    settings: 'Settings',
    collapseSidebar: 'Collapse sidebar',
    expandSidebar: 'Expand sidebar',
    running: 'running',
    activeRunDot: '1 running',
    rename: 'Rename',
    delete: 'Delete',
    cancel: 'Cancel',
    save: 'Save',
    deleteConversationConfirm: 'Delete this conversation? This cannot be undone.',

    // Chat View
    chatTitle: 'Chat',
    newConversation: 'New conversation',
    emptyGreetingTitle: 'How can I help you today?',
    emptyGreetingSub: 'Ask anything, explore ideas, or attach files and folders to collaborate.',
    composerPlaceholder: 'Message asAgent… (Shift+Enter for newline)',
    composerPlaceholderEmpty: 'Type a message to start… (Shift+Enter for newline)',
    webSearch: 'Web search',
    webSearchEnabled: 'Web search enabled',
    webSearchDisabled: 'Web search disabled',
    attachFileOrFolder: 'Attach files or folders',
    attachFolder: 'Attach folder',
    attachFile: 'Attach file',
    workspaceAttached: 'Workspace attached',
    noModelConfigured: 'No model configured',
    configureInSettings: 'Configure in Settings',
    stopGenerating: 'Stop',
    approve: 'Approve',
    deny: 'Deny',
    alwaysAllow: 'Always allow',
    approvalsTitle: 'Approvals',
    todayTitle: 'Today',
    activityTitle: 'Activity',
    activitySubtitle: 'Everything your agent has done, is doing, or is about to do.',
    noActivityYet: 'No run activity yet.',

    // Browser View
    browserTitle: 'Browser',
    newTab: 'New Tab',
    searchOrAddressPlaceholder: 'Search Google or enter a web address',
    back: 'Back',
    forward: 'Forward',
    reload: 'Reload',
    home: 'Home',
    closeTab: 'Close tab',
    browserAssistant: 'Browser Assistant',
    browserAssistantEmpty: 'Ask about this page or ask the agent to help you navigate.',
    askPagePlaceholder: 'Ask about this page… (Shift+Enter for newline)',
    toggleBrowserAgent: 'Toggle assistant panel',
    openInNewTab: 'Open in new tab',

    // Settings View
    settingsTitle: 'General',
    settingsSub: 'Manage model access, agent runtime, tools, and local storage.',
    generalCategory: 'General',
    languageSectionTitle: 'Language',
    languageSectionCopy: 'Select the display language for the user interface.',
    interfaceLanguageLabel: 'Interface language',
    languageEnglish: 'English',
    languageChinese: '中文 (Chinese)',

    modelPrivacyCategory: 'Model & privacy',
    modelProviderTitle: 'Model provider',
    modelProviderCopy:
      'Connect any OpenAI-compatible local server or external provider. API keys stay in your system credential store and are never shown here.',
    modelLocationLocal: 'Local model server',
    modelLocationLocalDesc: 'Ollama, LM Studio, or any local OpenAI-compatible endpoint.',
    modelLocationExternal: 'External API provider',
    modelLocationExternalDesc: 'DeepSeek, OpenAI, OpenRouter, SiliconFlow, or custom endpoint.',
    providerPreset: 'Provider preset',
    modelName: 'Model name',
    baseUrl: 'Base URL',
    apiKey: 'API Key',
    apiKeyPlaceholder: 'Enter API key (leave empty to keep current key)',
    saveModelSettings: 'Save model settings',
    configuredBadge: 'Configured',
    activeBadge: 'Active',
    needsAttentionBadge: 'Needs attention',
    notConfiguredBadge: 'Not configured',

    agentRuntimeCategory: 'Agent runtime',
    maxAgentStepsTitle: 'Maximum agent steps per request',
    maxAgentStepsCopy:
      'A step is one model decision. Higher limits can take longer and use more model tokens.',
    maxAgentStepsLabel: 'Steps (1–50)',
    saveAgentSettings: 'Save agent settings',

    connectedToolCategory: 'Connected tool',
    tavilySearchTitle: 'Tavily Web Search',
    tavilySearchCopy:
      'Tavily lets asAgent search the web through a configured MCP server. Your API key is stored securely.',
    tavilyEnabledStatus: 'Tavily web search is enabled.',
    tavilyDisabledStatus: 'Tavily is disabled. Your API key is still saved.',
    tavilyNotConfiguredStatus: 'Tavily is not configured.',
    changeApiKey: 'Change API key',
    removeSavedApiKey: 'Remove saved API key',
    saveApiKey: 'Save API key',

    dataSpaceCategory: 'Data & Space',
    storageSnapshotsTitle: 'Storage & Snapshots',
    storageSnapshotsCopy:
      'Manage undo snapshots for reversible file edits and deletions. Automatic cleanup purges older snapshots to keep disk space lean.',
    currentSnapshotUsage: 'Current snapshot usage',
    clearAllSnapshotsNow: 'Clear all snapshots now',

    // Modals & Notices
    restartNoticeTitle: 'Settings saved',
    restartNoticeBody: 'asAgent needs to restart to apply the new settings.',
    restartNow: 'Restart now',
    restartLater: 'Later'
  },
  'zh-Hans': {
    // Rail
    newChat: '新建对话',
    newBrowser: '新建浏览器',
    recents: '最近记录',
    noRecents: '暂无最近对话',
    settings: '设置',
    collapseSidebar: '折叠侧边栏',
    expandSidebar: '展开侧边栏',
    running: '运行中',
    activeRunDot: '1 个运行中',
    rename: '重命名',
    delete: '删除',
    cancel: '取消',
    save: '保存',
    deleteConversationConfirm: '确定要删除此对话吗？此操作无法撤销。',

    // Chat View
    chatTitle: '对话',
    newConversation: '新对话',
    emptyGreetingTitle: '今天我能为你做些什么？',
    emptyGreetingSub: '随时提问、探索灵感，或关联文件与目录进行深入协作。',
    composerPlaceholder: '给 asAgent 发送消息… (Shift+Enter 换行)',
    composerPlaceholderEmpty: '输入消息开始对话… (Shift+Enter 换行)',
    webSearch: '联网搜索',
    webSearchEnabled: '联网搜索已开启',
    webSearchDisabled: '联网搜索已关闭',
    attachFileOrFolder: '关联文件或目录',
    attachFolder: '关联目录',
    attachFile: '关联文件',
    workspaceAttached: '工作区已关联',
    noModelConfigured: '未配置模型',
    configureInSettings: '前往设置配置',
    stopGenerating: '停止生成',
    approve: '批准',
    deny: '拒绝',
    alwaysAllow: '始终允许',
    approvalsTitle: '操作审批',
    todayTitle: '今日动态',
    activityTitle: '活动记录',
    activitySubtitle: 'Agent 已执行、正在执行和准备执行的所有动作。',
    noActivityYet: '暂无活动记录。',

    // Browser View
    browserTitle: '浏览器',
    newTab: '新标签页',
    searchOrAddressPlaceholder: '在 Google 中搜索或输入网址',
    back: '后退',
    forward: '前进',
    reload: '刷新',
    home: '主页',
    closeTab: '关闭标签页',
    browserAssistant: '浏览器助手',
    browserAssistantEmpty: '关于当前页面提问，或让 Agent 协助你浏览操作。',
    askPagePlaceholder: '关于此页面提问… (Shift+Enter 换行)',
    toggleBrowserAgent: '切换助手面板',
    openInNewTab: '在新标签页中打开',

    // Settings View
    settingsTitle: '设置',
    settingsSub: '管理模型连接、Agent 运行时、联网工具和本地存储。',
    generalCategory: '常规设置',
    languageSectionTitle: '语言',
    languageSectionCopy: '选择软件界面的显示语言。',
    interfaceLanguageLabel: '界面语言',
    languageEnglish: 'English',
    languageChinese: '中文 (Chinese)',

    modelPrivacyCategory: '模型与隐私',
    modelProviderTitle: '模型提供商',
    modelProviderCopy:
      '连接任意兼容 OpenAI 接口的本地模型服务或外部 API。API Key 安全保存在系统钥匙串中，绝不会明文展示。',
    modelLocationLocal: '本地模型服务',
    modelLocationLocalDesc: 'Ollama、LM Studio 或任意本地兼容 OpenAI 协议的接口。',
    modelLocationExternal: '外部 API 提供商',
    modelLocationExternalDesc:
      'DeepSeek、OpenAI、OpenRouter、硅基流动 (SiliconFlow) 或自定义 API。',
    providerPreset: '提供商预设',
    modelName: '模型名称',
    baseUrl: '接口地址 (Base URL)',
    apiKey: 'API 密钥 (API Key)',
    apiKeyPlaceholder: '输入 API 密钥（留空则保持当前密钥不变）',
    saveModelSettings: '保存模型设置',
    configuredBadge: '已配置',
    activeBadge: '已激活',
    needsAttentionBadge: '需关注',
    notConfiguredBadge: '未配置',

    agentRuntimeCategory: 'Agent 运行时',
    maxAgentStepsTitle: '单次请求最大决策步数',
    maxAgentStepsCopy: '一个步骤代表一次模型决策。更高的上限可能耗费更多时间和 Token。',
    maxAgentStepsLabel: '步数上限 (1–50)',
    saveAgentSettings: '保存运行时设置',

    connectedToolCategory: '关联工具',
    tavilySearchTitle: 'Tavily 联网搜索',
    tavilySearchCopy:
      'Tavily 支持 asAgent 通过 MCP 协议检索互联网实时信息。API 密钥已安全加密存储。',
    tavilyEnabledStatus: 'Tavily 联网搜索已开启。',
    tavilyDisabledStatus: 'Tavily 已禁用。你的 API 密钥仍安全保存。',
    tavilyNotConfiguredStatus: 'Tavily 尚未配置。',
    changeApiKey: '更换 API 密钥',
    removeSavedApiKey: '移除保存的密钥',
    saveApiKey: '保存 API 密钥',

    dataSpaceCategory: '数据与存储',
    storageSnapshotsTitle: '存储与快照',
    storageSnapshotsCopy: '管理文件编辑与删除的可逆撤销快照。系统会自动清理旧快照以保持磁盘精简。',
    currentSnapshotUsage: '当前快照占用空间',
    clearAllSnapshotsNow: '立即清空所有快照',

    // Modals & Notices
    restartNoticeTitle: '设置已保存',
    restartNoticeBody: 'asAgent 需要重启以应用新的配置。',
    restartNow: '立即重启',
    restartLater: '稍后重启'
  }
} as const

export type TranslationKey = keyof (typeof TRANSLATIONS)['en']

export function t(lang: AppLanguage, key: TranslationKey): string {
  const dictionary = TRANSLATIONS[lang] ?? TRANSLATIONS['en']
  return dictionary[key] ?? TRANSLATIONS['en'][key] ?? key
}
