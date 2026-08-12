# asAgent 架构决策记录

本文记录当前已确认决策、借鉴 CowAgent 的结论和仍需确认的事项。改变已确认决策时，应新增记录并说明迁移影响，不直接静默改写历史原因。

## 1. 已确认决策

### DEC-001：产品定位为本地私有个人助手

- 状态：已确认
- 决策：asAgent 默认在客户本地运行，数据默认保存在本机。
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

- 状态：已确认，首次本地冒烟已验证
- 决策：Python Backend 打包为 onedir，由 electron-builder `extraResources` 携带。
- 原因：最终用户不需要 Python，且适合 Agent 数据文件和动态依赖。
- 已验证实现：首次本地构建通过 `scripts/build_backend.py` 收集 Alembic 配置与迁移
  资源，并为 `aiosqlite` 声明 hidden import；冻结 CLI 从 bundle 的 `_MEIPASS`
  定位迁移配置，所有可写 SQLite 数据仍由 `--app-home` 的 AppPaths 决定。独立目录
  自动化冒烟已覆盖认证 Health、会话创建、离线 Calculator 回合与 bundle 数据目录断言。

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
- 决策：CowAgent 源码目录为 `/Users/yuting/Desktop/BityDev/CowAgent`。asAgent 开发任务不得默认扫描或读取该目录；只有用户明确要求，或 Codex 说明具体参考目的并获得用户确认后，才能读取与问题直接相关的文件。
- 原因：asAgent 需要形成独立、可解释的架构，避免无意识复制 CowAgent 的历史兼容逻辑和耦合，同时保留在特定问题上向成熟实现学习的能力。
- 影响：CowAgent 不进入 asAgent 的 import path、依赖、构建、测试夹具和运行时配置。因参考产生的架构变化必须登记在本文。
- 执行规则：只读必要范围；先比较职责和取舍；不默认复制代码；没有确认时继续按照 asAgent 文档和测试推进。

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
- 状态：已替代（见 DEC-027）
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

### DEC-027：项目名称由 Ragent 恢复为 asAgent

- 日期：2026-08-07
- 状态：已确认
- 背景：在创建 GitHub 远端和公开发布前，用户重新确认产品的最终名称为 `asAgent`。现有 Ragent 命名已进入源码、CLI、脚本、Docker、CI 和文档，但尚未有已发布包、桌面安装、持久化用户数据或远端仓库需要兼容。
- 决策：所有用户可见名称、仓库显示名称、项目物理目录、文档标题、CI 显示名称和未来桌面应用名称使用精确大小写 `asAgent`；Python 分发名、包名、源码目录、导入、CLI 和后端可执行文件使用全小写 `asagent`，后端名称为 `asagent-backend`；环境变量前缀使用 `ASAGENT_`。本决策替代 DEC-023；DEC-023 保留为历史记录。
- 原因：产品身份、仓库名称和未来公开版本统一为 asAgent；同时遵循 Python 包和命令使用小写标识符的惯例，避免在区分大小写的平台产生 import、打包和命令歧义。
- 影响：迁移 `src/ragent` 至 `src/asagent` 并更新所有导入、项目元数据、CLI、脚本、测试、Docker/CI、路径示例和当前文档。历史工作记录与 DEC-023 中的 Ragent 表述不改写；迁移完成前不创建 GitHub 远端或推送。由于当前没有发布数据，无需提供运行时名称兼容别名或数据迁移。
- 替代方案：保留 Ragent、仅把 GitHub 仓库命名为 asAgent、或在 Python 中使用混合大小写 `asAgent`；当前均不采用。

### DEC-028：单人开发使用本地 Commit 与定期 Push 节奏

- 日期：2026-08-08
- 状态：已确认
- 背景：当前项目由单人开发。每个小任务都立即 Push 会打断学习节奏，但只保留本地提交又缺少远端备份与 GitHub Actions 的独立环境验证。
- 决策：每个通过 `scripts/check.sh` 的边界清晰小任务都创建本地 Git commit；Push 在每日收尾、阶段子里程碑、开始风险较高的改动前，或需要 GitHub Actions 验证时执行。GitHub Actions 成功作为远端验收证据，不为单纯的成功结果再单独修改 `progress.md`。
- 原因：本地 commit 保持小步、可回退历史；定期 push 同时提供异地备份与干净 Runner 验证，避免为每次成功 CI 产生额外的文档提交。
- 影响：Codex 在小任务完成时提醒 commit；在上述时机提醒 push。`git status -sb` 与 `git log --oneline origin/main..main` 用于查看未同步状态。
- 替代方案：每个 commit 立即 push，或长期不 push；当前均不采用。

### DEC-029：Agent Loop 以完整模型上下文往返为实现前提

- 日期：2026-08-08
- 状态：已确认
- 背景：工具执行不是单向的“模型选工具、程序执行”过程。下一次模型调用必须看见先前 assistant 的工具请求以及每个配对的工具结果；若标准化消息或 Provider 不能表达该历史，Loop 即使控制流可运行，也会在真实请求中产生不合法或丢失上下文的交互。
- 决策：开始最小非流式 Agent Loop 前，先固定并测试完整的上下文往返：assistant `tool_calls`、带结果文本和 `tool_call_id` 的 TOOL message、Provider-neutral 请求，以及目标 Provider 的合法请求映射。`ModelMessage` 负责单条消息的局部不变量；Agent Loop/Context Builder 负责跨消息的 call/result 配对。Provider 只做协议转换，不修复不合法历史。
- 原因：把工具往返作为明确前置条件，能在离线测试中发现历史表示和出站请求的缺口，避免把问题推迟到接入真实模型后才暴露。
- 影响：阶段 2 的实施顺序调整为工具基础 → 工具消息契约 → Provider 映射测试 → 内部/Provider 名称映射与 Snapshot → 最小 Loop。流式 tool call、参数校验、权限、超时、审计和持久化仍是独立任务，不因最小 Loop 而视为完成。
- 替代方案：先完成 Loop 控制流，再补消息模型和 Provider 映射；或让 Provider 容忍并猜测不完整历史；当前均不采用。

### DEC-030：Run 内工具链保持完整并设置明确安全检查点

- 日期：2026-08-08
- 状态：已确认
- 背景：经用户授权比较 CowAgent 的工具循环、消息清理与取消实现后，确认工具调用历史最容易在上下文裁剪、异常和取消路径中被破坏。CowAgent 的“当前回合不裁剪”和“为失败调用保留结果”原则值得吸收；其可变会话状态、静默修复或删除历史的做法不适合 asAgent。
- 决策：assistant tool calls 与其全部 TOOL results 构成当前 Run 不可拆分的上下文单元。仅在 Run 开始前或完整工具链之间裁剪；每个已收到的调用在继续模型交互前都必须有成功或错误结果。取消在模型调用前、相邻工具之间和结果追加前检查；若取消留下未闭合调用，Runtime 不复用该模型上下文，除非先显式追加取消结果。重复调用检测使用内部 `tool_id` 与规范化参数，而非 Provider 显示名称。
- 原因：把链完整性变为 Runtime 的确定性规则，可在离线测试中覆盖失败与取消路径，并避免 Provider 因孤立 tool result 或缺失结果拒绝请求。
- 影响：阶段 2 的 Loop 验收增加完整链裁剪、失败结果、取消检查点和重复检测的要求；阶段 4 Context Builder 必须保持工具链原子性。当前不实现 CowAgent 的历史合成/删除修复、额外总结模型调用或可变会话对象。
- 替代方案：每次模型调用前让 Provider 猜测或修补历史；裁剪时允许拆开当前链；仅记录成功工具结果；当前均不采用。

### DEC-031：最小 Agent Loop 以模型决策计数并在上限处停止工具执行

- 日期：2026-08-09
- 状态：已确认
- 背景：工具执行次数与 Agent 的自主决策次数不是同一件事。一条模型响应可以请求多个工具；若把每个工具也计为步骤，会使并列工具调用意外耗尽预算。反之，若在最后一个模型决策后继续执行工具，会越过用户配置的限制。
- 决策：`max_steps` 计数单位是一次非流式模型响应，最小默认值为 8 且必须为正数。同一响应中的多个工具按稳定顺序执行，但不额外增加决策数。最后一个允许步骤若返回工具调用，Loop 不执行任何工具，直接进入 `LIMIT_REACHED`；不发出额外的“总结”模型调用。模型返回空文本且没有工具调用、空 tool call ID 或重复 tool call ID 时，Loop 进入 `FAILED`。
- 原因：按决策计数匹配预算意图，且能使上限行为完全确定、离线可测试，并保持 DEC-030 的工具链完整性约束。
- 影响：`AgentLoopResult` 返回终态、文本、模型上下文、已用步骤和可选错误；最小 Loop 仍不承担取消、超时、参数校验、重复调用检测、审计、RunEvent 或持久化。
- 替代方案：按工具调用计数、最后一步继续执行工具、自动追加总结模型调用，或将空/重复调用静默忽略；当前均不采用。

### DEC-032：重复工具调用检测默认关闭并按策略启用

- 日期：2026-08-09
- 状态：已确认
- 背景：完全相同的工具调用通常表示 Loop，但并非必然无效。时间、轮询、搜索和其他外部状态工具可以在相同参数下产生新结果；将统一的低阈值作为全局默认会破坏这些合法任务。
- 决策：最小 `AgentLoop` 为每个 Run 按内部 `tool_id` 与规范化 JSON 参数计数。`max_calls_per_tool_input` 默认为 `None`，仅检测、不阻断；调用方显式传入正整数时才启用硬限制，达到次数后不执行工具而追加配对错误结果。最小测试使用 2，允许一次重试并阻断第三次。未来由 Tool Policy 根据工具类型设定阈值或豁免。
- 原因：保留对确定性 Loop 的可测试防护，同时不把时间敏感或轮询工具误判为错误。
- 影响：重复计数只在一次 `run()` 内有效；不同参数不会互相影响。正式参数校验、工具级 Policy 与审计仍未实现。
- 替代方案：所有工具默认限制两次、完全不实现重复检测、或只给模型追加自然语言提示；当前均不采用。

### DEC-033：工具结果截断仅限制模型上下文副本

