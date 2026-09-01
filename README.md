<div align="center">

# asAgent

**A desktop AI agent that turns conversations into visible, controllable actions.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**English** • [简体中文](README_zh.md)

[📥 Download](#download--installation) • [▶ Watch the product demo](#demo) • [Quickstart](#quickstart) • [Features](#features) • [Project status](#project-status--roadmap)

</div>

---

asAgent brings chat, browser assistance, scheduled tasks, local knowledge retrieval, and reversible file operations into one desktop app. Conversations, knowledge indexes, and application state stay on your computer by default. When you choose an external model or network-enabled tool, only the data required for that request is sent to the configured service.

> asAgent is under active development. A signed and notarized preview build is available for Apple Silicon Macs; other platforms and a fully mature release experience are not yet supported. Developers can also run the project from source.

## Demo

<p align="center">
  <video src="https://github.com/user-attachments/assets/a0c0ef10-a6af-4939-a4dc-80879d4b844e" controls muted playsinline width="720">
    Your browser cannot play this video.
    <a href="https://github.com/user-attachments/assets/a0c0ef10-a6af-4939-a4dc-80879d4b844e">Open the product demo →</a>
  </video>
</p>

## What you can do

- Chat with OpenAI-compatible models and inspect each run.
- Ask the agent to read and interact with pages in a visible browser.
- Chat with PDF documents — extract and read text from authorized local PDFs or online PDFs directly in browser tabs without saving temporary files.
- Create one-time, daily, and weekly automated tasks.
- Build local Knowledge libraries from folders and ask grounded questions with source citations.
- Read and modify authorized files with snapshots and recovery safeguards.

asAgent currently has no telemetry integration. External model providers, Tavily, and other user-configured MCP servers may still receive the data required to perform requested operations.

---

## Features

### 1. Multi-turn chat and context management

- **Authenticated run-event streaming:** The desktop observes persisted `RunEvent` updates over Bearer-authenticated SSE. The current Agent Loop uses non-streaming model completion, so assistant text is shown after the run completes rather than token by token.
- **Run activity:** Collapsible activity cards show safe step, tool, status, timing, and sanitized error metadata. They do not expose chain-of-thought, tool arguments, or complete tool results.
- **Persistent history:** Chat and Browser conversations, user-visible messages, run status, and safe run events survive application restarts.

### 2. Conversation-scoped workspace and reversible file changes

- **Scoped access:** Each Chat conversation starts with its own asAgent Workspace and can be granted additional folders or individual files. Real-path resolution prevents `..` and symlink escape.
- **Read tools:** `filesystem.list`, `filesystem.read_file`, `filesystem.search_files`, and `document.extract_text` operate only inside the current conversation's allowed scope.
- **Local PDF text extraction:** `document.extract_text` extracts text layers from authorized `.pdf` files page-by-page with character-offset pagination, without loading entire multi-megabyte documents into model context at once.
- **Write tools:** `filesystem.create_file`, `filesystem.replace_file`, and `filesystem.delete_file` are currently allowed without a per-operation approval prompt inside an explicitly authorized scope. Create and replace accept complete UTF-8 file content; there is no line-level edit tool yet.
- **Undo safety:** SQLite stores FileChange metadata and hashes, while private pre-change snapshots are stored under the application data directory. Snapshots are full pre-change bytes, not SQLite diffs. The current limits are 20 MiB per snapshot and 200 MiB in total, with configurable retention and manual cleanup.
- **Safer deletion:** Deleted files are moved to the operating system Trash. When a private snapshot is available, the chat also offers a guarded Undo action.
- **Workspace inspector:** The desktop provides a directory tree, bounded text preview, refresh, reveal-in-Finder, and quote-into-prompt/chat actions.

### 3. Visible Browser assistant and isolated automation browser

- **Visible Browser conversations:** Electron owns a persistent `WebContentsView` session and keeps page credentials, cookies, DOM selectors, and storage out of Python and the Renderer.
- **Page tools:** Bound Browser runs can use `browser.navigate`, `browser.read_current_page`, `browser.read_current_pdf`, `browser.take_snapshot`, `browser.click`, `browser.fill`, `browser.select`, and `browser.wait`.
- **Online PDF memory reading:** `browser.read_current_pdf` extracts text directly from the active tab's streaming PDF preview in memory (up to 20 MiB), enabling reading online papers and manuals with zero disk footprint.
- **Semantic snapshots:** `browser.take_snapshot` returns bounded `ref`, name, role, tag, disabled state, and native select options. It does not expose full HTML or CSS selectors.
- **Page Assistant:** A side panel can discuss the current page and perform visible interactions on the bound tab.
- **Background isolation:** Scheduled tasks use a separate Playwright-over-CDP automation service and an independent browser profile. This path requires a supported system browser such as Google Chrome, Microsoft Edge, or Chromium.

### 4. Scheduled tasks

- **Conversation-based planning:** A short-lived, isolated draft conversation helps create or refine a task without adding draft messages to normal Recents.
- **Supported schedules:** Triggers currently support `once`, `daily`, and `weekly` schedules with IANA time zones. Arbitrary cron expressions are not supported.
- **Management and history:** Tasks can be created, edited, activated, paused, deleted, or run manually. Execution history stores status, timestamps, duration, and final visible messages.
- **Missed-run protection:** Startup recovery skips stale recurring occurrences instead of launching a catch-up storm.
- **Optional plan refinement:** During an automation execution, the model can call `automation.update_plan` to save a successfully verified correction for future runs. This is a tool-guided behavior, not a guarantee that every website failure will repair itself.

### 5. Local Knowledge workspace and grounded retrieval

- **Libraries and folders:** Create, rename, switch, and remove Knowledge libraries, then attach one or more local folders as their sources. Knowledge folder access is separate from a Chat conversation's general file workspace permissions.
- **Supported documents:** Indexes text-layer PDFs, Markdown (`.md`, `.markdown`), plain text (`.txt`, `.text`, `.rst`), Word (`.docx`), and HTML (`.html`, `.htm`). Scanned PDFs that require OCR are not supported yet.
- **Automatic local indexing:** A source watcher detects supported files added, changed, or removed from attached folders and schedules incremental parsing, deterministic chunking, and embedding. The header and folder list expose document and indexing progress.
- **Offline retrieval index:** The bundled `paraphrase-multilingual-MiniLM-L12-v2` ONNX model generates 384-dimensional embeddings without a runtime download. SQLite stores chunk text, provenance, jobs, conversations, and citations; embedded Qdrant Local stores vectors and the small filtering payload needed for library-scoped search.
- **Grounded answers:** Knowledge conversations retrieve filename-aware evidence and present citations with file, page or section, and source snippets. Bearer-authenticated SSE also reports simple searching and answer-generation activity before the response appears.
- **Recoverable removal:** Original files remain authoritative and are never changed by Knowledge. Removing a folder soft-detaches it from retrieval while retaining its derived index cache, so re-adding it does not unnecessarily embed unchanged files again.

### 6. MCP and web search

- **MCP stdio client:** asAgent supports modern MCP discovery with an isolated legacy fallback, namespaces imported tools, validates schemas, applies permission/approval policy, and imports configured servers atomically.
- **Startup-time tool set:** MCP servers are loaded when the Python Sidecar starts. Configuration changes require a restart; hot reload, notifications, and paginated tool discovery are not yet implemented.
- **Optional Tavily search:** Tavily is configured as a restricted stdio MCP server. Its API key is stored in macOS Keychain and injected only into that server process. Tavily is not a built-in search implementation and is disabled until the user configures it.

---

## Architecture & Security

```text
┌─────────────────────────────────────────────────────────────┐
│ Electron Renderer                                           │
│ React 19 · TypeScript · named Preload capabilities only     │
└──────────────────────────────┬──────────────────────────────┘
                               │ validated IPC
┌──────────────────────────────▼──────────────────────────────┐
│ Electron Main                                               │
│ backend lifecycle · token · native dialogs · browser views  │
└──────────────────────────────┬──────────────────────────────┘
                               │ loopback HTTP + authenticated SSE
                               │ Bearer token · 127.0.0.1:0
┌──────────────────────────────▼──────────────────────────────┐
│ FastAPI Local API                                           │
├─────────────────────────────────────────────────────────────┤
│ Agent Runtime · Context Builder · Models · Tools · Scheduler│
├─────────────────────────────────────────────────────────────┤
│ SQLite · Qdrant Local · Workspace · snapshots · Keychain    │
└─────────────────────────────────────────────────────────────┘
```

- The backend binds its own random loopback port and reports the actual endpoint through a structured ready record.
- Electron Main creates a fresh launch token and sends it to the child process over stdin. The token is not placed in command-line arguments, URLs, Renderer storage, or normal logs.
- Main parses authenticated SSE and exposes only structured run updates to the trusted Renderer.
- Knowledge keeps source text and provenance in SQLite and uses embedded Qdrant Local as a rebuildable vector index. Its bundled embedding model runs offline and is versioned with Git LFS.
- Model API keys and Tavily credentials are stored in macOS Keychain.
- The product is single-user by default (`local-user`) but preserves `user_id` at domain and persistence boundaries.

---

## Quickstart

### Prerequisites

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- Node.js `>=20.19.0` or `>=22.12.0`
- npm
- [Git LFS](https://git-lfs.com/) for the bundled local embedding model
- Optional for background web automation: Google Chrome, Microsoft Edge, or Chromium

### 1. Clone and install

```bash
git lfs install
git clone https://github.com/yuting-ai/asAgent.git
cd asAgent
git lfs pull

uv sync --locked
npm --prefix desktop ci
```

### 2. Run the desktop development environment

```bash
npm --prefix desktop run dev
```

The default development mode starts a deterministic offline model/tool runtime, so it does not require an API key. Configure a local or external OpenAI-compatible model in **Settings → Model & Privacy** when you want real model responses. Saved model settings take effect after the Sidecar restarts.

The older `dev:deepseek` developer entry also requires a matching non-sensitive `deepseek` profile under the selected app home; setting an API-key environment variable alone is not a complete fresh-clone setup.

### 3. Testing & quality assurance

```bash
# Python tests (currently 689 collected tests)
uv run pytest

# Python lint, formatting check, strict typing, lock and diff checks
scripts/check.sh

# Desktop type checking, linting, and tests (currently 192 tests)
npm --prefix desktop run typecheck
npm --prefix desktop run lint
npm --prefix desktop test
```

Docker is currently used for clean Linux testing and CI, not as a desktop runtime or supported server deployment:

```bash
docker build --file docker/Dockerfile.test --tag asagent-tests:local .
docker run --rm asagent-tests:local
```

### 4. Current build status

The Python Sidecar can be built and smoke-tested independently:

```bash
uv run python scripts/build_backend.py
uv run python scripts/smoke_backend_bundle.py
```

The Renderer/Main/Preload production build can be checked with:

```bash
npm --prefix desktop run build
```

The macOS ARM64 release workflow builds and smoke-tests the Python Sidecar, bundles it with the Electron app, signs and notarizes the DMG, and attaches tagged builds to GitHub Releases. These builds are still previews while the product is under active development. Windows and Linux release packages, non-macOS credential stores, automatic in-app update installation, and broader clean-machine verification remain pending.

---

## Model Providers & Configuration

The Settings view currently offers these OpenAI-compatible presets. DeepSeek is the primary externally hosted model used for end-to-end development testing; the other entries are compatibility presets rather than a guarantee that every model/endpoint combination has been fully verified.

| Provider | Location | Default base URL | Current status |
| :--- | :--- | :--- | :--- |
| DeepSeek | External | `https://api.deepseek.com` | Primary tested external provider |
| OpenAI | External | `https://api.openai.com/v1` | Compatibility preset |
| Ollama | Local | `http://127.0.0.1:11434/v1` | Compatibility preset |
| LM Studio | Local | `http://127.0.0.1:1234/v1` | Compatibility preset |
| OpenRouter | External | `https://openrouter.ai/api/v1` | Compatibility preset |
| SiliconFlow | External | `https://api.siliconflow.cn/v1` | Compatibility preset |
| Custom | Local or external | User-defined | OpenAI-compatible endpoints only |

Local endpoints may omit an API key. External endpoints require a saved key. On the current macOS implementation, keys are stored in Keychain and are never returned to the Renderer.

---

## Project Status & Roadmap

### Implemented

- [x] Provider-neutral Core contracts and OpenAI-compatible model adapter
- [x] Non-streaming Agent Loop with tool schemas, permissions, approval gates, timeouts, cancellation checkpoints, and safe RunEvents
- [x] SQLite persistence for conversations, messages, runs, events, tool calls, file changes, connections, and scheduled tasks
- [x] Conversation-scoped read tools and reversible single-file create/replace/delete with guarded Undo
- [x] Visible Browser conversations and isolated background browser automation
- [x] Once/daily/weekly Scheduled tasks with execution history and optional `automation.update_plan`
- [x] Local Knowledge libraries with watched folders, offline embeddings, Qdrant retrieval, grounded conversations, and citations
- [x] MCP stdio client/manager and optional Tavily MCP configuration
- [x] Electron development shell with Chat, Browser, Scheduled tasks, Knowledge, Settings, workspace inspector, and English/Chinese UI
- [x] Independent PyInstaller Sidecar build and automated smoke test

### Pending

- [ ] True token-by-token assistant response streaming through the desktop Agent Loop
- [ ] Conversation summaries, confirmed long-term User Memory, and cross-conversation retrieval
- [ ] Runtime loading and selection of on-disk `SKILL.md` files
- [ ] Multi-agent/subagent orchestration
- [ ] MCP pagination, notifications, hot refresh, and Streamable HTTP transport
- [ ] Broader desktop distribution for Intel Macs, Windows, and Linux, plus a wider clean-machine test matrix and automatic in-app update installation
- [ ] Supported headless/Docker server distribution

---

## Download & Installation

> [!NOTE]
> Currently, prebuilt packages are provided for **Apple Silicon (M-series / arm64)** Mac computers only. Intel-based Macs are not yet supported.

- 📥 **Direct Download**: [Download asAgent-arm64.dmg (Latest)](https://github.com/yuting-ai/asAgent/releases/latest/download/asAgent-arm64.dmg)
- 📦 **Release Notes & All Releases**: [GitHub Releases](https://github.com/yuting-ai/asAgent/releases/latest)
- 🔐 **Code Signed & Notarized**: Official releases are signed with an Apple Developer ID and notarized by Apple for seamless installation on macOS.

---

## License

asAgent is released under the [MIT License](LICENSE).
