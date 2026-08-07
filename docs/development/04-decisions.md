# Ragent 架构决策记录

本文记录当前已确认决策、借鉴 CowAgent 的结论和仍需确认的事项。改变已确认决策时，应新增记录并说明迁移影响，不直接静默改写历史原因。

## 1. 已确认决策

### DEC-001：产品定位为本地私有个人助手

- 状态：已确认
- 决策：Ragent 默认在客户本地运行，数据默认保存在本机。
- 原因：产品目标是私人助手，不是 SaaS 或团队协作平台。
- 影响：优先本地 SQLite、Workspace、Electron 和本地安全边界。

### DEC-002：默认单用户，但保留 UserProvider

- 状态：已确认
- 决策：第一版固定 `user_id = local-user`，数据库保留 user_id，不实现登录、RBAC 和多租户。
- 原因：避免无效复杂度，同时保留未来身份映射边界。

### DEC-003：当前只实现本地对话入口

- 状态：已确认
- 决策：先实现 CLI、Local API 和 Electron Chat；Telegram、WeChat 等后置。
- 原因：Channel 不是 Agent Core 的核心难点，过早实现会分散学习目标。
- 影响：定义 Channel Adapter Protocol 和 Fake 测试，不开发真实适配器。

### DEC-004：采用模块化单体

- 状态：已确认
- 决策：Python 后端作为一个进程运行，内部按 Core、Chat、Agent、Models、Tools、Memory、Workspace、Storage 和 API 划分。
- 原因：适合个人本地应用，也便于学习、测试和打包。
- 排除：微服务、外部消息队列和 Kubernetes。

### DEC-005：名称保持简单

- 状态：已替代（见 DEC-023）
- 决策：项目名为 AsAgent，模块使用直白业务名称，不使用不必要的企业架构术语。

### DEC-006：拆分身份 ID

- 状态：已确认
- 决策：使用 `user_id`、`conversation_id`、`run_id`、`tool_call_id`、`event_id`，不让 session_id 承担全部责任。
- 原因：明确隔离、取消、持久化和未来 Channel 映射。

### DEC-007：Agent Runtime 按 Run 执行

- 状态：已确认
- 决策：长期状态来自 Repository，Runtime 尽量无状态，不长期维护 `agents[session_id]` 可变对象。
- 原因：避免内存和数据库状态分叉，降低并发和重启复杂度。

### DEC-008：消息、事件和模型上下文分离

- 状态：已确认
- 决策：用户可见 Message、内部 RunEvent、发送给模型的 Context 分开建模和持久化。
- 原因：支持 UI 展示、运行回放和上下文压缩，而不把内部消息直接暴露给用户。

### DEC-009：工具执行经过策略管线

- 状态：已确认
- 决策：工具必须经过 Schema 校验、权限策略、可选批准、超时、执行、结果截断和审计。
- 原因：模型选择工具不等于获得执行权限。

### DEC-010：工具命名空间化并使用 Run Snapshot

- 状态：已确认
- 决策：内部工具 ID 包含来源命名空间；一次 Run 使用稳定 Tool Snapshot。内部 ID 与模型 Provider 可见名称的映射由 DEC-021 细化。
- 原因：避免 MCP 同名覆盖和运行中 Schema 变化。

### DEC-011：主并发模型使用 asyncio

- 状态：已确认
- 决策：API、Runtime、事件和支持异步的工具使用 asyncio；阻塞工具进入受控线程池。
- 原因：避免混合大量 daemon thread、同步 Queue 和多个并发模型。

### DEC-012：Electron 是桌面外壳，Python 是业务核心

- 状态：已确认
- 决策：Electron Main 管理生命周期，Renderer 管理 UI，Python 实现全部 Agent 业务。
- 通信：本地 HTTP + 带 Bearer Header 的 fetch-based SSE。

### DEC-013：Electron 使用动态端口和临时 Token

- 状态：已替代（见 DEC-018）
- 决策：Main 选择空闲端口，通过启动参数传给 Python，并通过 Preload 告知 Renderer；不固定端口、不杀占用进程。
- 原因：比固定端口方案更安全，但后续审查发现“先探测、后绑定”仍存在竞争窗口，Token 也不应通过命令行传递。