- 日期：2026-08-09
- 状态：已确认
- 背景：工具可以返回大文件内容、搜索结果或其他长文本。若不加边界，单条结果就能挤占后续模型推理所需的全部上下文；但直接截断执行结果或未来审计记录又会丢失可追溯事实。
- 决策：最小 AgentLoop 在将结果追加为 TOOL message 前使用可配置字符上限，默认 4,000；截断标记包含在该上限内。此限制只作用于模型上下文副本，不定义原始结果的存储或审计策略。当前配置下限必须足以容纳截断标记；阶段 4 再以 token 预算和更细粒度策略替代纯字符近似。
- 原因：立即阻止单一工具结果淹没上下文，同时不预先决定阶段 3 的 ToolCall 原始结果持久化方案。
- 影响：工具执行、错误、未知工具和重复限制产生的文本都经同一模型上下文边界；后续 Storage/审计必须在截断前捕获原始结果或记录其受控位置。
- 替代方案：不限制结果、截断但让标记超出上限、或把截断文本当作审计主数据；当前均不采用。

### DEC-034：基础 Run 取消采用协作式 Token 与安全检查点

- 日期：2026-08-09
- 状态：已确认
- 背景：阶段 2 需要让用户停止 Run，但直接取消任意 await 中的 Provider 或工具协程可能破坏外部 I/O、丢失已完成工具结果，或留下不合法的 assistant tool calls/TOOL results 历史。
- 决策：使用携带 `run_id` 的可变 `RunCancellationToken`，由调用方显式交给 AgentLoop。Loop 在模型调用前、模型响应返回后、每个工具前和每个工具返回后轮询 Token。若取消发生在已写入 assistant tool calls 后，保留已经完成的 TOOL result，并为剩余调用追加明确的取消结果后返回 `CANCELLED`。Token 本身不取消正在 await 的底层协程，也不使用全局注册表。
- 原因：先以确定、离线可测的安全点维护消息完整性；随后再让超时和 Provider/Tool 原生取消缩短实际等待时间。
- 影响：最小 Loop 可报告 `CANCELLED` 和已用决策步骤，但尚未持久化 Run 状态、发出 RunEvent 或提供按 `run_id` 查询 Token 的 API。未来 Runtime/Service 负责 Token 生命周期。
- 替代方案：直接 `task.cancel()`、取消时删除 assistant tool calls、或继续下一次模型调用而不补齐工具结果；当前均不采用。

### DEC-035：模型请求超时由 Provider Profile 管理

- 日期：2026-08-09
- 状态：已确认
- 背景：复杂推理的单次模型请求可能明显超过短交互的等待时间；同时，一个长 Agent Run 由多次模型调用、工具执行和外部等待组成，不能以单个短阀值代替整体任务策略。
- 决策：`ProviderConfig.timeout_seconds` 是单次模型 HTTP 请求的唯一当前超时配置，默认 180 秒，并允许每个命名 Provider Profile 覆盖。OpenAI-compatible Provider 将 HTTP 超时映射为 `ProviderTimeoutError`；非流式 AgentLoop 将该错误收敛为 `FAILED`，且不计入已完成的模型决策步骤。Loop 不再另设重复的模型等待阀值。
- 原因：Provider 最了解实际传输并且 Profile 可按模型能力、服务商和网络环境配置；180 秒避免把复杂推理误判为故障，同时保留有限等待边界。超时结果具有不确定性，自动重试可能造成重复计费。
- 影响：Provider 超时与一般传输错误可区分，但当前均不自动重试；工具超时、Run 总 deadline、后台长任务和用户界面中的等待/取消反馈仍是后续独立任务。
- 替代方案：在 AgentLoop 以固定 30 秒 `asyncio.wait_for` 包裹所有 Provider、取消超时保护、或把数小时的 Run 总时长混入单次 HTTP 配置；当前均不采用。

### DEC-036：工具超时由工具定义执行，并作为可恢复的 TOOL 结果

- 日期：2026-08-09
- 状态：已确认
- 背景：工具的耗时和副作用各不相同，统一的 Loop 级超时无法表达具体限制；而工具失败不必然意味着模型无法继续完成任务。
- 决策：`ToolExecutor` 使用每个不可变 `ToolDefinition.timeout_seconds` 通过 `asyncio.wait_for` 限制单次执行，并将超时转换为 `ToolTimeoutError`。AgentLoop 将其写为与原 `tool_call_id` 配对的 `Error: tool execution timed out.` TOOL message，再继续下一次模型调用；不因工具超时直接终止 Run。
- 原因：工具定义是工具级执行预算的唯一来源，避免重复配置；将失败事实交回模型，使其可改用参数、替代工具、解释限制或结束回答，同时保持模型上下文的 call/result 配对。
- 影响：超时会向工具协程请求取消，但对已经发送给外部系统的副作用不提供回滚保证；工具实现应正确处理取消和清理资源。最后允许决策步骤的工具仍不会执行；参数校验、权限、批准、审计、Run 总 deadline 与后台长任务仍待实现。
- 替代方案：工具超时后直接让整个 Run `FAILED`、让每个 Tool 自行实现不一致的超时、或吞掉超时而不向模型写入结果；当前均不采用。

### DEC-037：工具参数在 Executor 以固定 JSON Schema Draft 校验

- 日期：2026-08-09
- 状态：已确认
- 背景：模型返回的工具参数是运行时数据，不能假设与每个 Tool 的输入 Schema 一致；若让各工具自行解析，会导致校验语义、错误处理和安全边界不一致。
- 决策：`ToolExecutor` 在调用 Tool 前使用 `jsonschema` 的 `Draft202012Validator` 校验 `ToolDefinition.input_schema`。校验失败时抛出 `ToolArgumentsValidationError`，不调用 Tool；AgentLoop 将其转换为与原 `tool_call_id` 配对的通用 TOOL 错误文本，再交回模型继续决策。`jsonschema` 是运行时依赖，`types-jsonschema` 仅为 strict mypy 提供开发期类型信息。
- 原因：固定 JSON Schema Draft 避免未声明 `$schema` 时随验证器版本漂移；集中在 Executor 能使内置工具与未来 MCP 工具共享同一入口。通用错误文本避免将原始参数、Schema 或验证器内部细节写入模型上下文。
- 影响：当前校验覆盖实例参数；ToolDefinition 的 Schema 元校验、格式检查、参数归一化与更细的模型纠错提示仍待后续策略完善。无效参数不会进入工具协程，但仍会形成可恢复的模型上下文事实。
- 替代方案：由每个 Tool 手写检查、仅在 Prompt 中要求模型遵守 Schema、使用动态 Pydantic 模型，或把详细验证错误原样发给模型；当前均不采用。

### DEC-038：最小工具权限策略默认拒绝并显式注入授权集合

- 日期：2026-08-09
- 状态：已确认
- 背景：`ToolDefinition` 已声明 `required_permissions`，但没有统一执行点时，这些元数据不能限制模型驱动的工具调用；单用户本地产品也不应等同于所有工具天然可执行。
- 决策：`ToolExecutor` 接受不可变的 `granted_permissions` 集合，默认空集合。仅当工具的 `required_permissions` 是该集合的子集时才执行；否则抛出 `ToolPermissionDeniedError`。AgentLoop 将拒绝写为与原 `tool_call_id` 配对的通用 TOOL 错误结果，继续下一次模型调用。当前调用方必须显式授予例如 `tool.execute`。
- 原因：默认拒绝确保新增工具不会因遗漏组合根配置而自动获得能力；显式集合足以满足当前本地单用户阶段，同时不提前引入用户身份、数据库权限表或复杂 Policy DSL。
- 影响：Schema 校验先于权限判断，权限判断先于超时与执行；工具缺少授权时不会进入协程。`requires_approval` 尚未执行，后续审批策略可建立在已授予权限之上；未来 Runtime 再按 `user_id`、Workspace 和 Run 上下文构造实际授权集合。
- 替代方案：默认允许所有工具、在每个 Tool 内自行检查权限、将权限判断混入 AgentLoop，或把单用户假设编码为无条件允许；当前均不采用。

### DEC-039：文件系统范围由用户选择，副作用仍逐次批准

- 日期：2026-08-09
- 状态：已确认，阶段 5 实现
- 背景：本地 Agent 若以用户主目录、整块磁盘或不透明的递归搜索作为默认能力，会使单一任务获得远超所需的私人文件访问范围；模糊的“访问文件”提示也无法让用户作出知情决定。
- 决策：文件范围是用户在设置窗口中选择的持久、可撤销偏好，提供三档：仅 Workspace（默认）、用户明确选择的文件夹、整台电脑。任何范围内的路径都必须经 `WorkspaceResolver` 规范化，路径穿越和符号链接不得逃逸当前允许根。整台电脑模式须经高风险二次确认及平台所需的系统文件访问授权，且只扩大可寻址路径范围；它不自动授予写入、删除、执行命令或读取敏感位置的操作权限。用户也可将外部文件导入 Workspace。
- 用户可见信息：设置窗口必须清楚显示当前范围、已授权根目录及撤销入口；整台电脑模式展示风险说明与二次确认。逐次批准界面必须显示操作类型、精确规范化目标或根目录、所请求权限、是否递归、影响摘要和保留期限；不能只显示工具或 Agent 的宽泛最大能力。
- 审计：所有改变文件的操作以及授权/拒绝/范围扩大都记录最小必要元数据（时间、Run、工具、操作、目标范围和决定），不把文件正文、Secret 或无关路径写入审计。
- 原因：范围偏好让高级用户可主动选择便利性，而默认最小范围保护普通场景；将“能看到哪里”与“能做什么”分离，避免全盘读取偏好意外变成静默破坏全盘文件的能力。
- 影响：阶段 5 的 WorkspaceResolver、File Tool、设置窗口、Policy 和 Approval API 必须共同执行该边界；阶段 2 的 `granted_permissions` 只是一层工具类别开关，不能单独授权任意路径或高副作用操作。用户选择的外部根和全盘模式必须作为带来源、范围、生命周期与撤销状态的显式数据建模。
- 替代方案：默认允许整个用户目录、仅依赖模型提示词自律、在工具内部静默扩大路径范围、让全盘范围自动跳过高副作用批准，或以一次全局“磁盘访问”批准覆盖所有操作类别；当前均不采用。

### DEC-040：跨资源授权分离能力、资源范围与操作批准

