# asAgent 桌面端、打包与 Docker 决策

## 1. 总结

此前架构讨论形成了双交付路线，asAgent 在此基础上进一步明确安全和一致性细节：

```text
同一套 Python Agent Core
├── local-dev：本机 Python + 本机 Electron
├── desktop-release：Electron + PyInstaller onedir Sidecar
├── docker-test：干净环境测试和 CI
└── docker-server：后期可选的无桌面部署
```

Docker 不是桌面客户端依赖。最终用户安装 Electron 应用后，不需要安装 Python 或 Docker。

## 2. 已形成的 CowAgent 对比结论（历史记录）

本节是此前讨论后写入 Ragent 的冻结结论，不代表后续任务可以自动读取 CowAgent。需要重新查看或验证 CowAgent 源码时，仍必须遵守 `AGENTS.md` 的确认规则。

### 应借鉴

- Electron Main 管理 Python 子进程生命周期。
- Renderer 通过 HTTP + fetch-based SSE 使用 Python API。
- 后端提供 Health Check，准备完成后再开放 UI。
- 开发环境运行 Python 源码，发布环境运行打包后的可执行文件。
- PyInstaller 使用 onedir，便于携带 Skills、模板和动态依赖。
- electron-builder 通过 `extraResources` 携带 Sidecar。
- 可执行资源与用户可写数据分离。
- macOS、Windows 在各自平台 CI 构建。
- 桌面依赖集与完整服务器依赖集分开。

### 不直接照搬

- 不使用固定端口并终止占用端口的未知进程。
- 开发和发布不使用完全不同的数据路径规则。
- Docker 默认不使用 `seccomp:unconfined`。
- 第一版 Docker 镜像不安装所有语音、浏览器和渠道依赖。
- 不让 Renderer 直接知道长期 Secret/API Key 或任意访问本地文件；短期 Backend Token 只保存在内存。

## 3. Electron 三层边界

### Main Process

负责：

- 单实例锁和窗口生命周期。
- 启动、停止、重启 Python Backend。
- 让 Backend 绑定动态端口，并解析 Backend 返回的结构化启动握手。
- 生成一次启动周期的随机本地 Token，通过受控 Bootstrap 通道交给 Backend。
- 轮询 Health Check。
- 捕获 Backend stdout/stderr 并写入脱敏日志。
- 原生文件/目录选择器。
- 系统托盘、菜单和后续自动更新。
- 应用退出时清理子进程。

Main 不负责 Agent 业务。

可见嵌入式浏览器同样由 Main 管理，但它不是 Renderer 的任意网页容器：新的浏览器菜单只创建一个采用 asAgent 专属持久 Electron Session 的 `WebContentsView`。网页显示与用户登录发生在该 View 中，Renderer 只显示 asAgent 自己的 UI 状态，不能访问网页 DOM、Cookie、Storage、密码或向网页注入 IPC。HTTP/HTTPS 的 popup 请求不会生成任意原生窗口，而是转换为同一可见 Session 中受数量限制的标签；`file:`、`javascript:`、`data:` 等协议被拒绝。URL userinfo 只可在 Main 内实际加载时存在，所有回传 Renderer 的导航状态和地址栏值均删除 username/password。首版不接入 Python Backend 或 Agent；以后 BrowserAction 仍必须由 Main 在同一个可见 View 上执行，并先经既有站点范围、审批、超时和取消边界。不得让 Playwright/其他 Chromium 进程同时读取该 Profile 目录，也不得把该 Profile 当作 Gmail OAuth 或 MCP credential store。

Preferences 中的本地文件范围由 Main 的原生 `showOpenDialog` 选择目录；Main 在校验 Renderer 来源后，将目录路径交给受 Bearer 保护的固定 Workspace Settings API。Renderer 仅能读取已授权目录列表、请求选择一个目录或替换该列表，不能取得 Node 文件系统、任意路径读取或通用 IPC。该范围会在后续 Run 中约束已接入的受控读写 File Tool；保存范围本身不会扫描或修改文件，写操作仍需其独立 Tool 审批。

