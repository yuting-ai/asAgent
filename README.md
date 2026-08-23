<div align="center">

# asAgent

**A Private, Local-First, Autonomous Personal AI Assistant & Desktop Agent**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.12+](https://img.shields.io/badge/Python-3.12%2B-teal.svg)](https://www.python.org/)
[![Electron: 39+](https://img.shields.io/badge/Electron-39%2B-47848F.svg)](https://www.electronjs.org/)
[![React: 19](https://img.shields.io/badge/React-19-52C9D1.svg)](https://react.dev/)
[![TypeScript: 5.9](https://img.shields.io/badge/TypeScript-5.9-3178C6.svg)](https://www.typescriptlang.org/)
[![Tests: 660+ Passed](https://img.shields.io/badge/Tests-660%2B%20Passed-brightgreen.svg)](#-testing--quality-assurance)

**English** • [简体中文](README_zh.md)

[Key Features](#-key-features) • [Architecture](#-architecture--security) • [Quickstart](#-quickstart) • [Configuration](#-model-providers--configuration) • [Project Status & Roadmap](#-project-status--roadmap)

</div>

---

## 🌟 Philosophy & Overview

**asAgent** is an open-source, local-first personal AI assistant and autonomous desktop agent. It pairs the reasoning capabilities of Large Language Models (LLMs) with direct, secure, and observable operating system capabilities—while keeping 100% of user data, database records, and credentials stored strictly on the local machine.

* 🔒 **100% Private & Local-First**: Built on SQLite with OS-level credential encryption (macOS Keychain / System Credential Store). No telemetry, no external accounts, zero cloud tracking.
* 🧩 **Provider-Neutral Model Engine**: Connects seamlessly to Ollama, LM Studio, DeepSeek, OpenAI, OpenRouter, SiliconFlow, or any custom OpenAI-compatible endpoint.
* 🛡️ **Human-in-the-Loop Security**: Every sensitive filesystem write and tool execution is guarded by configurable approval policies (Allow Once, Allow for Chat, Always Allow, or Deny) with automatic snapshot undo.
* ⚡ **Neo-Mint Visual Identity**: Modern desktop UI featuring high-contrast WCAG AAA typography, draggable window headers, customizable split panes, and real-time bilingual localization.

---

## 🚀 Key Features

### 1. 💬 Private Multi-Turn Chat & Context Management
* **Real-time SSE Streaming**: Smooth token-by-token streaming over an authenticated local loopback connection.
* **Observable Run Activity**: Collapsible, step-by-step trace cards detailing tool calls, execution statuses, timings, and outputs.
* **Context Budgeting**: Context Builder with token-aware sliding window management to maintain conversation depth while preventing context overflows.
* **Bilingual Localization**: Seamless runtime switching between **English** and **中文 (Simplified Chinese)** without app restarts.

### 2. 📁 Workspace & Reversible File Tools
* **Granular Workspace Confinement**: Controlled tools for `list_dir`, `read_file`, `write_file`, `edit_file` (unified line-level search/replace), and `search_files` with strict symlink escape prevention.
* **Reversible File Snapshots (One-Click Undo)**: Automatic atomic pre-change diff snapshotting in SQLite. Undo cards are injected directly into the chat stream for instant rollback.
* **Integrated File Tree**: Real-time workspace file explorer with inline previewing and one-click quote-into-chat/prompt functionality.

### 3. 🌐 Embedded Autonomous Browser
* **Dual-Browser Isolation**: Clear separation between the interactive user-facing browser view and the autonomous agent automation engine.
* **Deep Web Automation Toolkit**: Native support for `browser.navigate`, `browser.read_current_page` (Markdown DOM extraction with indexed links/buttons), `browser.inspect_interactive`, `browser.click`, `browser.fill`, `browser.select`, and `browser.wait`.
* **Page Assistant Sidebar**: Instant side-panel to ask questions about the current page, summarize content, or direct the agent to complete web tasks.

### 4. ⏰ Scheduled Tasks & Self-Healing Automation Engine
* **Natural Language Task Planning**: Multi-turn interactive canvas to draft and refine recurring task instructions and schedules.
* **Resizable Full-Canvas Workspace**: Master-detail view with persistent draggable column widths (260px to 640px) and prompt template chips.
* **Execution History & Output Timeline**: Detailed execution logs with run status badges, timestamps, duration metrics, and rendered Markdown outputs.
* **Self-Healing Plan Refinement (`automation.update_plan`)**: When executing scheduled jobs, the agent automatically diagnoses broken URLs (400/404) or website layout changes, explores alternative working paths, and permanently refines the saved task plan in SQLite for future unattended runs.

### 5. 🔌 Tool Protocols & Extensibility
* **Model Context Protocol (MCP)**: Native support for MCP `stdio` client sessions, managing external server sidecars and dynamically registering custom tool capabilities.
* **Real-Time Web Search**: Built-in Tavily Search API integration for live web lookups.

---

## 🏗️ Architecture & Security

```
┌─────────────────────────────────────────────────────────────┐
│                    Electron Desktop Shell                   │
│         (React 19 + TypeScript + Vite + CSS Tokens)         │
└──────────────────────────────┬──────────────────────────────┘
                               │ Loopback HTTP & Authenticated SSE
                               │ Bearer Token / 127.0.0.1:0
┌──────────────────────────────▼──────────────────────────────┐
│                    FastAPI Local API Gateway                │
├─────────────────────────────────────────────────────────────┤
│                       asAgent Core Engine                   │
│  ┌──────────────────────┬────────────────────────────────┐  │
│  │ Context Builder      │ Model Provider Neutral Adapter │  │
│  ├──────────────────────┼────────────────────────────────┤  │
│  │ Tool Pipeline & Sec  │ Scheduler & Cron Engine        │  │
│  ├──────────────────────┼────────────────────────────────┤  │
│  │ Browser Automation   │ Reversible File Snapshot Store │  │
│  └──────────────────────┴────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│             SQLite Repository & OS Keychain Store           │
└─────────────────────────────────────────────────────────────┘
```

* **Local Process Isolation**: The Python backend binds dynamically to a random loopback port (`127.0.0.1:0`) and reports its active port back to the Electron main process.
* **Single-Session Bearer Authentication**: An ephemeral Bearer token is generated on every launch; API and SSE endpoints reject unauthorized requests.
* **Credential Vault**: API keys are saved directly into the OS credential store (Keychain on macOS) and are never logged or exposed in plaintext.

---

## 💻 Quickstart

### Prerequisites
* **Node.js** >= 20.0.0
* **Python** >= 3.12 (managed via `venv` or `uv`)
* **npm** or **pnpm**

---

### 1. Clone & Environment Setup

```bash
# Clone the repository
git clone https://github.com/your-username/asAgent.git
cd asAgent

# Create and activate Python virtual environment
python -m venv .venv
source .venv/bin/activate

# Install Python dependencies in editable mode
pip install -e ".[dev]"

# Install desktop frontend dependencies
npm --prefix desktop install
```

---

### 2. Running in Development

Start both the Python agent backend and the Electron desktop application with a single command:

```bash
cd desktop
npm run dev
```

To run directly with DeepSeek using an environment secret:
```bash
ASAGENT_MODEL_API_KEY="your-deepseek-api-key" npm --prefix desktop run dev:deepseek
```

---

### 3. Testing & Quality Assurance

asAgent includes a comprehensive test suite (unit, integration, and contract tests):

```bash
# Run backend Python tests (530+ tests)
pytest

# Run desktop TypeScript typechecks, linting, and tests (133+ tests)
npm --prefix desktop run typecheck
npm --prefix desktop run lint
npm --prefix desktop test
```

---

### 4. Building Desktop Packages

```bash
# Build macOS application bundle (.dmg / .app)
npm --prefix desktop run build:mac

# Build Windows installer (.exe)
npm --prefix desktop run build:win

# Build Linux packages (AppImage / deb)
npm --prefix desktop run build:linux
```

---

## ⚙️ Model Providers & Configuration

Navigate to the **Settings** view in the application to select or configure your model endpoint:

| Provider | Deployment Type | Default Base URL | Status |
| :--- | :--- | :--- | :--- |
| **DeepSeek** | Cloud API | `https://api.deepseek.com/v1` | **Fully Tested & Verified** |
| **Ollama** | Local Server | `http://localhost:11434/v1` | Compatible (OpenAI API standard) |
| **LM Studio** | Local Server | `http://localhost:1234/v1` | Compatible (OpenAI API standard) |
| **OpenAI** | Cloud API | `https://api.openai.com/v1` | Compatible (OpenAI API standard) |
| **OpenRouter** | API Aggregator | `https://openrouter.ai/api/v1` | Compatible (OpenAI API standard) |
| **SiliconFlow** | Cloud API | `https://api.siliconflow.cn/v1` | Compatible (OpenAI API standard) |
| **Custom** | Local / Cloud | User defined | Compatible (OpenAI API standard) |

> [!IMPORTANT]
> **Current Testing Status**: While asAgent's model layer is strictly provider-neutral and conforms to the OpenAI API specification, **DeepSeek (e.g., `deepseek-chat`) is currently the primary model that has undergone thorough end-to-end testing and verification**. Testing and tuning for additional local/cloud providers is underway.

*API keys are encrypted and stored directly in your OS credential vault (macOS Keychain) and are never exposed in plaintext or logged.*

---

## 📋 Project Status & Roadmap

### ✅ Completed & Implemented
* [x] **Autonomous Agent Loop**: Multi-turn tool execution, schema validation, permissions, and timeout controls.
* [x] **Provider-Neutral Model Layer**: OpenAI-compatible adapter with streaming SSE and failure classification.
* [x] **SQLite Persistence**: Complete repositories for Conversations, Messages, Runs, Automations, and File Changes.
* [x] **Reversible Filesystem System**: Atomic diff snapshots with one-click rollback in chat.
* [x] **Embedded Browser Automation**: Dual-view isolation, Markdown DOM extraction, and page interaction tools (`navigate`, `click`, `fill`, `select`, `wait`).
* [x] **Scheduled Task Engine**: Cron scheduling, storm-prevention locks, timeline history, and self-healing plan updates (`automation.update_plan`).
* [x] **MCP Extensibility**: Stdio client session manager with dynamic tool registration.
* [x] **Desktop Interface**: Modern Electron shell with resizable panes, macOS window dragging, i18n localization (EN/ZH), and Neo-Mint design tokens.

### 🚧 Unimplemented / Pending Roadmap Tasks
* [ ] **Semantic Long-Term User Memory & Knowledge Base**: Embedding-based user profiling and memory recall across conversations (currently handled via sliding-window context buffer).
* [ ] **Dynamic Skill Directory Ingestion**: Modular on-disk `SKILL.md` parser and dynamic runtime loader for domain-specific agent instructions.
* [ ] **Multi-Agent Subagent Delegation**: Spawning and coordinating hierarchical subagent trees for multi-threaded complex research tasks.
* [ ] **Production Code Signing & Auto-Update Pipeline**: Apple Notarization, Windows Authenticode signing, and GitHub Releases auto-updater integration.
* [ ] **Standalone Headless Server / Docker Daemon**: Dedicated Docker Compose bundle for deploying the core backend as a remote headless service.

---

## 📄 License

Distributed under the [MIT License](LICENSE).