- 日期：2026-08-09
- 状态：已确认，随浏览器、OAuth 与 MCP 能力实现
- 背景：文件、浏览器、Gmail 等 OAuth 服务和 MCP Server 的权限来源、资源边界不同。若把“全盘文件范围”或任一工具的长期授权解释为通用“全部权限”，会造成跨资源的意外权限继承。
- 决策：所有工具统一在三个互不替代的维度上授权：（1）工具能力，决定某类 Tool 是否可用；（2）资源范围，决定该 Tool 可以访问哪些文件根、浏览器 Profile/站点、OAuth scope 或 MCP Server；（3）操作批准，决定一次具体的高副作用动作是否执行。授权不跨维度、不跨资源传播：全盘文件模式只影响本地文件路径，不能授予浏览器、Gmail 或 MCP 权限；Gmail OAuth Token 只在其声明 scope 内有效；MCP Server 不继承宿主文件范围或账户 Token。
- 资源专属规则：浏览器使用独立 Profile、站点范围和会话；登录、上传、下载、提交表单等高风险动作单独批准。OAuth Token 存入 Secret Store，并按最小 scope 获取；发信、删除邮件或修改账户状态仍单独批准。stdio MCP 使用显式工作目录、最小环境变量和 Server 配置；远程 MCP 仅获得其自身 Token 与声明能力。浏览器下载或外部工具产物进入本地后，再按文件系统范围策略处理。
- 原因：统一模型让用户能够理解每次授权授予的究竟是什么，并防止方便设置演变为对无关账户或外部进程的隐式完全控制。
- 影响：未来 Policy、Approval、Settings、Secret Store、Browser Adapter 和 MCP Server Manager 必须携带资源类型与范围，不得只传一个通用 `allow_all` 标志；审计记录资源类型、范围与操作，但不记录正文、Cookie、Token 或 Secret。
- 替代方案：以全局“全权限”开关覆盖所有工具、让 OAuth/浏览器/MCP 自动继承文件范围、共享浏览器登录态与 Secret，或只依赖模型提示词区分权限；当前均不采用。

### DEC-041：最小用户批准以异步 Policy Gate 默认拒绝

- 日期：2026-08-09
- 状态：已确认
- 背景：工具的 `requires_approval` 元数据必须在执行前生效，但当前尚无 Electron/API 审批窗口、持久化请求或 RunEvent 通道；直接把 UI 细节放入 Executor 会破坏核心工具边界。
- 决策：`ToolExecutor` 接受可选异步 `ToolApprovalPolicy`，其输入为 `ToolDefinition` 与已校验参数，输出为允许或拒绝。仅对 `requires_approval=True` 的工具调用该 Policy；缺少 Policy 或 Policy 拒绝均抛出 `ToolApprovalDeniedError`，默认拒绝。AgentLoop 将拒绝写为与原 `tool_call_id` 配对的通用 TOOL 结果并继续让模型决策。审批检查位于权限检查后、超时和工具执行前。
- 原因：异步 Protocol 可由当前离线测试替身立即实现，也可在未来由 Electron/API 的用户交互实现，不必重塑 Executor 接口；默认拒绝避免尚未接入 UI 时意外放行高风险工具。
- 影响：当前没有审批窗口、审批请求 ID、持久化审计、过期时间或用户等待期间的取消处理。未来审批实现必须遵守 DEC-039/DEC-040 的资源范围和操作显示要求，并把等待中的取消作为独立任务处理。
- 替代方案：没有 Policy 时默认批准、让 AgentLoop 直接调用 UI、仅靠 `requires_approval` 提示词、或在每个 Tool 内自行弹窗；当前均不采用。

### DEC-042：阶段 2 采用最小基础与可体验垂直切片交替推进

- 日期：2026-08-09
- 状态：已确认
- 背景：工具消息契约、Snapshot、Loop 安全边界和权限 Gate 已分别可离线验证；若继续横向完成所有持久化、API、桌面与后续安全能力后才第一次运行完整链路，接口不匹配和交互反馈会过晚暴露。反之，在核心边界尚未建立时先做界面会令 Electron 或某个 Provider 反向绑定 Core。
- 决策：完成阶段 2 的最小 RunEvent 记录后，插入一个内存态、可由开发 CLI 手动体验的 Agent 垂直切片：输入经 AgentLoop、Provider、ToolExecutor 和内置工具到最终回答，并在终端展示 RunEvent。该切片先以 Fake Model 保证离线可重复验证，真实 Provider 仅作为可选手动路径；不等待 SQLite、SSE 或 Electron，也不提前实现审批窗口。
- 原因：以薄而完整的链路尽早验证模块接口、失败路径和用户可观察性，同时保留已建立的 Core 边界与小任务测试节奏。
- 影响：阶段 2 的下一顺序为最小 RunEvent 记录、最小 CLI Agent 闭环体验，然后再继续 ToolCall 记录及后续阶段工作。该 CLI 是开发体验入口，不替代阶段 1 ChatService 或正式桌面客户端；Run 的持久化、SSE 续传和 UI 仍按既定阶段实现。
- 替代方案：所有基础能力完成后一次性缝合，或先构建 Electron UI 再逐步补 Core；当前均不采用。

### DEC-043：最小 RunEvent 由 Loop 发布安全元数据，发布失败停止 Run

- 日期：2026-08-09
- 状态：已确认
- 背景：阶段 2 的 Loop 已能在内存中完成模型与工具回合，但缺少统一观察出口；未来 CLI、SQLite、SSE 与桌面 UI 若各自推断状态，会产生不一致的执行视图。事件同时不能携带模型上下文、工具参数或结果正文，以免将隐私和 Secret 扩散到日志与传输层。
- 决策：`AgentLoop` 可选注入 `EventPublisher`。启用时调用方显式提供 `run_id`、`conversation_id`、事件 ID 工厂与时钟；Loop 为单次 Run 从 1 单调递增发布 `run.started`、`model.requested`、`model.completed`、`tool.requested`、`tool.completed` 或 `tool.failed`，以及 `run.completed`、`run.failed`、`run.cancelled`、`run.limit_reached` 终态。事件仅包含步骤数、内部或 Provider 工具名与 `tool_call_id` 等安全元数据。未配置 Publisher 时不发布事件；已配置 Publisher 但任次发布失败时，Loop 停止后续模型和工具调用并返回 `FAILED`。
- 原因：复用 Core `EventPublisher` Protocol 使观察、持久化和 SSE 保持可替换；显式身份、时间和 ID 工厂使事件可确定测试；停止 Run 避免在调用方已要求可观察性却失去事件流时继续产生新的动作。
- 影响：当前事件仅进程内发布，不保存、查询、重放或发送给 UI；若最后一次终态事件本身发布失败，不能保证额外记录失败事件。ToolCall 原始结果、审计详情、事件重试与持久化由后续独立任务实现。
- 替代方案：由 CLI/UI 自行推断 Loop 状态、在事件中记录完整参数和结果、Publisher 缺失时抛错，或发布失败后继续执行；当前均不采用。

### DEC-044：开发 CLI 默认离线，真实 DeepSeek 仅由显式 Profile 启用

- 日期：2026-08-09
- 状态：已确认
- 背景：阶段 2 需要尽早体验完整 Agent 链路，但让默认 CLI 或自动测试依赖 API Key、网络与付费模型会降低可重复性；反过来，只保留离线脚本又无法观察真实模型是否会遵守工具 Schema 与完整调用历史。
- 决策：`asagent` 默认启动确定性的离线 Development Provider，并组合三个低风险内置工具、AgentLoop 与终端 EventPublisher。真实模式要求同时显式传入 `--profile <name> --secret-env <environment-name> --app-home <root>`：入口加载本地 Profile，并将其 `secret_id` 映射到调用者指定的开发期环境变量后通过现有 Provider 组合根创建 Adapter。`uv run --env-file .env` 可在启动前加载被忽略的开发环境文件，应用代码不解析 `.env`；正式桌面端以后使用系统 Secret Store。真实模式配置或调用失败时不降级到离线模式。
- 原因：离线默认保证测试与演示可重复；显式真实模式提供模型自主选择工具的实际体验；将 `.env` 限定在入口前的开发便利层，避免把文件式 Secret 误当成正式用户存储。
- 影响：当前 CLI 仅为开发垂直切片，不持久化 Conversation/Run，也不承担 ChatService、SQLite、SSE 或 Electron 的正式入口职责。真实调用可能产生费用，且单次等待受 Profile 超时约束。开发者为每次真实启动显式给出 Secret 环境变量名；正式 Secret Store 则按 `secret_id` 查询，不经过环境变量。
- 替代方案：默认真实 Provider、让 CLI/Provider 自行读取 `.env`、真实模式失败后悄悄改用 Fake，或将 `.env` 作为正式桌面端 Secret Store；当前均不采用。

### DEC-045：ToolCall 分离内部身份与模型调用身份

- 日期：2026-08-09
- 状态：已确认
- 决策：最小 Loop 可选注入异步 `ToolCallRecorder`。每个已解析内部工具的调用完成后记录不可变 ToolCall：内部 `tool_call_id` 由注入工厂生成，模型返回的 `call_id` 保存为 `model_call_id`；成功保存未截断原始结果，失败保存错误文本。未知 Provider 工具名没有内部 `tool_id`，本阶段仅保留配对 TOOL 错误与 RunEvent。Recorder 写入失败时停止 Run。
- 原因：模型协议 ID 只能负责本次请求历史配对，不能充当稳定的内部审计身份；同时不能让模型上下文的截断副本取代可追溯的执行事实。
- 影响：当前只进程内记录，SQLite Repository 后续适配该 Protocol；不实现审计 UI、重试或持久化 pending 状态。

### DEC-046：阶段 3 以 SQLAlchemy Core Schema 与 Alembic 管理本地 SQLite 迁移