### Preload

只暴露最小、类型明确的 IPC：

```typescript
interface DesktopBridge {
  getBackendInfo(): Promise<BackendInfo>
  restartBackend(): Promise<void>
  selectFile(options?: FileDialogOptions): Promise<string | null>
  selectDirectory(): Promise<string | null>
  getAppVersion(): Promise<string>
}
```

不提供通用 Shell、通用文件读写和无限制 IPC Relay。

### Renderer

负责：

- Conversation 列表和聊天界面。
- SSE 事件显示。
- Tool 状态、错误、取消按钮。
- 设置和 Memory/Skill/MCP 管理界面。

所有用户可见的桌面 UI 文案统一为英文；当前不实现多语言切换或本地化资源层，未来若要支持其他语言，必须先建立完整的国际化策略，不能在单个界面混入不同语言。

安全默认值：

```text
contextIsolation = true
nodeIntegration = false
sandbox = true
```

Renderer 不启动 Python、不读取 API Key、不直接操作文件系统。

额外安全要求：

- 生产环境不加载远程代码，优先通过注册为 secure/standard 的自定义协议加载本地 Renderer 资源，而不是直接依赖 `file://`。
- 配置严格 Content Security Policy；开发和发布分别维护允许的连接来源。
- 禁止或限制页面导航、新窗口和不受信任的 `shell.openExternal`。
- Main 对每个 IPC 调用校验 sender 和参数，不把通用 `ipcRenderer` 暴露给 Renderer。

## 4. Python Backend 边界

Backend 独立支持：

```bash
asagent serve \
  --host 127.0.0.1 \
  --port 0 \
  --app-home '<path>' \
  --workspace-dir '<path>'
```

`--app-home` 是 Electron 或 CLI 入口已经解析好的应用数据根目录；Backend 通过 `AppPaths.from_root(app_home)` 得到 config、data、log、cache、默认 workspace 和 temp。`--workspace-dir` 只在用户显式选择独立 Workspace 时覆盖默认值。

Token 不作为命令行参数。首选由 Main 通过仅连接到该子进程的管道传递；如果第一版先使用环境变量，则使用专用变量名并确保它不会进入日志或崩溃报告。

开发环境命令可为：

```bash
uv run asagent serve ...
```

阶段 6 当前已实现最小开发入口：`uv run asagent serve --bootstrap-stdin --app-home <root> --port 0`。调用方在 stdin 写入一行 `{"token":"..."}` Bootstrap JSON；该参数只声明读取管道，Token 本身不出现在命令行。Backend 以 `AppPaths.from_root(app_home)` 定位并升级 `<root>/data/asagent.sqlite3`，在整个服务生命周期组合 SQLite Conversation/Run Repository、Starter、Finisher、Runtime 与进程内 Dispatcher；每个 API 提交会立即返回 CREATED Run 并在后台执行，客户端可通过 `GET /api/v1/runs/{run_id}` 查询其稳定状态、通过 `POST /api/v1/runs/{run_id}/cancel` 请求协作取消，并通过 `GET /api/v1/runs/{run_id}/events?after_sequence=<n>` 回放/观察安全 RunEvent。事件流先从 SQLite 按 sequence 补发，再在 Run 活跃期间短轮询新增事件；Run 终态或客户端断开时结束。取消请求不直接终止模型调用或写入终态，Runtime 在安全检查点完成收口。退出时先关闭 Dispatcher，再关闭 Finisher、Starter 和 Repository，避免后台任务使用已关闭的数据库。App Factory 仍只接收注入的 Repository、Submission Service 与调度/取消回调。Backend 仅接受 `127.0.0.1`，自己绑定端口并在 Uvicorn 启动后向 stdout 输出一次并立即刷新 `ASAGENT_READY ` 前缀的 JSON，其中包含 `host`、实际 `port`、`pid` 和 `protocol_version`，不包含 Token。阶段 7 开发模式已由 Electron Main 使用 `BackendLauncher` 启动：Main 从 `desktop/` 的父目录作为 Python 项目根运行该命令，以仓库 `.local-data/` 作为 app home，在 Main 内生成 Token 并只写入 Backend stdin。Main 验证 ready 记录的 loopback host、端口、PID 和协议版本，再以同一 Token 轮询认证 Health；成功前不创建窗口，失败只显示启动错误并停止自己持有的子进程。Renderer 只通过窄 Preload 读取无敏感的 `ready`/`unavailable` 状态，尚不能读取 Token、端口或调用业务 API。