### DEC-014：桌面发布采用 PyInstaller onedir Sidecar

- 状态：已确认
- 决策：Python Backend 打包为 onedir，由 electron-builder `extraResources` 携带。
- 原因：最终用户不需要 Python，且适合 Agent 数据文件和动态依赖。

### DEC-015：Docker 不是桌面依赖

- 状态：已确认
- 决策：日常开发运行本机 Python 和 Electron；Docker 用于测试、CI 和未来可选 Server 部署。
- 原因：桌面本地文件、浏览器、MCP 子进程和系统集成无法只靠 Docker 验证。

### DEC-016：先实现文本/关键词 Memory，再评估向量检索

- 状态：已确认
- 决策：Conversation、摘要和显式 User Memory 优先；不在第一版引入向量数据库。
- 原因：先理解记忆作用域和写入策略，避免用基础设施掩盖设计问题。

### DEC-017：CowAgent 仅作为按需、经确认的只读参考

- 状态：已确认
- 决策：CowAgent 源码目录为 `/Users/yuting/Desktop/BityDev/CowAgent`。Ragent 开发任务不得默认扫描或读取该目录；只有用户明确要求，或 Codex 说明具体参考目的并获得用户确认后，才能读取与问题直接相关的文件。
- 原因：Ragent 需要形成独立、可解释的架构，避免无意识复制 CowAgent 的历史兼容逻辑和耦合，同时保留在特定问题上向成熟实现学习的能力。
- 影响：CowAgent 不进入 Ragent 的 import path、依赖、构建、测试夹具和运行时配置。因参考产生的架构变化必须登记在本文。
- 执行规则：只读必要范围；先比较职责和取舍；不默认复制代码；没有确认时继续按照 Ragent 文档和测试推进。

### DEC-018：Backend 自主绑定动态端口并使用安全 Bootstrap

- 日期：2026-07-30
- 状态：已确认
- 决策：Backend 绑定 `127.0.0.1:0` 并向 Main 返回结构化 ready 记录；Main 不先探测再释放端口。临时 Token 优先通过子进程管道传递，环境变量仅作为后备，不进入命令行、URL 或日志。
- 通信：Renderer 使用带 Bearer Header 的 fetch-based SSE；Local API 校验明确的 Origin Allowlist。
- 原因：消除端口检查与绑定之间的竞争窗口，并解决原生 EventSource 无法设置 Authorization Header 的问题。
- 影响：阶段 6 定义认证 SSE 和续传契约；阶段 7 实现启动握手、Renderer 内存 Token 和 Sidecar 验证。

### DEC-019：RunEvent 的唯一标识与顺序分离

- 日期：2026-07-30
- 状态：已确认
- 决策：`event_id` 只负责唯一标识和去重；每个 Run 使用从 1 开始单调递增的 `sequence` 负责排序、回放和 SSE 续传，并对 `(run_id, sequence)` 建立唯一约束。
- 原因：UUID 和时间戳不能可靠表达并发事件的严格顺序。
- 影响：事件模型、SQLite Schema、SSE 帧和回放 API 都必须包含 `sequence`。

### DEC-020：文件与数据库的主数据边界固定

- 日期：2026-07-30
- 状态：已确认
- 决策：Conversation、Run、事件、摘要和结构化 User Memory 以 SQLite 为主；Profile、Knowledge Markdown、Skills 和用户文件以 Workspace 文件为主。数据库只索引文件，不维护第二份可独立修改的正文。
- 原因：避免 Memory 和 Knowledge 同时存在于文件与 SQLite 时发生双向漂移。
- 影响：`workspace/memory/` 仅用于可重建导出；MCP 非敏感配置以 `config_dir/mcp.json` 为主，Secret 使用系统 Secret Store。

### DEC-021：内部 Tool ID 与 Provider 名称分离

- 日期：2026-07-30
- 状态：已确认
- 决策：命名空间化字符串只作为内部 `tool_id`；Model Adapter 为每个 Provider 生成兼容名称，并在 Run Tool Snapshot 中保存双向映射和 Schema Hash。
- 原因：不同模型 Provider 对工具名称字符和长度的限制不同，MCP 内部 ID 不能直接假设可发送给模型。
- 影响：模型返回 ToolCall 后必须经 Snapshot 反查内部工具，回放也使用同一 Snapshot。