- 日期：2026-08-09
- 状态：已确认
- 背景：阶段 3 需要先固定持久化表、约束和迁移基线，同时不让 Core 或未来 Repository 绑定 SQLite 连接实现。架构文档已使用 `schema_migrations` 这一名称，而 Alembic 默认版本表名称不同。
- 决策：使用 SQLAlchemy 2.0 Core `MetaData` 定义 `users`、`conversations`、`messages`、`runs`、`run_events` 与 `tool_calls`；使用 Alembic 管理迁移，并显式配置版本表为 `schema_migrations`。迁移命令使用同步 SQLite URL；未来运行时 SQLite Repository 使用 `aiosqlite`，并从 `AppPaths.data_dir` 接收数据库路径。Repository Protocol 仍是未来 PostgreSQL 等存储实现的替换边界。
- 原因：Core Schema 和迁移可独立验证，`schema_migrations` 与既有架构术语一致；同步迁移避免把运行时异步连接生命周期混入 Alembic。现在不创建泛化 DatabaseAdapter 或远程同步层，避免为尚未实现的场景增加抽象。
- 影响：初始迁移固定 Conversation 内 Message 顺序、Run 内 Event 顺序、外键及 ToolCall 结果/错误互斥约束；SQLite 专有连接设置、Repository、事务服务与 PostgreSQL 实现仍是后续独立任务。
- 替代方案：使用 Alembic 默认 `alembic_version`、额外维护自定义迁移表、或提前实现通用数据库/同步 Adapter；当前均不采用。

### DEC-047：SQLite Conversation Repository 在存储边界规范化 UTC 时间

- 日期：2026-08-09
- 状态：已确认
- 背景：SQLite 的日期时间存储不保留 `tzinfo`，直接回读会把原本 UTC-aware 的领域时间变成 naive datetime；非 UTC 输入还可能被错误解释为 UTC 墙上时间。
- 决策：`SqliteConversationRepository` 在写入前将 aware datetime 转换为 UTC，在读取时将 SQLite 的 naive datetime 解释为 UTC 并返回 UTC-aware 值。异步 SQLAlchemy 使用 `sqlalchemy[asyncio]` extra，显式包含其所需的 `greenlet` 运行时依赖；仍只使用 SQLAlchemy Core，不使用 ORM。
- 原因：时间规范化属于 SQLite/持久化边缘，Core Conversation 与 Message 模型不应知道具体数据库的时区限制；显式异步 extra 避免部署环境缺失运行所需依赖。
- 影响：持久化 Conversation 和 Message 可在重启后保持 UTC 时间语义；未来 PostgreSQL 适配器仍必须遵守同一 UTC 领域约定，但可使用原生时区类型。
- 替代方案：让各调用方自行处理时区、回读 naive datetime、或将 SQLite 原始字符串直接暴露给 Core；当前均不采用。

### DEC-048：SQLite 运行时连接使用 WAL、有限锁等待与 FULL 同步

- 日期：2026-08-10
- 状态：已确认
- 背景：阶段 3 的 Repository 会有多个连接及未来并发写入；SQLite 的外键、journal mode、锁等待与同步策略若分散在各 Repository，行为会随入口不一致且难以测试。
- 决策：所有运行时异步 SQLite Engine 经 `storage.sqlite.connection.create_sqlite_async_engine()` 创建，并在每个连接建立时设置 `foreign_keys = ON`、`journal_mode = WAL`、`busy_timeout = 5000` 毫秒和 `synchronous = FULL`。事务由调用方显式使用 SQLAlchemy 异步事务上下文管理；短暂写锁时后续写者在 busy timeout 内等待，而非立即失败。
- 原因：foreign keys 保持关系完整性；WAL 改善读写并存；有限等待吸收短暂单写者竞争且不无限挂起；个人助手优先数据耐久性，故选择 FULL 而非降低同步级别。集中工厂避免每个 Repository 复制或遗漏连接设置。
- 影响：SQLite Repository 只依赖该工厂，不自行注册 PRAGMA；运行时集成测试验证连接参数、异常回滚与锁等待后的写入。更长时间的锁冲突仍在 5 秒后报错，未来入口负责将其转换为可理解的 Run/API 失败；跨进程策略、业务级重试与 Run 的原子事务边界仍是后续任务。
- 替代方案：默认 rollback journal、连接遇锁立即失败、无限等待、`synchronous = NORMAL`，或让各 Repository 单独配置 PRAGMA；当前均不采用。

### DEC-049：SQLite Run Repository 以 Run 关联回放事件并保存原始 ToolCall

- 日期：2026-08-10
- 状态：已确认
- 背景：RunEvent 的领域对象需要 `conversation_id`，但数据库为避免冗余仅通过 `run_id` 关联 Run；ToolCall 则需要保存模型上下文之外的原始结果与参数。若允许二者的存储语义分散在 Loop、Publisher 或 API 中，回放与审计事实会不一致。
- 决策：`SqliteRunRepository` 完整实现既有 `RunRepository` Protocol。Run 按稳定 ID覆盖保存；RunEvent 保持仅追加语义，写入时校验其 `conversation_id` 与已存 Run 一致，读取时经 Run 关联恢复并严格按 `sequence` 与 `after_sequence` 回放。ToolCall 按稳定 ID覆盖保存，保存未截断的 `result` 或 `error` 和 JSON 参数；当前没有 ToolCall sequence 时，读取固定按 `created_at`、`tool_call_id` 排序。不可变 Mapping 在 Storage 边界复制为普通 JSON object，读取后再由领域对象冻结。
- 原因：不重复保存可由 Run 导出的 Conversation 身份，减少漂移；RunEvent sequence 保持 SSE 与回放的同一顺序契约；保存 ToolCall 原始内容兑现模型上下文截断不等于审计事实的边界；稳定排序让测试和未来 API 不依赖 SQLite 未定义的自然行序。
- 影响：Repository 接收已迁移数据库路径并复用统一 SQLite Engine 工厂，不推导 AppPaths 或执行迁移。它尚不是 `EventPublisher`/`ToolCallRecorder` 适配器，Runtime 组合、创建用户消息与 Run 的原子事务、重试、SSE 和审计 UI 仍由后续独立任务实现。
- 替代方案：在 `run_events` 重复保存 `conversation_id`、按插入/自然行序读取 ToolCall、把截断后的 TOOL message 当作唯一记录，或让 Loop 直接访问 SQLite；当前均不采用。

### DEC-050：用户消息与初始 Run 由 SQLite 单一事务创建

- 日期：2026-08-10
- 状态：已确认
- 背景：分别调用 ConversationRepository 追加用户消息、再调用 RunRepository 保存 Run 会产生两个独立事务。后一写入失败时，数据库会留下没有对应执行的用户消息，破坏请求与执行的最小一致性。
- 决策：使用 `SqliteRunStarter.start(user_message, run)` 作为阶段 3 的 SQLite 专属跨表写入协调器。它在同一 `AsyncEngine.begin()` 事务中校验 Message 与 Run 的 Conversation 身份相同且 Conversation 已存在，再插入用户 Message（数据库分配该 Conversation 的 sequence）与初始 Run。Run 主键或任何后续插入失败时，整个事务回滚；未知或不一致 Conversation 在写入前明确拒绝。
- 原因：跨 Repository 的原子性必须由共享连接和明确事务边界提供，不能由两个成功的异步方法调用“看起来连续”来保证。输入保持为已构造的领域对象，使 ID、时间、状态与未来入口策略不被 SQLite 存储层隐式生成。
- 影响：该协调器不替代 ConversationRepository 或 RunRepository，不生成 `run.started` Event，也不实现 API 重试幂等键、每 Conversation 锁、Runtime 组合、Publisher/Recorder 适配或锁超时的用户提示。这些仍需要在后续服务/API 任务中设计。
- 替代方案：让入口依次调用两个 Repository、在各 Repository 中嵌套事务、由 SQLite Trigger 自动创建 Run，或现在提前引入通用 Unit of Work/分布式事务抽象；当前均不采用。

### DEC-051：RunEvent 通过注入的 Repository 持久化

- 日期：2026-08-10
- 状态：已确认
- 背景：Agent Loop 已通过 Core `EventPublisher` 发布安全运行事件；若 Loop 直接依赖 SQLite，或 Publisher 自行创建数据库连接，Core 与存储实现会耦合，且连接生命周期难以由组合根统一管理。
- 决策：新增 `storage.event_publisher.RepositoryEventPublisher`，仅依赖 `RunRepository` Protocol，并把 `publish(event)` 原样委托给 `repository.append_event(event)`。运行时需要 SQLite 持久化时，由组合根注入 `SqliteRunRepository`。
- 原因：依赖倒置使 Agent Runtime 不知道数据库细节，同时可复用同一 Publisher 适配任何未来的 RunRepository 实现。事件顺序、去重约束和 JSON 转换继续由 Repository 的既有契约负责。
- 影响：适配器不创建 Engine、不重试、不改变 Event 数据，也不吞掉写入异常；异常向上层传播，沿用 Agent Loop 已有的失败路径。该任务不接入 SSE、Run 状态更新或 ToolCall 持久化。
- 替代方案：让 Agent Loop 直接调用 SQLite、在 Publisher 中硬编码 SqliteRunRepository 或创建独立 Engine、在此处补偿重试/状态更新；当前均不采用。

### DEC-052：ToolCall 通过注入的 Repository 持久化

- 日期：2026-08-10
- 状态：已确认
- 背景：Agent Loop 已在工具调用结束后通过 Core `ToolCallRecorder` 记录完整的工具审计对象。若 Loop 直接写 SQLite，将把编排层与持久化实现耦合；若记录适配器自行创建连接，也会绕开应用的连接生命周期。
- 决策：新增 `storage.tool_call_recorder.RepositoryToolCallRecorder`，仅依赖 `RunRepository` Protocol，并将 `record(tool_call)` 原样委托给 `repository.save_tool_call(tool_call)`。运行时需要 SQLite 持久化时，由组合根注入 `SqliteRunRepository`。
- 原因：与 RunEvent 的持久化采用相同依赖倒置边界，使 Loop 无需知道数据库细节，并允许未来替换 Repository。ToolCall 的 JSON 参数、原始成功结果或错误及稳定读取顺序仍由 Repository 契约负责。
- 影响：适配器不创建 Engine、不截断或重写 ToolCall、不重试也不吞掉异常；写入失败向 Loop 传播并触发其既有 FAILED 路径。本任务不改变工具执行、事件发布、Run 状态更新或 SSE。
- 替代方案：让 Agent Loop 直接调用 SQLite、让 Recorder 硬编码 SqliteRunRepository、在 Recorder 内增加重试或吞错；当前均不采用。

### DEC-053：终态 Run 与可见 AssistantMessage 由 SQLite 单一事务完成