阶段 7 已进一步完成只读 Renderer 接入：Electron Main 仍独占 Token 和 endpoint，`BackendLauncher` 复用该私有连接请求固定的 Conversation 列表和 Message 历史。Preload 只向受信任 Renderer 暴露这两个固定读取操作；它不暴露 Token、端口、任意 URL、写入 API 或 SSE。此前“Renderer 尚不能调用业务 API”的阶段性描述以此为准更新；创建 Conversation、提交 Message、Run 观察和 SSE 仍待后续独立任务。

阶段 7 现已允许 Renderer 经两个额外固定操作创建空 Conversation 与提交非空 Message。Main 保持来源检查并持有 Token；Renderer 不直接构造认证 HTTP 请求。提交请求立即返回已持久化的 USER Message 与后台 `created` Run，当前 UI 只显示前者及等待状态；Run 查询和 SSE 不在本次范围内。

阶段 7 已接入受限的实时 Run 观察：Main 对每个提交的 Run 保持认证 SSE 连接、解析 `text/event-stream` 帧，并仅把结构化安全事件推送给对应的受信任 Renderer。Preload 不暴露通用事件通道；Renderer 只能订阅具名 Run 更新并请求协作取消。对话内的临时 Activity 卡片保留本次 Run 的状态链，终态后重读 Message 历史显示最终助手回答。窗口内部采用固定 header/composer 与可滚动消息区，长 Activity 不会将输入框推出可视区域。

阶段 7 现支持可选的真实 Provider 开发验收。默认 `npm run dev` 仍只启动离线 `development-tools` Runtime；`npm run dev:deepseek` 仅向 Electron Main 提供非敏感的 Profile 名和 Secret 环境变量名。Main 将 `.env` 文件路径、`--profile` 与 `--secret-env` 交给自身启动的 Python Sidecar；Sidecar 使用既有 Profile Loader、EnvironmentSecretProvider、Provider Factory 和生命周期内的 HTTP Client 创建真实 Runtime。API Key 仅由启动时加载 `.env` 的 Python 进程读取，不进入 Renderer、Preload、IPC、URL、ready 记录或日志。真实配置或调用失败时不得降级为离线 Provider；正式发行版仍应以系统 Secret Store 取代开发 `.env`。

Electron Main 还会向 Renderer 暴露一个无敏感信息的处理模式：`local` 或 `external`。它只反映本次 Sidecar 的启动配置或已保存的桌面模型 Profile 是否可用，不包含 Provider 名、端口、Token 或 API Key；Privacy 与 Preferences 页面据此准确说明是否可能将请求内容发送到外部模型服务。默认离线模式明确不外发对话内容，真实 Provider 模式明确请求所需的对话内容和工具结果可能发送至选定服务商。

桌面 Chat 仅对 AssistantMessage 使用安全 Markdown 渲染，以显示标题、列表、引用、代码块、GFM 表格和普通外部链接；UserMessage 保持原始文本。Renderer 使用不启用原始 HTML 的解析配置，因此模型文本不会直接成为 DOM HTML。宽表格限制在消息区域内横向滚动。点击链接会经过窄 Main IPC：只允许无凭据的 `http`/`https` URL，并由系统默认浏览器打开；Renderer 不获得 Electron shell、任意 IPC 或页面内导航能力。消息数据库仍保存原始 Markdown 文本，显示规则不改变 API 或持久化契约。