### DEC-022：锁定 Python 基线与阶段 0 工具链

- 日期：2026-07-31
- 状态：已确认
- 背景：阶段 0 启动前需要锁定 Python 版本、依赖管理、验证、测试、代码质量、类型检查和 SQLite 访问方案，保证本地、Docker 与 CI 使用同一套工程约定。
- 决策：Python 使用 `>=3.13,<3.14`，项目通过 `.python-version` 固定 `3.13`；依赖与虚拟环境由 uv 管理并提交 `uv.lock`；Pydantic 使用 `>=2,<3`，主要用于 API、配置、模型响应和工具参数等系统边界，Core 领域对象优先使用 dataclass、Enum、NewType 和 Protocol；测试使用 pytest 与 pytest-asyncio；Ruff 同时负责 Lint、Import 排序和格式化；CI 类型检查使用 strict mypy 与 `pydantic.mypy`；SQLite Repository 使用 SQLAlchemy `>=2.0,<2.1` Core 与 aiosqlite `>=0.20,<1`，不使用 ORM；数据库迁移使用 Alembic `>=1.18,<2`。
- 原因：Python 3.13 在生命周期与第三方依赖成熟度之间更平衡；单一 uv/Ruff/mypy 工具链减少环境差异；Pydantic 与领域对象分层可避免 Core 被序列化框架绑定；SQLAlchemy Core 保留显式 Schema、SQL 和事务边界，同时减少直接管理异步连接与迁移的重复代码。
- 影响：阶段 0 创建 `pyproject.toml`、`.python-version`、`uv.lock` 和质量检查配置；SQLAlchemy、aiosqlite 与 Alembic 的具体实现和迁移脚手架推迟到阶段 3，不得因此把存储实现提前放入阶段 0；SQLite 的 foreign keys、journal mode、busy timeout、synchronous 和事务控制在阶段 3 通过集成测试确定。
- 替代方案：Python 3.12、pyright、直接 sqlite3、SQLAlchemy ORM 和自有轻量迁移；当前均不采用。

### DEC-023：项目名称由 AsAgent 变更为 Ragent

- 日期：2026-07-31
- 状态：已确认
- 背景：阶段 0 代码骨架和首次提交尚未创建，当前是统一产品名称、Python 包名、命令名和桌面资源名的最低迁移成本时点。
- 决策：项目名称和桌面显示名使用 `Ragent`；Python 包名使用 `ragent`；后端命令和 Sidecar 名称使用 `ragent-backend`。DEC-005 中的旧名称 `AsAgent` 不再作为当前命名决策。
- 原因：用户确认在正式创建代码结构前采用新名称，避免后续同时迁移 import、入口点、构建产物和用户数据目录。
- 影响：产品、架构、路线、桌面和进度文档统一更新；未来代码目录使用 `src/ragent`，CLI 使用 `ragent`，macOS 用户数据目录使用 `~/Library/Application Support/Ragent/`。仓库物理目录已于 2026-07-31 重命名为 `/Users/yuting/Desktop/BityDev/Ragent`。
- 替代方案：继续使用 AsAgent；当前不采用。

### DEC-024：Message 使用独立的 MessageId

- 日期：2026-07-31
- 状态：已确认
- 背景：Message 是需要长期持久化和通过历史接口返回的用户可见领域对象；现有核心 ID 模型未包含其稳定身份。
- 决策：增加 `MessageId = NewType("MessageId", str)`；`UserMessage` 与 `AssistantMessage` 共用该 ID，并同时持有 `conversation_id`。MessageId 只标识“哪一条消息”，不负责 Conversation 内排序。
- 原因：避免让 Core 依赖 SQLite 自增主键，也不依赖无法严格唯一或稳定排序的 `(conversation_id, created_at)`、列表位置或 `run_id`。两类 Message 属于同一实体集合，共用 MessageId 可保持 Repository、API 和数据库边界一致。
- 影响：Core ID 模块、Message 数据对象、后续 SQLite `messages` 表和历史 API 均使用 `message_id`；Conversation 内排序将在阶段 3 Schema 设计中通过独立字段和约束确认。
- 替代方案：SQLite 自增主键、`(conversation_id, created_at)` 复合身份、列表位置或复用 `run_id`；当前均不采用。

