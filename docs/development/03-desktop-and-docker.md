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

阶段 6 当前已实现最小开发入口：`uv run asagent serve --bootstrap-stdin --app-home <root> --port 0`。调用方在 stdin 写入一行 `{"token":"..."}` Bootstrap JSON；该参数只声明读取管道，Token 本身不出现在命令行。Backend 以 `AppPaths.from_root(app_home)` 定位并升级 `<root>/data/asagent.sqlite3`，在整个服务生命周期组合 SQLite Conversation/Run Repository、Starter、Finisher、离线 `development-tools` Runtime 与进程内 Dispatcher；每个 API 提交会立即返回 CREATED Run 并在后台执行，客户端可通过 `GET /api/v1/runs/{run_id}` 查询其稳定状态、通过 `POST /api/v1/runs/{run_id}/cancel` 请求协作取消，并通过 `GET /api/v1/runs/{run_id}/events?after_sequence=<n>` 回放/观察安全 RunEvent。事件流先从 SQLite 按 sequence 补发，再在 Run 活跃期间短轮询新增事件；Run 终态或客户端断开时结束。取消请求不直接终止模型调用或写入终态，Runtime 在安全检查点完成收口。退出时先关闭 Dispatcher，再关闭 Finisher、Starter 和 Repository，避免后台任务使用已关闭的数据库。App Factory 仍只接收注入的 Repository、Submission Service 与调度/取消回调。Backend 仅接受 `127.0.0.1`，自己绑定端口并在 Uvicorn 启动后向 stdout 输出一次并立即刷新 `ASAGENT_READY ` 前缀的 JSON，其中包含 `host`、实际 `port`、`pid` 和 `protocol_version`，不包含 Token。阶段 7 开发模式已由 Electron Main 使用 `BackendLauncher` 启动：Main 从 `desktop/` 的父目录作为 Python 项目根运行该命令，以仓库 `.local-data/` 作为 app home，在 Main 内生成 Token 并只写入 Backend stdin。Main 验证 ready 记录的 loopback host、端口、PID 和协议版本，再以同一 Token 轮询认证 Health；成功前不创建窗口，失败只显示启动错误并停止自己持有的子进程。Renderer 只通过窄 Preload 读取无敏感的 `ready`/`unavailable` 状态，尚不能读取 Token、端口或调用业务 API。当前 `serve` 不接受真实 Provider 配置；真实模型服务端组合、Workspace、发布版 Sidecar 路径与完整 Renderer API 接入仍待后续阶段。

阶段 7 已进一步完成只读 Renderer 接入：Electron Main 仍独占 Token 和 endpoint，`BackendLauncher` 复用该私有连接请求固定的 Conversation 列表和 Message 历史。Preload 只向受信任 Renderer 暴露这两个固定读取操作；它不暴露 Token、端口、任意 URL、写入 API 或 SSE。此前“Renderer 尚不能调用业务 API”的阶段性描述以此为准更新；创建 Conversation、提交 Message、Run 观察和 SSE 仍待后续独立任务。

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

MCP Token、密码和带凭据的环境变量进入系统 Keychain/Secret Store，不写入 `mcp.json`。SQLite 可以缓存 MCP Server 状态，但配置文件和数据库不能形成两个可独立修改的配置主来源。

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

### 提前验证

在 Local API 和 Electron 最小集成完成后，作为路线图阶段 7 的验收任务立即做第一次 PyInstaller Smoke Test，不等 MCP、Memory 和全部 UI 完成。阶段 12 再处理签名、公证、安装器、自动更新和正式发布。

重点验证：

- 动态模块是否被收集。
- 模板和数据文件路径。
- SQLite 和证书文件。
- 子进程和信号处理。
- 安装目录只读。
- 运行时数据写入 AppPaths。

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