文件修改审批继续复用对话底部的 Approval 横幅，并保留 `Deny`、`Allow once` 与 `Allow for this conversation`。对 CREATE、REPLACE、DELETE，Backend 只把目标路径和影响摘要返回给 Main/Renderer，待写入正文不会进入审批 IPC。成功修改后 Renderer 通过固定的 FileChange 查询显示持久卡片；用户点击 `Undo` 时，Preload 只把 `change_id` 和卡片中的精确路径交给 Main，Main 再以私有 Bearer Token 调用固定 Undo API。Renderer 不取得快照、文件正文、Token 或通用文件系统能力；刷新后卡片从 SQLite-backed API 恢复，冲突只显示安全提示而不强制覆盖文件。

消息的复制操作也遵循同一窄桥接原则：Renderer 只能请求具名 `copyText(content)`；Main 验证来源后使用 Electron 系统剪贴板写入纯文本。用户消息的 Edit 操作仅将现有正文填回 Composer，明确提示重新发送会创建新的消息和 Run；它不提供编辑 SQLite 中既有 Message 的 API 或 IPC。

需要重新组合 Sidecar 的设置（当前为模型 Profile 与 Tavily）在成功保存后显示统一的 `Restart asAgent now to apply your changes?` 提示。用户选择 `Restart now` 时，Renderer 只能调用固定 IPC；发布版 Main 校验来源、登记 Electron relaunch 并走正常退出流程关闭自身 Backend，随后启动新实例。`electron-vite dev` 模式则保留 Electron 进程，只重启 Main 持有的 Sidecar 并刷新 Renderer，避免开发编排器随 Electron 子进程退出而停止 Vite 服务。选择 `Later` 不回滚已保存的配置，但当前 Runtime 不会热替换。

发布环境命令为：

```text
resources/backend/asagent-backend/asagent-backend
```

Electron 只依赖 `BackendLauncher` 契约，不关心具体命令。

## 5. 本地通信

### HTTP

用于：

- Conversation CRUD。
- 创建 Run。
- 查询 Run。
- 取消 Run。
- 配置和状态。

API 使用版本前缀：

```text
/api/v1/health
/api/v1/conversations
/api/v1/browser/conversations
/api/v1/runs
/api/v1/runs/{run_id}
/api/v1/runs/{run_id}/cancel
/api/v1/runs/{run_id}/events?after_sequence=<n>
```

### SSE

用于单向流式事件。Renderer 使用 `fetch` 携带 Bearer Header 并解析 `text/event-stream`，不使用无法设置自定义 Authorization Header 的原生 EventSource：

```text
GET /api/v1/runs/{run_id}/events
```

事件统一包含：

```json
{
  "event_id": "evt_...",
  "sequence": 17,
  "event_type": "tool.completed",
  "conversation_id": "conv_...",
  "run_id": "run_...",
  "created_at": "...",
  "data": {}
}
```

后端在 SSE 帧中写入 `id: <sequence>`，并以 `event_type` 作为 SSE `event`。Renderer 记录最后确认的 `sequence`，断线后通过查询参数 `after_sequence` 重连；后端先从持久化事件补发，再对活跃 Run 短轮询新增事件。Run 终态或客户端断开时自然结束流。`event_id` 用于去重，`sequence` 用于排序和续传。`Last-Event-ID` 兼容仍是后续工作，不能作为当前客户端契约。

### 动态端口

```text
Electron Main 使用 --port 0 启动 Backend
→ Backend 自己绑定 127.0.0.1 的可用端口
→ Backend 在 stdout 输出一次带固定前缀的 JSON ready 记录
→ Main 从自己持有的子进程流读取并校验 PID、端口和协议版本
→ Main 使用实际端口轮询 Health
→ Preload 将 BackendInfo 传给 Renderer
```

Main 不采用“先探测空闲端口、释放后再让 Backend 绑定”的流程，避免检查与使用之间的竞争窗口；也不扫描和终止其他进程。