### DEC-025：Provider 使用统一配置 Profile 与协议 Adapter

- 日期：2026-08-06
- 状态：已确认
- 背景：阶段 1 需要接入第一个真实模型。DeepSeek 作为首个目标，同时产品未来需要支持 OpenAI、Claude 和其他服务；若每家 Provider 都拥有独立且重复的配置结构，会把“用户选择什么服务”与“代码实现什么协议”混为一谈。
- 决策：首个真实 Provider Profile 为 `deepseek`，使用 `openai_compatible` Adapter。配置以 `config_dir/providers.toml` 中的命名 Profile 表达；每个 Profile 包含 `adapter`、`model`、`base_url`、超时等非敏感参数和 `secret_id` 引用。OpenAI 与其他兼容服务复用同一 Adapter，仅新增 Profile；Claude 使用独立的 `anthropic_messages` Adapter。所有实现继续只满足内部 `ModelProvider` Protocol。
- Secret：API Key 不写入 Profile、仓库、日志或测试夹具。后续通过 SecretProvider 从系统 Keychain/Secret Store 解析 `secret_id`；开发期环境变量只能由入口层显式作为后备，不能由 ChatService、Core 或 Provider 业务逻辑直接读取。
- 原因：DeepSeek 的官方 API 支持兼容格式，适合作为首个低复杂度实现；统一 Profile 消除重复配置，并允许将相同协议的服务作为配置扩展。Claude 的原生 Messages API 有独立请求与认证语义，应保持单独 Adapter，避免兼容 Adapter 逐渐变成难以维护的多厂商分支。
- 影响：下一任务先定义 Pydantic ProviderConfig 与 SecretProvider 边界，不立即写网络客户端。测试继续默认使用 Fake Provider；CLI 的 Echo Provider 保持离线默认值。真实 DeepSeek 网络调用、Provider 错误转换和重试在后续独立任务实现。
- 替代方案：每个厂商单独一套配置文件和 Python Provider、把 API Key 写入 TOML、让所有 Provider 强行共用 OpenAI 格式；当前均不采用。

### DEC-026：Provider 错误分类与保守重试

- 日期：2026-08-07
- 状态：已确认
- 背景：首个真实 HTTP Provider 已经可以发出请求；直接泄露 HTTPX 异常或 Provider 响应正文会使入口无法提供稳定提示，也可能意外暴露用户内容。另一方面，生成请求在网络中断后可能已由服务端处理，不能把所有故障简单重试。
- 决策：在 `models` 边缘使用 `ProviderError` 分类配置、认证、余额、请求、响应格式、传输、限流和服务端错误；异常只携带安全消息、可选 HTTP 状态码和 `retryable`，不保存响应正文、请求或 Secret。非流式 `complete()` 仅对 HTTP 429 与 5xx 使用固定短延迟重试一次；认证、余额、请求/响应格式、Secret 缺失及传输/超时不重试。流式调用不自动重试。
- 原因：DeepSeek 将 429、500、503 标为可在短暂等待后重试，而 400、401、402、422 需要修改配置、凭据、余额或请求。传输/超时是否已经触发模型生成不可判定；重试可能重复收费。流式响应可能已产生 UI 增量，重试会重复展示。
- 影响：`OpenAICompatibleProvider` 接口保持不变，入口可以按稳定错误类型提供脱敏提示；更复杂的指数退避、`Retry-After` 和跨 Provider 策略以后另行评估。
- 替代方案：透传 HTTPX/JSON 异常、所有错误立即重试、对流式请求重试或在异常中保留服务端正文；当前均不采用。

## 2. 技术选型

阶段 0 直接相关的技术选型已由 DEC-022 锁定；后续阶段的待定项仍在对应阶段开始前确认：

