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