### 本地认证

每次 Electron 启动生成随机 Token。业务 API 要求：

```text
Authorization: Bearer <token>
```

Token 只保存在 Main、Backend 和当前 Renderer 的内存中，不进入命令行、URL、localStorage 或日志。Local API 校验 Origin Allowlist；生产 Renderer 与开发服务器分别配置明确 Origin。FastAPI 只为这些来源开放 CORS，并处理携带 Authorization Header 所需的 OPTIONS 预检，不使用 `*` 来源。

Health Endpoint 只返回最少状态，并与当前其他 API 一样要求本次启动的 Bearer Token。Backend 只监听 `127.0.0.1`。

## 6. Backend 生命周期

状态：

```text
stopped → starting → ready
             └────→ error
ready → stopping → stopped
```

启动：

1. 确定 AppPaths。
2. 生成 Token 并建立 Bootstrap 传递通道。
3. 使用 `--port 0` Spawn Backend。
4. 捕获日志，并等待带超时的结构化 ready 记录。
5. 校验 ready 记录中的 PID、端口和协议版本。
6. 在限定时间内轮询 Health。
7. 成功后通知 Renderer。
8. 失败则只终止自己持有的子进程，并展示明确错误和日志位置。

停止：

1. 优先调用受保护的 Shutdown Endpoint，并关闭 Bootstrap/控制管道。
2. 等待数据库提交和事件清理。
3. 超时后按平台对自己持有的子进程执行温和终止，再在第二个超时后强制终止；不假设 Windows 与 POSIX 的 SIGTERM 行为相同。
4. 绝不根据端口终止不属于当前 Electron 的进程。

需要保存 Spawn 后返回的 PID 和进程句柄。

## 7. AppPaths

业务代码不硬编码系统目录。统一对象：

```python
class AppPaths:
    data_dir: Path
    config_dir: Path
    log_dir: Path
    cache_dir: Path
    workspace_dir: Path
    temp_dir: Path
```

macOS 发布环境建议基于 Electron `app.getPath('userData')`：

```text
~/Library/Application Support/asAgent/
├── config/
│   └── mcp.json                 # 仅非敏感 MCP 配置
├── data/
├── logs/
├── cache/
├── workspace/
└── temp/
```

MCP Token、密码和带凭据的环境变量进入系统 Keychain/Secret Store，不写入 `mcp.json`。当前
`tools.mcp_config` 将该文件作为可选、严格的非敏感配置加载：每个 Server 仅声明名称、命令参数和
绝对工作目录；文件缺失代表没有 MCP Server，加载本身不启动子进程。SQLite 可以缓存 MCP Server
状态，但配置文件和数据库不能形成两个可独立修改的配置主来源。

开发环境使用仓库内 `.local-data/`，但仍通过完全相同的 AppPaths 参数传入。测试使用临时目录。

程序资源位于只读安装目录：

```text
asAgent.app/Contents/Resources/
├── backend/
└── app-assets/
```

升级程序不能覆盖用户数据。

## 8. PyInstaller 决策

### 使用 onedir

原因：

- Agent 需要携带模板、Skills 和可能的静态资源。
- 动态 Import 容易检查和补充。
- 启动无需每次解压巨大 onefile。
- 崩溃时更容易定位缺失依赖。

输出：

```text
desktop/build/dist/asagent-backend/
├── asagent-backend
└── _internal/
```

当前首次本地构建由 `uv run python scripts/build_backend.py` 执行。它将
`alembic.ini` 和 `alembic/` 迁移脚本作为 bundle data 携带，并显式收集
SQLAlchemy SQLite 异步驱动所需的 `aiosqlite` hidden import。冻结运行时的
CLI 从 `sys._MEIPASS/alembic.ini` 定位迁移配置；源码运行仍从仓库根目录定位。
构建中间目录与产物位于 `desktop/build/`，不进入版本控制。

### 提前验证