| 项目 | 方案 | 状态 |
| --- | --- | --- |
| Python | `>=3.13,<3.14`，`.python-version` 使用 `3.13` | 已确认 |
| Python 包管理 | uv，提交 `uv.lock` | 已确认 |
| 数据验证 | Pydantic `>=2,<3`，主要用于系统边界 | 已确认 |
| API | FastAPI | 推荐，待锁定 |
| 数据库 | SQLite | 已确认 |
| 数据库访问 | SQLAlchemy `>=2.0,<2.1` Core，不使用 ORM | 已确认 |
| 异步 SQLite Driver | aiosqlite `>=0.20,<1` | 已确认，阶段 3 引入 |
| 迁移 | Alembic `>=1.18,<2` | 已确认，阶段 3 引入 |
| 测试 | pytest + pytest-asyncio | 已确认 |
| Lint/Format | Ruff | 已确认 |
| 类型检查 | strict mypy + `pydantic.mypy` | 已确认 |
| Electron | Electron + React + TypeScript | 已确认方向 |
| Renderer 构建 | Vite | 推荐，待锁定 |
| UI 状态 | Zustand 或 React Context | 后期决定 |
| Python 打包 | PyInstaller onedir | 已确认 |
| Electron 打包 | electron-builder | 已确认方向 |

## 3. 已形成的 CowAgent 对比结论（历史记录）

以下内容是此前讨论后写入 Ragent 的冻结结论，不授权后续任务自动读取 CowAgent；重新查看源码仍需遵守 DEC-017。

### 借鉴

- Python Core 同时服务源码、Docker 和 Electron。
- Electron Main 启动 Python Backend。
- HTTP + SSE。
- Health Check。
- PyInstaller onedir + electron-builder extraResources。
- 用户数据与安装资源分离。
- Docker Volume 持久化 Workspace。
- 桌面版依赖精简和各平台独立 CI 构建。

### 优化

- 拆分 session_id 的多重职责。
- Agent Runtime 不绑定长期可变 Agent 实例。
- Bridge 拆成 ChatService、Runtime、Model、Tools、Events 和 Repository。
- Workspace 明确长期空间与 Run 临时空间。
- MCP 工具命名空间和 Schema Snapshot。
- 动态端口替代固定端口清理进程。
- 开发和发布使用同一 AppPaths 规则。
- Docker 使用更安全、精简的默认配置。

## 4. 开放问题与解决状态

### OPEN-001：第一目标操作系统

- 建议：先 macOS，保持跨平台路径抽象，稳定后增加 Windows。
- 待确认：是否正式接受这一优先级。

### OPEN-002：第一家真实模型 Provider

- 状态：已解决，见 DEC-025。
- 当前决定：首个真实 Profile 使用 DeepSeek 的 OpenAI-compatible Adapter；未来 OpenAI 复用 Adapter，Claude 采用独立原生 Adapter。
- 实施时点：先定义配置与 Secret 边界，再实现 DeepSeek 的真实网络客户端。

### OPEN-003：Shell 工具开放程度

- 选择：第一版不实现、严格 allowlist、或受批准的通用 Shell。
- 建议：阶段 5 先完成文件工具和 Policy，再决定 Shell。

### OPEN-004：个人记忆是否默认自动写入

- 选择：仅显式保存、自动建议后确认、完全自动。
- 建议：第一版采用“Agent 建议，用户确认”。

### OPEN-005：源码项目与 CowAgent 的物理关系

- 状态：已解决，不再是开放架构问题。
- 当前决定：Ragent 位于独立目录 `/Users/yuting/Desktop/BityDev/Ragent`，物理目录已于 2026-07-31 完成重命名。
- 已确认关系：CowAgent 仅按 DEC-017 作为经用户确认的只读参考，不建立代码依赖。
- 完成状态：独立 Git 仓库初始化和物理目录重命名均已完成；后续阶段 0 任务在 `progress.md` 跟踪。

### OPEN-006：SQLite 访问方式

- 状态：已解决，见 DEC-022。
- 当前决定：使用 SQLAlchemy 2.0 Core + aiosqlite + Alembic，不使用 ORM。
- 实施时点：阶段 0 只锁定选择；阶段 3 再实现 Repository、迁移和 SQLite 运行参数测试。

## 5. 决策模板

新增决策时复制：

```markdown
### DEC-XXX：标题

- 日期：YYYY-MM-DD
- 状态：提议 / 已确认 / 已替代
- 背景：为什么需要做决定
- 决策：最终选择
- 原因：选择依据
- 影响：代码、数据和计划如何变化
- 替代方案：考虑过但未采用的方案
```