- 日期：2026-08-10
- 状态：已确认
- 背景：Run 已能在启动时与用户消息原子创建。若 Agent Loop 结束后由 Runtime 分别追加 AssistantMessage 和更新 Run 终态，任一失败会留下“有回答但 Run 仍未完成”或“Run 已完成但回答缺失”的不一致记录。
- 决策：使用 `SqliteRunFinisher.finish(run, assistant_message)` 作为阶段 3 的 SQLite 专属结束协调器。它要求 Run 是终态，校验可选 AssistantMessage 与已存 Run 属于同一 Conversation，并在同一事务中追加消息（如有）和更新 Run 的 status、updated_at；任一写入失败则整体回滚。
- 原因：启动与结束是一次 Run 生命周期中两个跨表一致性边界。显式 SQLite 协调器避免把事务控制泄漏到 Runtime，也不为尚未实现的多数据库场景提前引入 Unit of Work。
- 影响：失败、取消或达到步骤上限时可不写 AssistantMessage，但仍原子更新终态 Run；由未来 Runtime 决定何时传入用户可见文本。该组件不生成领域对象、不更新 Conversation 元数据、不做幂等、重试、SSE 或工具审计。
- 替代方案：Runtime 依次调用两个 Repository、用 SQLite Trigger 自动创建消息、让 RunRepository 直接依赖 Conversation 表，或提前引入通用事务抽象；当前均不采用。

### DEC-054：持久化 Agent Runtime 依赖生命周期 Protocol 与预配置 Loop

- 日期：2026-08-10
- 状态：已确认
- 背景：阶段 3 已有 SQLite 的启动/结束原子事务，以及 EventPublisher 与 ToolCallRecorder 持久化适配器；若 Runtime 直接 import SQLite 或由入口自行拼接每一步，将破坏 Core 边界并容易遗漏终态保存。
- 决策：`PersistentAgentRuntime` 位于 agent 应用层，只依赖 `ConversationRepository`、新增的 Core `RunStarter` / `RunFinisher` Protocol、已配置的 `AgentLoop`、时钟和 ID 工厂。它负责顺序组合“原子开始、读取可见历史、Loop、原子完成”；SQLite 实现和两个 Repository 审计适配器由外部组合根构造并注入 Loop/Runtime。
- 原因：Runtime 获得一条明确、可测试的请求生命周期，同时仍不知道数据库、Engine、FastAPI 或 Electron。将 EventPublisher/Recorder 保持为 Loop 的已配置依赖，避免 Runtime 重复定义事件与工具审计语义。
- 影响：未知 Conversation 在模型调用前拒绝；所有 Loop 终态都会保存 Run；仅 COMPLETED 的最终文本写入 AssistantMessage。LIMIT_REACHED 的潜在文本不进入 Conversation，以免未闭合工具回合污染未来模型历史。请求幂等、每 Conversation 锁、取消注册、SSE 和 API 仍不在本任务范围。
- 替代方案：让 CLI/API 手写完整生命周期、Runtime 直接依赖 SqliteRunStarter/Finisher、让 Loop 负责 Message/Run 写入，或把 LIMIT_REACHED 文本一律保存为助手回答；当前均不采用。

### DEC-055：SQLite 启动迁移由显式数据库初始化函数执行

- 日期：2026-08-10
- 状态：已确认
- 背景：Alembic 升级此前只存在于集成测试辅助函数中，开发组合根无法可靠地为 `AppPaths.data_dir` 下的应用数据库创建或升级 Schema。
- 决策：新增 `storage.sqlite.database.upgrade_sqlite_database(database_path, alembic_config_path)`。调用方显式提供两条路径；函数创建数据库父目录、为 Alembic 设置同步 SQLite URL，并执行 `upgrade head`。迁移失败原样传播。
- 原因：将启动迁移从测试代码提升为可复用的 Storage 边界，同时不让 SQLite 层猜测用户数据位置或持有 AppPaths。显式 Alembic 配置路径使开发组合根的资源来源可见。
- 影响：后续持久化 CLI/API 组合根使用 `AppPaths.data_dir / "asagent.sqlite3"` 计算数据库位置，并在构造 Repository 前调用该函数。函数不创建 Engine、Repository、Conversation、Run 或 Runtime；正式打包时迁移资源如何携带仍由桌面打包阶段决定。
- 替代方案：每个入口复制测试 `_upgrade()`、Repository 首次使用时隐式迁移、Storage 中硬编码 `.local-data` 或当前工作目录，或跳过迁移直接创建表；当前均不采用。

### DEC-056：持久化开发 CLI 以显式模式组合 SQLite Runtime

- 日期：2026-08-10
- 状态：已被 DEC-057 扩展
- 背景：持久化 Runtime、SQLite 生命周期协调器和审计适配器已经独立验证，但此前没有入口将它们组合成可跨进程手动体验的完整链路；直接改变默认 CLI 又会破坏已有离线、无副作用的开发行为。
- 决策：新增 `--persistent` 开关。启用后 CLI 从 `AppPaths.data_dir / "asagent.sqlite3"` 计算数据库路径、执行启动迁移，组合 SQLite Repository/Starter/Finisher、Repository EventPublisher/ToolCallRecorder 与 PersistentAgentRuntime。它仅使用离线 DevelopmentToolModelProvider；可选 `--conversation-id` 用于复用既有 Conversation，省略时创建新的本地用户 Conversation。
- 原因：显式模式使持久化行为可体验、可测试且不意外改变默认 CLI；离线 Provider 保持零网络、零费用的可重复演示。对话 ID 显式输出与输入提供最小跨进程续接，不提前构建对话列表 UI 或 API。
- 影响：最初实现仅使用离线 Provider；真实 Provider 与持久化 Runtime 的组合已由 DEC-057 扩展。不存在 Conversation 在模型调用前拒绝。该模式只打印最终回答、错误或终态，事件已持久化但尚不做终端多播/SSE。正式 Secret Store、API 与 Electron 仍为后续任务。
- 替代方案：把默认 CLI 改为持久化、让每次启动新建不可续接 Conversation、持久化模式默认调用真实模型、或现在引入 EventPublisher fan-out/SSE；当前均不采用。

### DEC-057：真实 Provider 可显式组合到持久化开发 Runtime

- 日期：2026-08-10
- 状态：已确认
- 背景：持久化开发 CLI 起初只使用确定性的离线 Provider，真实 `--profile` 路径则只运行内存态 Agent Loop，导致真实模型的 Conversation、Run、RunEvent 与 ToolCall 无法进入已验证的 SQLite 生命周期。
- 决策：`--persistent` 只表示使用 SQLite 持久化 Runtime，不再排斥真实 Provider。调用者同时提供成对的 `--profile` 与 `--secret-env` 时，CLI 从 Profile 创建 `ModelProvider`，将其与 SQLite 生命周期协调器、EventPublisher 和 ToolCallRecorder 组合到同一个 `PersistentAgentRuntime`；没有该参数对时，继续注入离线 DevelopmentToolModelProvider。真实 HTTP Client 覆盖整个交互会话并在退出时关闭。
- 原因：持久化语义属于 Runtime/Storage 组合，模型厂商选择属于入口层；二者通过 `ModelProvider` Protocol 正交组合，避免为真实模型复制另一套 Run 或审计流程。显式参数对保持密钥来源可审计，并避免网络、配置或密钥错误静默回退到离线模式。
- 影响：CLI 现在支持离线/真实 Provider 与内存态/持久化的四种明确组合；真实持久化模式会产生费用，仍仅是开发入口，不引入 API、SSE、桌面 UI、取消注册或未完成 Run 恢复。测试用 FakeModelProvider 验证通用 Provider 注入路径，不在自动化测试访问真实网络或 Secret。
- 替代方案：保持真实 Provider 只能内存态运行、为真实模式复制 PersistentAgentRuntime、让 Runtime 自行读取 Profile/环境变量，或在持久化模式失败时回退到离线 Provider；当前均不采用。

### DEC-058：上下文压缩、长期记忆与历史检索分层并以快照确定模型可见内容

- 日期：2026-08-10
- 状态：已确认
- 背景：长 Conversation 需要预算、裁剪和可能的语义压缩；个人助手又需要跨 Conversation 学习稳定偏好，并可能检索相关历史。若把这些过程混为后台“记忆刷新”，模型当前实际可见材料会随异步回调变化，重试可能重复摘要或写入，且临时对话内容会错误升级为长期偏好。参考 CowAgent 的上下文和记忆实现后，asAgent 采用其“完整工具链裁剪、分项预算与用户可配策略”的优点，但不复制其后台摘要注入、模型名窗口猜测或短期压缩与长期记忆混写方式。
- 决策：阶段 4 的 Context Builder 每次调用前创建不可变 `ContextSnapshot`，并以完整工具链为裁剪单元。模型能力配置提供 context window 硬上限；用户策略提供输入预算、输出预留和轮次保护，实际预算不得超过能力上限。原始 Conversation Message 继续是 SQLite 主数据；摘要、裁剪和检索只生成模型请求副本。Conversation Summary、User Memory、Skill 和跨 Conversation 检索严格分层：Summary 仅用于同一 Conversation 连续性；User Memory 是经用户确认的跨 Conversation 偏好/事实；Skill 是用户维护的版本化说明；检索结果是带来源、受范围和预算限制的历史参考，不进入 System Prompt。阶段 4 只定义摘要/压缩接口和确定性降级；阶段 10 才持久化/复用 Summary、写入 User Memory 并先实现关键词检索。
- 原因：快照让 Run 可解释且避免后台竞态；幂等的摘要覆盖区间与策略版本让重试可控；分层避免把临时内容或旧提示当成永久人格。模型能力与用户偏好分离，既允许未来设置窗口控制成本和体验，又避免用户设置超过 Provider 实际限制。关键词检索先于向量数据库，符合 DEC-016 并降低当前复杂度。
- 影响：后续 Context Builder 需要 TokenEstimator、预算策略、工具链分组、ContextSnapshot 与默认脱敏调试信息。未来摘要持久化需记录 Conversation、覆盖的 Message sequence 区间、策略版本和 READY 状态，并对同一 Conversation 压缩串行化；摘要不可用时保留最近完整单元。User Memory 必须支持确认、来源、编辑和删除。跨 Conversation 检索默认不扫描全部历史，排除内部运行材料，并按用户范围、相关度、数量与 Token 预算过滤。
- 替代方案：按模型名字硬编码上下文窗口；让摘要后台直接改写正在使用的消息；压缩时删除 SQLite 原始历史；把摘要直接写成 User Memory 或 Skill；每次请求无范围检索全部 Conversation；一开始引入向量数据库；当前均不采用。