在 Local API 和 Electron 最小集成完成后，作为路线图阶段 7 的验收任务立即做第一次 PyInstaller Smoke Test，不等 MCP、Memory 和全部 UI 完成。阶段 12 再处理签名、公证、安装器、自动更新和正式发布。

重点验证：

- 动态模块是否被收集。
- 模板和数据文件路径。
- SQLite 和证书文件。
- 子进程和信号处理。
- 安装目录只读。
- 运行时数据写入 AppPaths。

2026-08-11 的首次手动冒烟及后续自动化冒烟均已通过。自动化命令为：

```bash
uv run python scripts/build_backend.py
uv run python scripts/smoke_backend_bundle.py
```

`smoke_backend_bundle.py` 从临时工作目录（非源码根）启动
`desktop/build/dist/asagent-backend/asagent-backend`，用 stdin 传入一次性 Token，
再验证认证 Health、创建会话、离线 `calculate 2 + 2` 的 `Tool result: 4`。它还断言
SQLite 仅出现在显式 `--app-home/data/asagent.sqlite3`，bundle 目录不存在 SQLite。
因此阶段 7 的本地 Sidecar 验收已完成；这不是已签名、已公证的正式发行包。

### 平台构建

- macOS ARM64 在 macOS ARM Runner 构建。
- macOS x64 在相应 Runner 或经过验证的交叉流程构建。
- Windows x64 在 Windows Runner 构建。
- 不假设一个 PyInstaller 产物跨平台运行。

## 9. Electron Builder

通过 `extraResources` 包含 PyInstaller onedir：

```json
{
  "from": "build/dist/asagent-backend",
  "to": "backend/asagent-backend"
}
```

正式阶段处理：

- macOS DMG/ZIP。
- Hardened Runtime、Entitlements、签名和公证。
- Windows NSIS 和代码签名。
- 自动更新。
- 数据库迁移和回滚策略。

第一目标平台尚待最终确认，当前开发优先保证 macOS 可用并保持跨平台路径抽象。

## 10. Docker 定位

### docker-test

从阶段 0 开始维护，用于：

- Python 干净环境安装。
- pytest、lint 和类型检查。
- SQLite 迁移测试。
- MCP stdio 测试 Server。
- CI。

当前最小实现为仓库根目录的 `docker/Dockerfile.test`。它使用 Python 3.13、固定的 uv 版本和已提交的 `uv.lock`，在干净 Linux 容器中执行单元测试、Ruff、mypy 与锁文件检查；`.dockerignore` 排除本地虚拟环境、缓存、本地数据和环境变量。当前不需要 Compose 文件。

### docker-server

后期可选，用于无 Electron 的后台运行：

```text
Browser/Web Client
→ Docker Python Backend
→ Volume Workspace/Data
```

它不是第一版产品主路径。

### 不在 Docker 中开发 Electron

Electron GUI、文件选择器、本地浏览器、用户 PATH、系统通知、签名和 Python Sidecar 都需要宿主机验证。Docker 不能替代桌面集成测试。

## 11. 推荐开发命令形态

当前已确定的命令形态如下；尚未创建的后续组件命令仅代表目标体验：

```bash
# Python 快速测试
uv run pytest

# 本地 Backend
uv run asagent serve

# Electron 开发
cd desktop && npm run dev

# Docker 干净环境测试
docker build --file docker/Dockerfile.test --tag asagent-tests:local .
docker run --rm asagent-tests:local

# 构建 Sidecar
./scripts/build-backend.sh

# 打包桌面应用
cd desktop && npm run dist:mac
```

## 12. 发布前桌面验收

- 干净机器不安装 Python 也能启动。
- 不安装 Docker 也能使用全部桌面核心功能。
- 重复启动只保留一个应用实例。
- Backend 崩溃有清晰恢复入口。
- 退出后无僵尸进程。
- 端口冲突不会终止其他应用。
- 安装目录只读不影响运行。
- 升级后配置、数据库、Workspace 和 Memory 保留。
- 日志不包含 Secret。
