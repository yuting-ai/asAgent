<div align="center">

# asAgent

**一个将对话转化为可见、可控行动的桌面 AI Agent。**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[English](README.md) • **简体中文**

[📥 下载安装](#下载与安装-download--installation) • [▶ 观看产品演示](#演示) • [快速开始](#快速开始) • [核心能力](#核心能力) • [项目状态](#项目状态与路线图)

</div>

---

asAgent 将对话、浏览器辅助、定时任务和可撤回文件操作集中在一个桌面应用中。会话与应用状态默认保存在你的电脑上；当你选择外部模型或联网工具时，只有完成该次请求所需的数据会发送给已配置的服务。

> asAgent 仍在持续开发中，目前需要从源码运行，尚未成为可正式发布的桌面产品。

## 演示

<p align="center">
  <video src="https://github.com/user-attachments/assets/a0c0ef10-a6af-4939-a4dc-80879d4b844e" controls muted playsinline width="720">
    你的浏览器无法播放此视频。
    <a href="https://github.com/user-attachments/assets/a0c0ef10-a6af-4939-a4dc-80879d4b844e">打开产品演示 →</a>
  </video>
</p>

## 你可以用它做什么

- 与兼容 OpenAI 接口的模型对话，并查看每次运行过程。
- 让 Agent 在可见浏览器中读取网页并执行交互。
- 创建单次、每日和每周自动化任务。
- 在授权范围内读取和修改文件，并通过快照与恢复机制降低风险。

asAgent 当前没有接入遥测服务。外部模型服务商、Tavily 和用户配置的其他 MCP Server 仍可能接收完成相应操作所需的数据。

---

## 核心能力

### 1. 多轮对话与上下文管理

- **认证 RunEvent 实时流：** 桌面端通过 Bearer 认证的 SSE 观察持久化 `RunEvent`。当前 Agent Loop 使用非流式模型调用，因此 Assistant 正文会在 Run 完成后显示，而不是逐 Token 输出。
- **Run Activity：** 可折叠卡片展示安全的步骤、工具、状态、耗时和脱敏错误元数据；不展示模型思维链、工具参数或完整工具结果。
- **上下文预算：** 确定性的 Token 估算器与 Context Builder 在输入预算内保留最近的完整会话/工具单元。
- **持久化历史：** Chat 与 Browser Conversation、用户可见 Message、Run 状态和安全事件可在应用重启后恢复。

### 2. 会话级工作区与可撤回文件变更

- **范围隔离：** 每个 Chat Conversation 默认拥有自己的 asAgent Workspace，并可额外授权文件夹或单个文件；真实路径解析阻止 `..` 和符号链接逃逸。
- **只读工具：** `filesystem.list`、`filesystem.read_file` 和 `filesystem.search_files` 只能访问当前会话已授权范围。
- **写入工具：** `filesystem.create_file`、`filesystem.replace_file` 和 `filesystem.delete_file` 当前在用户已明确授权的路径范围内免逐次审批执行。Create/Replace 接收完整 UTF-8 文件正文；目前没有行级编辑工具。
- **Undo 安全机制：** SQLite 保存 FileChange 元数据和哈希，变更前快照正文保存在应用数据目录的私有文件中。快照是完整的变更前字节，不是 SQLite diff；当前单项上限为 20 MiB、总量上限为 200 MiB，并支持保留周期设置与手动清理。
- **更安全的删除：** 删除文件会移动到系统废纸篓；存在私有快照时，对话中还会提供带冲突校验的 Undo。
- **工作区检查器：** 桌面端提供目录树、有限文本预览、刷新、在 Finder 中显示，以及引用到输入框/对话的操作。

### 3. 可见 Browser 助手与隔离的自动化浏览器

- **可见 Browser Conversation：** Electron 独占持久化 `WebContentsView` Session，网页凭据、Cookie、DOM Selector 和 Storage 不进入 Python 或 Renderer。
- **页面工具：** 绑定标签页的 Browser Run 可使用 `browser.navigate`、`browser.read_current_page`、`browser.take_snapshot`、`browser.click`、`browser.fill`、`browser.select` 和 `browser.wait`。
- **语义快照：** `browser.take_snapshot` 返回有界的 `ref`、名称、角色、标签、禁用状态和原生 Select Options，不暴露完整 HTML 或 CSS Selector。
- **页面助手：** 右侧面板可以讨论当前网页，并在绑定标签页中执行用户可见的交互。
- **后台隔离：** Scheduled task 使用独立 Profile 的 Playwright-over-CDP 自动化服务。该能力要求系统安装 Google Chrome、Microsoft Edge 或 Chromium 等受支持浏览器。

### 4. 定时任务

- **对话式规划：** 短生命周期且隔离的草案 Conversation 用于创建或调整任务，不会把草案消息加入普通 Recents。
- **已支持的周期：** Trigger 当前支持带 IANA 时区的 `once`、`daily` 和 `weekly`；尚不支持任意 Cron 表达式。
- **管理与历史：** 可以创建、编辑、启用、暂停、删除或手动运行任务；Execution History 保存状态、时间、耗时和最终用户可见消息。
- **过期任务保护：** 启动恢复时会跳过过期的周期事件，避免休眠恢复后出现集中补跑风暴。
- **可选计划修正：** Automation Run 中，模型可以调用 `automation.update_plan` 保存已经实际验证成功的修正方案。这是工具引导的行为，不保证每次网页故障都一定能够自动修复。

### 5. MCP 与联网搜索

- **MCP stdio Client：** asAgent 支持现代 MCP 发现流程及隔离的旧协议回退；导入工具会被命名空间化，经过 Schema、权限和审批策略，并以原子方式加入 Registry。
- **启动时固定工具集：** MCP Server 在 Python Sidecar 启动时加载。配置变化需要重启；热刷新、通知和分页工具发现尚未实现。
- **可选 Tavily 搜索：** Tavily 作为受限的 stdio MCP Server 配置。API Key 保存在 macOS Keychain，并只注入该 Server 子进程。Tavily 不是内置 Search Tool，用户配置前默认不可用。

---

## 架构与安全

```text
┌─────────────────────────────────────────────────────────────┐
│ Electron Renderer                                           │
│ React 19 · TypeScript · 仅使用具名 Preload 能力             │
└──────────────────────────────┬──────────────────────────────┘
                               │ 经过校验的 IPC
┌──────────────────────────────▼──────────────────────────────┐
│ Electron Main                                               │
│ 后端生命周期 · Token · 原生对话框 · 浏览器视图             │
└──────────────────────────────┬──────────────────────────────┘
                               │ 回环 HTTP + 认证 SSE
                               │ Bearer Token · 127.0.0.1:0
┌──────────────────────────────▼──────────────────────────────┐
│ FastAPI Local API                                           │
├─────────────────────────────────────────────────────────────┤
│ Agent Runtime · Context Builder · Model · Tool · Scheduler  │
├─────────────────────────────────────────────────────────────┤
│ SQLite · Workspace · 私有快照 · macOS Keychain             │
└─────────────────────────────────────────────────────────────┘
```

- Backend 自行绑定随机回环端口，并通过结构化 Ready Record 报告实际端点。
- Electron Main 每次启动生成新的 Token，经子进程 stdin 发送；Token 不进入命令行参数、URL、Renderer Storage 或普通日志。
- Main 解析认证 SSE，只向受信任 Renderer 暴露结构化 Run 更新。
- 模型 API Key 与 Tavily Credential 当前保存在 macOS Keychain。
- 产品默认使用单个本地用户 `local-user`，但领域与持久化边界仍保留 `user_id`。

---

## 快速开始

### 环境要求

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- Node.js `>=20.19.0` 或 `>=22.12.0`
- npm
- 后台网页自动化可选依赖：Google Chrome、Microsoft Edge 或 Chromium

### 1. 克隆并安装依赖

```bash
git clone https://github.com/yuting-ai/asAgent.git
cd asAgent

uv sync --locked
npm --prefix desktop ci
```

### 2. 启动桌面开发环境

```bash
npm --prefix desktop run dev
```

默认开发模式使用确定性的离线 Model/Tool Runtime，不需要 API Key。需要真实模型回答时，可在 **设置 → 模型与隐私** 中配置本地或外部 OpenAI-compatible 模型；保存后的设置在 Sidecar 重启后生效。

旧的 `dev:deepseek` 开发入口还要求所选 App Home 中存在对应的非敏感 `deepseek` Profile；仅设置 API Key 环境变量并不能让全新 Clone 直接运行该入口。

### 3. 测试与质量保证

```bash
# Python 测试（当前收集 530 个测试）
uv run pytest

# Python Lint、格式检查、strict mypy、锁文件和 diff 检查
scripts/check.sh

# Desktop 类型检查、Lint 和测试（当前 133 个测试）
npm --prefix desktop run typecheck
npm --prefix desktop run lint
npm --prefix desktop test
```

Docker 当前只用于干净 Linux 测试和 CI，不是桌面运行依赖，也不是已支持的 Server 部署方式：

```bash
docker build --file docker/Dockerfile.test --tag asagent-tests:local .
docker run --rm asagent-tests:local
```

### 4. 当前构建状态

Python Sidecar 可以独立构建并进行自动化冒烟测试：

```bash
uv run python scripts/build_backend.py
uv run python scripts/smoke_backend_bundle.py
```

Renderer/Main/Preload 的生产构建可以通过以下命令检查：

```bash
npm --prefix desktop run build
```

现有 `build:mac`、`build:win` 和 `build:linux` 仍属于开发脚手架：它们尚未把 PyInstaller Sidecar 组装进可发布的 asAgent 安装包，打包后的 Launcher 也尚未切换到正式可执行文件路径。代码签名、公证、跨平台 Credential Store、更新发布和干净机器安装验证仍未完成。

---

## 模型服务商与配置

Settings 当前提供以下 OpenAI-compatible Preset。DeepSeek 是端到端开发验证的主要外部模型；其他条目代表兼容性预设，不表示每种模型与 Endpoint 组合均已完成充分测试。

| 服务商 | 位置 | 默认 Base URL | 当前状态 |
| :--- | :--- | :--- | :--- |
| DeepSeek | 外部 | `https://api.deepseek.com` | 主要实测外部 Provider |
| OpenAI | 外部 | `https://api.openai.com/v1` | 兼容性预设 |
| Ollama | 本地 | `http://127.0.0.1:11434/v1` | 兼容性预设 |
| LM Studio | 本地 | `http://127.0.0.1:1234/v1` | 兼容性预设 |
| OpenRouter | 外部 | `https://openrouter.ai/api/v1` | 兼容性预设 |
| SiliconFlow | 外部 | `https://api.siliconflow.cn/v1` | 兼容性预设 |
| Custom | 本地或外部 | 用户自定义 | 仅限 OpenAI-compatible Endpoint |

本地 Endpoint 可以不设置 API Key；外部 Endpoint 必须保存 Key。当前 macOS 实现将 Key 保存在 Keychain，并且永不把 Key 回传给 Renderer。

---

## 项目状态与路线图

### 已实现

- [x] Provider-neutral Core 合同与 OpenAI-compatible Model Adapter
- [x] 非流式 Agent Loop，以及工具 Schema、权限、审批 Gate、超时、取消检查点和安全 RunEvent
- [x] Conversation、Message、Run、Event、ToolCall、FileChange、Connection 和 Scheduled task 的 SQLite 持久化
- [x] 会话级只读文件工具，以及可撤回的单文件 Create/Replace/Delete 和带冲突保护的 Undo
- [x] 可见 Browser Conversation 与隔离的后台浏览器自动化
- [x] Once/Daily/Weekly Scheduled task、执行历史和可选 `automation.update_plan`
- [x] MCP stdio Client/Manager 与可选 Tavily MCP 配置
- [x] 包含 Chat、Browser、Scheduled task、Settings、工作区检查器和中英双语 UI 的 Electron 开发外壳
- [x] 独立 PyInstaller Sidecar 构建与自动化冒烟测试

### 待完成

- [ ] 桌面 Agent Loop 的 Assistant 正文逐 Token 实时输出
- [ ] Conversation Summary、经用户确认的长期 User Memory、Knowledge 索引和跨会话检索
- [ ] 运行时扫描、选择和加载磁盘上的 `SKILL.md`
- [ ] 多 Agent/Subagent 编排
- [ ] MCP 分页、通知、热刷新和 Streamable HTTP Transport
- [ ] 包含 Sidecar、正式产品元数据、签名/公证、干净机器测试和更新能力的可发布 Electron 安装包
- [ ] 受支持的无头/Docker Server 发行方式

---

## 下载与安装 (Download & Installation)

> [!NOTE]
> 目前预编译安装包仅支持 **Apple 芯片 (Apple Silicon / M 系列芯片，arm64)** 的 Mac 电脑，暂不支持 Intel 芯片。

- 📥 **直接下载**：[点击直接下载最新版 asAgent-arm64.dmg](https://github.com/yuting-ai/asAgent/releases/latest/download/asAgent-arm64.dmg)
- 📦 **发行说明与历史版本**：[GitHub Releases 页面](https://github.com/yuting-ai/asAgent/releases/latest)
- 🔐 **官方签名与公证**：所有官方发布版本均已通过 Apple Developer ID 签名并完成苹果官方公证（Notarization），开箱即用，无系统安全拦截。

---

## 许可证

asAgent 采用 [MIT License](LICENSE) 开源许可证。