### DEC-059：模型窗口能力面向用户自动解析，自定义模型才高级配置

- 日期：2026-08-10
- 状态：已确认
- 背景：Context Builder 必须知道模型 context window 才能保证请求不超限，但将 `context_window_tokens` 作为每个普通用户 Provider Profile 的必填字段，会把内部 Token 概念和厂商细节推给用户，造成脆弱且不友好的配置体验。
- 决策：模型窗口仍是独立于用户 ContextBudget 的硬能力，但最终产品通过模型能力解析层为已知模型自动提供经维护的能力数据；用户选择标准模型时不填写窗口。只有自定义端点、未知模型或用户主动覆盖时，设置界面才显示高级窗口配置并解释其影响。当前没有模型目录或设置 UI，`ContextBuilder` 因而保持为 AgentLoop 的可选注入，阶段 4 先进行真实 Provider 人工体验，不把未完成的能力目录和配置流程提前塞入 Profile。
- 原因：保留硬上限与用户策略分离的安全边界，同时让常见模型选择保持简单；明确的高级回退路径优于按模型名临时猜测，也避免现在把短期开发 TOML 固化为最终产品交互。
- 影响：后续模型选择/设置功能需提供能力目录、版本维护和自定义覆盖；组合根只从已解析能力构造 ContextBuilder。当前真实 CLI 继续兼容未注入 Builder 的路径，开发期如需专门验证裁剪，可使用显式、文档化的测试配置，而不冒充自动识别。
- 替代方案：要求所有 Profile 必填窗口、按模型名称散落硬编码数字、无窗口保护地永远发送完整历史，或让用户输入预算直接突破模型上限；当前均不采用。

### DEC-060：可撤回文件变更以持久化 FileChange、快照和哈希冲突检测为前置条件

- 日期：2026-08-11
- 状态：已确认
- 背景：create-only 的 `filesystem.write_file` 不会修改既有文件，但未来覆盖、追加和删除都会产生不可逆或难以恢复的用户数据变化。只在工具结果或 RunEvent 中记录操作不足以恢复正文；无条件恢复旧内容又可能覆盖用户或其他程序之后的修改。
- 决策：在引入覆盖、追加或删除前，先建立持久化 `FileChange` 生命周期。每项变更记录稳定 `change_id`、来源 `run_id`、规范化 `root_path` 与相对路径、`CREATE`/`REPLACE`/`DELETE` 种类、变更前后 SHA-256、可选快照引用及 `PREPARED`、`APPLIED`、`REVERTED`、`CONFLICTED` 状态。变更前先把需要恢复的正文快照保存到 `AppPaths.data_dir` 的私有快照目录，再持久化 `PREPARED`；文件操作完成并校验结果哈希后才标记 `APPLIED`。SQLite 只保存元数据和相对快照引用，不保存文件正文。撤回只处理 asAgent 自己记录的 APPLIED 变更：CREATE 仅删除仍等于 after hash 的文件，REPLACE 仅在当前仍等于 after hash 时以同目录临时文件原子恢复快照，DELETE 仅在目标仍不存在时以独占创建恢复快照；任何不匹配均拒绝并标记/报告冲突。
- 原因：PREPARED/APPLIED 让崩溃恢复可以根据磁盘状态处理而不猜测；哈希比较保护用户后续修改；快照位于应用私有数据目录使 SQLite 保持轻量，且不把正文泄漏至 RunEvent、ToolCall、日志、模型上下文或 Git。保存 root path 与相对路径可精确定位多授权根中的目标；根移动后不搜索猜测，只报告不可恢复。
- 影响：初版单快照最多 5 MiB、总快照预算 100 MiB、默认保留 30 天。超过预算时拒绝需要新快照的变更，不静默删除仍可撤回的备份；清理只处理过期且已完成或已撤回记录。撤回本身仍需 `filesystem.write` 与逐次批准。create-only 可在该机制完成后纳入 FileChange，支持删除仍未被后续修改的 Agent 新建文件；当前 create-only Tool 不因此获得覆盖、追加、删除或撤回能力。快照加密与系统 Keychain 的结合留待正式设置/桌面存储设计。
- 替代方案：直接覆盖后依赖用户手动备份、将完整正文存入 SQLite/RunEvent、无条件恢复旧文件、按路径搜索移动后的 Workspace、或静默删除旧快照腾出空间；当前均不采用。

### DEC-061：阶段 6 使用 FastAPI App Factory 建立最小 Local API

- 日期：2026-08-11
- 状态：已确认
- 背景：桌面 Renderer 和未来本地 API 客户端需要稳定 HTTP 边界，但直接在 CLI 或 Runtime 中绑定端口会使测试、认证、启动生命周期和 Electron 集成纠缠在一起。阶段 6 的第一步应先验证版本化 HTTP 契约，而不启动完整服务。
- 决策：锁定 FastAPI 为 Local API 框架，并以 `api.app.create_app()` 创建应用。首个端点为无需认证的 `GET /api/v1/health`，固定返回最小 liveness 状态；使用 HTTPX ASGITransport 进行进程内契约测试。App Factory 不创建 SQLite、Runtime、模型 Client、工具或后台任务，也不自行绑定 socket。
- 原因：App Factory 让 API 路由可在不打开端口的测试中验证，并为后续显式依赖注入、认证、中间件与 Server 生命周期留下单一组合边界；最小健康检查可供未来 Electron 启动握手使用，又不会把业务状态误报为就绪。
- 影响：`fastapi` 成为运行依赖，Pydantic 继续只用于系统边界。后续独立任务再引入 Uvicorn、host/port 参数、仅监听 `127.0.0.1`、Token Bootstrap、Origin/CORS、Conversation/Run API 与 fetch-based SSE；Health 是否最终免认证由 Bootstrap 设计确认。
- 替代方案：在 CLI 中手写 HTTP Server、先绑定固定端口再补路由、让 Health 启动完整 Runtime/真实 Provider，或第一步就引入认证/SSE；当前均不采用。

### DEC-062：本地 API 使用一次性 stdin Bootstrap Token 并认证 Health

- 日期：2026-08-11
- 状态：已确认
- 背景：仅绑定 `127.0.0.1` 不能阻止同一设备上的其他进程请求本地 API；而把 Token 放入命令行、URL、配置、SQLite 或 ready 输出都会扩大 Secret 暴露面。当前还没有 Electron Main，但阶段 6 需要先固定可测试的 Backend 认证契约。
- 决策：每次 Backend 启动使用一个随机、仅内存存在的 `LocalApiToken`。开发 `serve` 命令只在显式 `--bootstrap-stdin` 模式下，从 stdin 读取一次 JSON Bootstrap 记录中的 Token；命令行参数与 `ASAGENT_READY` JSON 均不包含 Secret。App Factory 显式接收 Token，所有当前 API 路由（包括 Health）经 Bearer Header 认证；缺失、格式错误或错误 Token 均返回相同的 401 与 `WWW-Authenticate: Bearer`，比较使用常量时间函数。Token 不持久化、不记录日志，进程结束即失效。
- 原因：一次性 stdin 管道与未来 Electron Main 持有的子进程 stdin 自然对应，避免开发期先引入环境变量或命令行 Secret；先保护 Health 使启动握手也必须证明调用方拥有本次启动能力。
- 影响：源码开发需向 stdin 提供 Bootstrap JSON 后才能运行 `serve`；未来 Electron Main 负责生成随机 Token、写入自己的 Backend 子进程 stdin，并仅在 Main/Backend/当前 Renderer 内存中保存。CORS/Origin、Conversation/Run 路由、SSE、Token 轮换、Shutdown Endpoint 和 Electron 的进程管道管理仍是后续独立任务。
- 替代方案：Health 永久免认证、固定或持久化 Token、通过 `--token` 传参、将 Token 放入 ready JSON/URL、或仅依赖回环地址；当前均不采用。

### DEC-062 实施补充：Token 保持在 Main，Renderer 使用固定能力

- 日期：2026-08-11
- 状态：已确认
- 决策：Electron 开发 Sidecar 的启动 Token 仅存在于 Python Backend 与 Electron Main。`BackendLauncher` 可使用该私有连接实现固定的最小业务操作；Renderer 只经来源校验的 Preload/Main IPC 调用允许的操作，不获得 Token、端口、通用 HTTP 或任意 URL 访问能力。
- 原因：既能让桌面界面读取真实本地数据，又不把 Renderer 变成可滥用本地 API 能力的持有者；固定调用也避免为单一调用者增加通用客户端或 IPC 代理层。
- 影响：当前固定操作为 Conversation 列表与指定 Conversation 的 Message 历史读取。创建、提交、Run 查询、取消和 SSE 将在各自独立任务中按同一原则增加，且每项都需经过来源校验。
- 替代方案：将 Token/端口交给 Renderer、暴露通用 fetch 或 `ipcRenderer.invoke(channel, payload)` 转发器；当前均不采用。

### DEC-062 实施补充：真实 Provider 仅通过显式桌面开发入口启用

- 日期：2026-08-11
- 状态：已确认
- 决策：`npm run dev` 保持离线 `development-tools` 默认值；`npm run dev:deepseek` 才传入 `ASAGENT_DESKTOP_PROFILE` 与 `ASAGENT_DESKTOP_SECRET_ENV` 两个非敏感名称。Electron Main 将 Profile、Secret 环境变量名与仓库 `.env` 路径作为 Sidecar 启动配置，Python `serve` 使用既有 Profile/Secret/Provider 组合根创建真实持久化 Runtime，并保持 HTTP Client 至 Sidecar 关闭。实际 API Key 不作为 Electron 参数、IPC 数据或 Renderer 状态出现。
- 原因：真实模型体验应复用已经验证的 API、Run、SSE 和工具路径，同时离线 UI 开发与自动化测试必须稳定、无网络成本且不依赖用户 Secret。
- 影响：源码开发期需要用户自行维护被 Git 忽略的 `.env` 与非敏感 `providers.toml`；配置或调用错误明确失败，绝不静默回退离线模型。系统 Keychain、设置页与发行版 Sidecar 配置属于后续独立任务。
- 替代方案：让默认开发入口总是调用真实模型、将 Key 传入 Renderer/Preload、或在 Electron 中自行调用模型服务；当前均不采用。

### DEC-062 实施补充：Privacy 披露由安全处理模式驱动

- 日期：2026-08-11
- 状态：已确认
- 决策：Electron Main 只向 Renderer 的 App Info 暴露 `local` 或 `external` 的处理模式。此模式由当前 Sidecar 启动配置决定；Renderer 以它切换顶栏与 Privacy 文案，说明离线模式不会外发对话内容，或真实 Provider 模式可能向选定服务商发送请求所需内容及工具结果。
- 原因：固定“所有内容均在设备内处理”的文案会在真实 Provider 模式下误导用户。最小处理模式足以让披露真实，又不会泄露 Profile、端口、Token、API Key 或开放通用配置通道。
- 影响：Privacy 页的权限编辑、历史审计和外发字节计数仍未实现；本次只保证当前模型调用边界的准确披露。
- 替代方案：始终显示本地处理、把具体 Provider/密钥交给 Renderer、或等完整设置页完成后再纠正文案；当前均不采用。

### DEC-062 实施补充：会话标题由首条消息确定性生成

- 日期：2026-08-11
- 状态：已确认
- 决策：Conversation 保存可空 `title`。创建 API 继续拒绝请求体中的 `title`；首次提交用户消息时，提交服务将文本规范化并截断至 60 个字符生成标题，已有标题永不自动覆盖。标题更新、Conversation `updated_at`、UserMessage 与 CREATED Run 通过既有 RunStarter 在同一 SQLite 事务中写入。
- 原因：侧栏需要即时、稳定且零模型成本的可读标签；原子写入避免“消息/Run 已创建但标题未更新”的部分成功状态，并且不为标题专门引入新的 API、后台模型调用或编辑工作流。
- 影响：历史 Conversation 的 `title` 可以为 null，桌面显示 `New conversation`。未来手动改名或模型摘要标题必须以独立的明确操作覆盖该字段，不能改变当前自动生成语义。
- 补充：`ConversationRepository.list_for_user()` 以 `updated_at` 倒序、`conversation_id` 倒序提供稳定的最近活跃排序；提交服务在写入初始 Message/Run 时同步更新时间，桌面以同一规则立即重排本地列表。
- 替代方案：创建时由客户端提供 title、每轮消息重写标题、用模型异步生成摘要标题、或仅在桌面内保留未持久化标题；当前均不采用。

### DEC-062 实施补充：仅安全渲染 Assistant Markdown

- 日期：2026-08-11
- 状态：已确认
- 决策：桌面 Renderer 只将 AssistantMessage 的文本作为 Markdown 显示，UserMessage 继续原样呈现。解析不启用原始 HTML 或危险 DOM 注入；消息存储和 Local API 保留模型返回的原始文本。
- 原因：模型自然倾向使用 Markdown 组织回答，原样显示会降低列表和代码示例的可读性；同时模型输出不应被信任为可执行 HTML。
- 影响：支持常见文本 Markdown 和代码块显示，但不在本任务引入 HTML、脚本、富文本编辑、代码高亮或链接预览。
- 替代方案：全局 Prompt 禁止 Markdown、对所有用户/模型文本使用 `dangerouslySetInnerHTML`、或在后端将 Markdown 转为 HTML；当前均不采用。

### DEC-062 实施补充：固定写入操作沿用 Main 私有 Token

- 日期：2026-08-11
- 状态：已确认
- 决策：创建空 Conversation 与提交非空 Message 同样只由 `BackendLauncher` 经 Main 持有的私有 Token 请求；Main 先验证来自受信任 Renderer 的参数，Preload 只暴露两个具名方法。提交后 Renderer 只消费 API 返回的用户 Message，不把后台 Run 的执行、状态轮询或 SSE 混入本次写入操作。
- 原因：这让用户可以真实开始对话，同时把一次 HTTP 提交与后续异步 Run 观察明确分开，避免先引入通用 IPC/HTTP 转发器或半成品轮询器。
- 影响：UI 可以显示“已提交、等待响应”，刷新或重新选择 Conversation 后才能读取已持久化的助手回答。下一项应独立接入 Run 状态与 SSE，而不是在提交函数中等待模型。
- 替代方案：Renderer 直接持有 Token、提交 HTTP 请求同步等待最终模型回答、或在本次引入通用后台轮询；当前均不采用。

### DEC-062 实施补充：实时 Run 事件经 Main 解析并作为临时对话 Activity 显示

- 日期：2026-08-11
- 状态：已确认
- 决策：Main 持有每次提交 Run 的认证 SSE 连接并解析事件帧；Preload 只暴露具名 Run 更新订阅和取消操作。Renderer 将当前 Run 的安全事件显示为临时 Activity 卡片，收到终态后重新读取用户可见 Message 历史；不把内部 RunEvent 变成持久化聊天消息。
- 原因：离线工具 Run 往往在毫秒级完成，单行瞬时状态会被最终状态覆盖；保留 Activity 既使实际执行过程可见，又保持 Message、RunEvent 和模型上下文的既有分离。
- 影响：刷新后的历史只显示持久化 User/Assistant Message；调试、审计和 SSE 续传仍以 SQLite RunEvent 为准。Activity 的展示不增加 Renderer 的 HTTP、Token 或通用 IPC 权限。
- 替代方案：把所有事件写成 AssistantMessage、Renderer 直接连接 SSE、或仅显示最后一个状态；当前均不采用。

### DEC-063：以独立生命周期和失败语义控制抽象粒度

- 日期：2026-08-11
- 状态：已确认
- 背景：asAgent 同时承担学习与产品开发。随着 Submission、Runtime、Dispatcher 等组件出现，过度拆分“仅转发一次调用”的薄包装层会使数据流更难理解、测试夹具膨胀，且延迟真实体验；反过来，把原子提交、后台生命周期和模型/工具执行混在一个入口中又会掩盖取消、失败持久化和 UI 观察责任。
- 决策：这是一条全项目约定，适用于 Python Core、Local API、Electron Main/Preload/Renderer、构建和测试。只在对象拥有独立调用者、生命周期、失败处理或可验证业务规则之一时新增边界。在职责、调用者和生命周期仍紧密一致时，相关实现、辅助函数和针对性测试优先留在同一文件；只有独立职责、独立生命周期、明显的可读性收益或实际文件规模要求时才拆分。当前 Run 路径保持 Submission Service（原子创建）、PersistentAgentRuntime（模型/工具执行与终态）和 Dispatcher（后台 Task/协作式取消/清理）三层；“只包一层 Runtime、没有独立调用者或规则”的 PersistentRunExecutor 不实现。意外执行异常的 FAILED 终态属于 Runtime 的执行责任，而不是新增包装器。已验证的现有模块保持不动，除非真实问题或新范围使其需要改变。
- 原因：三层分别对应 API/CLI 提交、Agent 执行和后台生命周期，具有可独立测试的失败模式；薄包装器或为“文件整齐”而拆出的微型模块，不能改善替换性、可观察性或可读性时只会增加认知成本。
- 影响：后续设计需先写清数据流与失败归属，再决定是否新增 Protocol、Service、Adapter、前端 store、React hook、IPC Bridge 或组件层。优先实现最小可体验闭环；Provider、SSE、桌面和未来多进程需求出现前，不为假设场景预建层次。该约定指导未来增量，不作为对既有已验证代码的重构命令。
- 替代方案：把所有逻辑塞入 FastAPI 路由或 Runtime；为每一步都建立 Service/Executor/Adapter/Protocol 包装；当前均不采用。

### DEC-064：首个桌面产品界面统一使用英文

- 日期：2026-08-11
- 状态：已确认
- 背景：桌面客户端开始形成用户可见界面。若在同一产品表面临时混用中文、英文或其他语言，会降低一致性，也会在尚未设计翻译资源、回退语言和布局适配前形成难以维护的伪国际化。
- 决策：所有用户可见的 asAgent 产品 UI 文案统一使用英文，包括 Renderer、原生桌面窗口、设置、审批和错误提示。开发文档、代码注释、测试、日志和与开发者的协作语言不受限制。当前不实现语言选择、翻译资源或本地化框架；未来需要多语言时，先单独设计完整国际化策略，再统一迁移。
- 原因：英文单语言表面让首个桌面版本保持一致并避免过早引入 i18n 基础设施；同时保留未来以完整策略替换的明确边界。
- 影响：后续任何界面任务都以英文编写和验收用户可见文本，不得在单个页面或错误路径混入其他自然语言。此规则不要求回溯翻译 CLI、开发工具输出或项目文档。
- 替代方案：按开发者当前输入语言临时混用、现在建立未使用的多语言框架、或将界面语言视为每个组件的独立选择；当前均不采用。

### DEC-065：MCP 采用现代优先、隔离旧版回退的协议策略

- 日期：2026-08-11
- 状态：已确认
- 背景：路线图原先以 `initialize` / `notifications/initialized` 为 MCP 生命周期学习入口；
  MCP `2026-07-28` 已改为无会话核心，以可选 `server/discover` 与每请求 `_meta` 承载
  协议版本、Client 身份和能力。只实现旧生命周期会让新项目立即落后；只实现现代协议
  又会使仍广泛存在的旧 stdio Server 无法接入。
- 决策：asAgent 的 MCP Client 以 `2026-07-28` 为首选协议。对于未知 stdio Server，先在
  有界超时内进行现代 `server/discover` 探测；确认现代支持后，后续请求使用每请求元数据。
  若 Server 明确不支持、返回方法不存在或探测超时，则关闭探测子进程，并使用全新子进程
  走旧版 `initialize` / `notifications/initialized` 生命周期。可以由配置固定某一协议，
  但默认不把旧协议当作首选。
- 原因：现代优先使新功能基于当前规范；独立进程回退避免未知请求污染、卡死或破坏旧 Server
  的正式 stdin/stdout 会话；协议差异被收敛在 McpClient，不渗透到 AgentLoop、ToolExecutor
  或模型 Provider。
- 影响：首个测试 Server 只验证现代协议；随后 McpClient 负责现代发现、请求元数据、超时和
  旧版 fallback。上层仍只消费统一的 ToolDefinition 与 Tool 结果。测试必须覆盖现代成功、
  旧版 fallback 和不兼容/超时隔离。此前路线图中把旧握手描述为默认 MCP 流程的内容由本决策
  替代。
- 替代方案：锁定 `2025-11-25` 及以前的旧生命周期；只支持 `2026-07-28` 而拒绝旧 Server；
  在同一已探测 stdio 子进程内直接发送旧版 initialize；当前均不采用。

### DEC-066：桌面端采用内存中的逐次工具审批闭环

- 日期：2026-08-12
- 状态：已确认
- 背景：MCP Tool 已统一声明 `requires_approval=True`，但真实桌面入口尚不能把用户的单次 Allow/Deny 决定可靠地送回正在等待的 Python ToolExecutor。将 Token 交给 Renderer 或让 CLI 读取输入都会破坏既有桌面安全边界与产品入口。
- 决策：每次需要审批的调用使用不可变 `ToolApprovalRequest`，包含一次性 `approval_id`、Run、Conversation、模型 Tool Call、ToolDefinition 和参数。`PendingToolApprovalPolicy` 只在内存中保存未决定请求；它登记成功后才发出安全元数据 `tool.approval_requested` 事件并等待决定。Local API 以 Bearer 认证提供读取待处理请求和提交决定的端点；Electron Main 持有 Token 并转发受信任 Renderer 的具名 IPC，Renderer 在对话中展示英文审批卡片。取消 Run、关闭 Sidecar 或重复/过期决定均拒绝并解除等待。
- 原因：一次性内存请求足以完成首次真实 MCP 体验，又能保证 UI 不会为无效参数或未获权限的调用弹窗；Main 继续是唯一可访问本地 HTTP Token 的桌面进程，且审批本身不污染用户可见消息或持久化 RunEvent 正文。
- 影响：当前审批不具备刷新恢复、长期授权、审批历史或审计持久化；未来这些能力必须单独设计数据最小化、范围、有效期与撤销规则。配置的 MCP Server 尚未自动进入 Runtime，本决策只提供其可安全使用的用户确认通道。
- 替代方案：Renderer 直接访问本地 API、CLI stdin 审批、只按固定风险等级自动批准、或将审批结果和完整参数写入 RunEvent；当前均不采用。

### DEC-067：Sidecar 以最小环境原子导入配置的 MCP Server

- 日期：2026-08-12
- 状态：已确认
- 背景：`mcp.json` 已能表达非敏感的 stdio Server，但若 MCP 子进程默认继承 Sidecar 全部环境，真实 Provider 的 API Key 或本地 API Token 可能泄露给任意已配置 Server；若逐个直接注册工具，后续 Server 启动失败还会使 Runtime 留下不可用工具。
- 决策：仅 `asagent serve` 在构造 Runtime 前读取可选 `config_dir/mcp.json` 并启动 `McpServerManager`。Manager 仍先以临时 Registry 导入全部工具，成功后才合并到内置 ToolRegistry；缺失配置保持内置工具路径，非空配置只在全部 Server 成功后向该 Runtime 授予 `mcp.execute`。`McpClient` 默认传递空环境，Sidecar 只显式允许 `PATH` 给 MCP 子进程。启动失败不得输出 ready 记录，关闭时在数据库关闭前关闭 Manager 与子进程；`mcp.json` 改动需重启 Sidecar 才会生效。
- 原因：这让模型只看到一次启动时已经可用的工具快照，同时防止 Secret 随进程环境隐式扩散；全量成功后再合并保持现有 Manager 的原子导入语义。
- 影响：MCP Server 不获得模型 API Key、Local API Token 或任意 `.env` 值，也不自动继承本地文件、浏览器或 OAuth 范围。需要凭据的 Server 必须等待独立 Secret Store 引用设计。当前持久化 CLI、设置页、热刷新、重连、分页和 legacy fallback 不因此实现。
- 替代方案：继承完整宿主环境、将 Token/环境值放入 `mcp.json`、逐个 Server 成功即向 Runtime 注册、或允许 Renderer 直接启动 Server；当前均不采用。

### DEC-068：工具审批按会话与内部 tool_id 授权，而不是全局布尔值

- 日期：2026-08-12
- 状态：已确认
- 背景：首次桌面审批只有 Allow/Deny 布尔值，无法表达“本会话连续使用同一 MCP 工具”。若做成全局记住，会把 Gmail 搜索与发信、或不同 Server 的同名工具混成一次授权。
- 决策：审批决定改为 `deny`、`allow_once`、`allow_conversation` 三种。会话授权键为 `(conversation_id, definition.tool_id)`；MCP 的内部 ID 已包含 Server、工具名和 Schema Hash，因此不同 Server、不同工具或接口版本不会共用授权。`allow_once` 只放行当前调用；`allow_conversation` 写入 Sidecar 内存 grants，后续同键调用不再弹窗。grants 不持久化，Sidecar `aclose()` 时清空。Local API、Main 与 Renderer 传递字符串 `decision`，不再使用 `approved: bool`。
- 原因：这保持一次性确认的安全默认，又让同一对话里重复使用同一工具不必连点；授权范围仍然小于全局或跨会话记住。
- 影响：换 Conversation、重启 Sidecar、更换工具或 Schema 后仍需批准。Renderer 横幅提供 `Deny`、`Allow for this conversation`（次级）和 `Allow once`（主按钮）。长期授权、撤销 UI、审批历史和审计仍需单独设计。
- 替代方案：全局布尔记住、按 Server 记住全部工具、把 grants 写入 SQLite、或继续只用 Allow/Deny；当前均不采用。

### DEC-069：专用集成工作区使用账户范围的持久偏好，不复用 Chat 授权

- 日期：2026-08-12
- 状态：已确认，留待 Gmail OAuth/Secret Store/专用 UI 阶段实现
- 背景：用户从 Chat 请求工具与从专用 Email 页面管理已连接邮箱是两种意图。若只用 Conversation grant，专用页面会重复弹窗；若把 OAuth 连接或 Chat grant 解释为全局许可，又会把不同账户、入口与高副作用邮件操作混为一谈。
- 决策：未来授权上下文至少区分 `interaction_surface`、账户/资源范围、OAuth scope、内部 `tool_id` 与操作风险。Email 工作区可在用户明确设置后，对指定账户的低风险只读工具自动执行；Chat 仍使用临时会话级授权。OAuth 连接只证明第三方允许 asAgent 访问，不代表模型可自动使用该能力。发送、删除、修改规则、范围扩大等操作即使来自专用页面仍保留逐次确认或默认拒绝。
- 原因：专用工作区应减少符合用户预期的只读重复确认，同时把账户、入口和副作用保留为可解释、可撤销的边界。
- 影响：该策略需要未来持久化设置与撤销 UI，并与 Gmail OAuth、Secret Store、风险覆盖策略一起设计；不在当前 `PendingToolApprovalPolicy`、`mcp.json` 或会话授权任务中预建数据库表、设置页面或凭据注入。
- 替代方案：OAuth 成功即全局自动允许、所有入口都只按 Conversation grant、或所有 Email 操作永久逐次弹窗；当前均不采用。

### DEC-070：外部连接元数据与系统凭据存储分离

- 日期：2026-08-12
- 状态：已确认并完成最小 macOS 实现
- 背景：Gmail、GitHub、Calendar 和其他 MCP Server 可能需要 OAuth refresh token、API Key 或其他 credential。把这些值放入 SQLite、`mcp.json`、`.env` 或 Sidecar 环境会使备份、日志、子进程继承和普通配置读取扩大 Secret 暴露面；但仅有 `SecretProvider.get_secret()` 又不足以表达连接的保存、替换、撤销和账户范围。
- 决策：新增通用 `Connection`，在 SQLite 只持久化 `connection_id`、用户、服务标识、账户显示名、scope、状态和时间；新增 Core `CredentialStore`，只以 `connection_id` 保存、读取和删除不透明 credential。首个生产适配器是 macOS `MacOSKeychainCredentialStore`，使用系统 Keychain；Windows Credential Manager 和 Linux Secret Service 以后实现同一 Protocol。未支持的平台必须明确失败，不能退回到文件、SQLite 或环境变量。断开连接的未来组合操作必须同时删除 CredentialStore 条目和 Connection 元数据。
- 原因：连接生命周期与凭据载体从具体 OAuth/MCP 服务中解耦；任一服务专属 Connector 只需负责登录、刷新及账户信息解析，随后复用同一安全存储和撤销路径。
- 影响：本次没有 Gmail OAuth、刷新逻辑、Provider Keychain 接入、MCP 子进程 Secret 注入、Connection API 或桌面设置页。`mcp.json` 继续禁止 Secret，McpClient 继续只接收显式最小环境；下一项必须设计非敏感 connection reference 如何被组合根解析为仅对目标 Server 可用的凭据。
- 替代方案：每个服务各自维护 token 文件、让所有 MCP 子进程继承完整 Sidecar 环境、把 token 写入 `mcp.json`，或将 macOS 实现伪装为跨平台支持；当前均不采用。

## 2. 技术选型

阶段 0 直接相关的技术选型已由 DEC-022 锁定；后续阶段的待定项仍在对应阶段开始前确认：

| 项目 | 方案 | 状态 |
| --- | --- | --- |
| Python | `>=3.13,<3.14`，`.python-version` 使用 `3.13` | 已确认 |
| Python 包管理 | uv，提交 `uv.lock` | 已确认 |
| 数据验证 | Pydantic `>=2,<3`，主要用于系统边界 | 已确认 |
| API | FastAPI | 已确认，阶段 6 引入 |
| ASGI Server | Uvicorn，`Config` / `Server` 生命周期 | 已确认，阶段 6 引入 |
| 数据库 | SQLite | 已确认 |
| 数据库访问 | SQLAlchemy `[asyncio]` extra、`>=2.0,<2.1` Core，不使用 ORM | 已确认 |
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
- 当前决定：asAgent 位于独立目录 `/Users/yuting/Desktop/BityDev/asAgent`；此前的 Ragent 目录重命名是历史记录，最终名称以 DEC-027 为准。
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
