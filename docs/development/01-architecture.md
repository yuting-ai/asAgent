# asAgent 目标架构

## 1. 架构目标

asAgent 采用模块化单体。所有后端能力在一个 Python 应用中运行，但模块边界明确，允许独立测试和替换边缘实现。

目标不是建立最多的抽象，而是保证以下关系清楚：

- 输入入口与 Agent Core 分离。
- Conversation 与单次 Run 分离。
- 用户消息与内部事件分离。
- 模型选择工具与工具实际执行分离。
- 长期状态与运行时对象分离。
- 程序资源与用户可写数据分离。
- Electron、Docker 和源码运行共享同一个 Python Core。

asAgent 的架构必须能够独立成立。`/Users/yuting/Desktop/BityDev/CowAgent` 只是在用户许可下用于比较具体实现的外部参考目录，不出现在 asAgent 的 import path、包依赖、启动参数、构建输入或运行时查找路径中。

## 2. 总体结构

```text
Electron / CLI / Future Channel
              │
              ▼
          Chat Service
              │
              ▼
          Agent Runtime
    ┌─────────┼──────────┐
    ▼         ▼          ▼
Context     Model      Tools
Builder     Gateway    Registry/Executor
    │         │          │
    └─────────┼──────────┘
              ▼
       Events + Repositories
       ┌──────┼─────────┐
       ▼      ▼         ▼
    SQLite  Memory   Workspace
```

## 3. 建议目录

```text
asAgent/
├── AGENTS.md
├── pyproject.toml
├── src/
│   └── asagent/
│       ├── core/                 # ID、消息、事件、错误和基础接口
│       ├── chat/                 # Conversation、Message、ChatService
│       ├── agent/                # Runtime、Agent Loop、Context Builder
│       ├── models/               # 模型 Provider
│       ├── tools/                # Registry、Executor、Policy、内置工具、MCP
│       ├── memory/               # 摘要、个人记忆、检索
│       ├── workspace/            # WorkspaceResolver、作用域和权限
│       ├── storage/              # Repository 实现；阶段 1 内存适配器，阶段 3 SQLite 与迁移
│       ├── api/                  # FastAPI、本地 HTTP、SSE
│       ├── paths.py              # AppPaths：所有运行方式共享的路径契约
│       └── app.py                # 组合依赖和启动应用
├── desktop/                      # Electron + React + TypeScript
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── replay/
├── docker/
├── docs/
│   ├── development/
│   └── learning-notes/
└── scripts/
```

`core` 不依赖 FastAPI、Electron、SQLite SDK 或任何模型厂商 SDK。依赖方向由外向内，具体实现通过构造函数注入。

阶段 6 的 Local API 从 `api.app.create_app(access_token=..., conversations=..., runs=..., run_submission=..., dispatch_submitted_run=..., cancel_run=...)` 开始。App Factory 只依赖注入的 Core `ConversationRepository`、`RunRepository`、应用层 `RunSubmissionService` 和已提交 Run 的调度/取消回调；它不创建数据库连接、Agent Runtime、模型 Client、文件工具或后台任务。当前 `GET /api/v1/health` 返回最小 liveness JSON；`GET /api/v1/conversations` 仅查询固定 `local-user` 的 Conversation 元数据（稳定身份和创建/更新时间）；`POST /api/v1/conversations` 只接受空 JSON object，拒绝未知字段，服务端生成 Conversation ID 和 UTC 创建/更新时间，为 `local-user` 保存没有 Message 或 Run 的 Conversation，并返回 201；`POST /api/v1/conversations/{conversation_id}/messages` 验证非空、非纯空白且无未知字段的文本，调用 Submission Service 原子创建 UserMessage 与 CREATED Run，再交给注入的 Dispatcher 创建后台执行，并立即返回两者的稳定身份和创建时状态。`GET /api/v1/runs/{run_id}` 先读 Run，再经所属 Conversation 确认属于 `local-user`，返回稳定 Run 身份、完整 `RunStatus` 与创建/更新时间；未知或其他用户归属统一 404，不返回事件或 ToolCall。`POST /api/v1/runs/{run_id}/cancel` 先执行同一归属检查，再仅向注入的 Dispatcher 请求协作取消；活跃 Run 返回 202，非活跃 Run 返回 409，最终 `cancelled` 状态仍由 Runtime 在安全检查点持久化。`GET /api/v1/runs/{run_id}/events` 在相同归属检查后以 `text/event-stream` 按 `sequence` 回放持久化 `RunEvent`，并以查询参数 `after_sequence`（`>=0`）续传；对活跃 Run 在 Repository 短轮询直到终态或客户端断开，SSE 帧的 `id` 使用事件 `sequence`。`GET /api/v1/conversations/{conversation_id}/messages` 先确认该 Conversation 存在且属于 `local-user`，再按持久化的 Conversation 内 sequence 返回用户可见的 USER/ASSISTANT message 身份、角色、正文与时间；未知或其他用户 Conversation 统一为 404，且这些路由都不返回 user_id、内部事件或 ToolCall。`api.auth.LocalApiToken` 只在内存中保存本次启动的随机 Token，`BearerTokenAuthenticator` 以常量时间比较验证每个当前 API 请求；缺失、格式错误或不匹配的凭据统一返回 401，Health 也不再例外。`api.bootstrap.read_local_api_token()` 从一次 JSON Bootstrap 记录取得 Token，既不把它写入配置/SQLite/日志，也不放进 ready 记录。`api.server.LocalApiServer` 是独立的 Uvicorn 生命周期封装：它只接受 `127.0.0.1`，由 Backend 先绑定端口（允许 `0` 的系统分配）再交给 Uvicorn，并在实际服务启动后产生含 host、port、PID 和协议版本的 `ServerReady`。开发 CLI 的 `asagent serve --bootstrap-stdin --app-home <root> --port 0` 从 stdin 读取该记录，启动或升级 `<root>/data/asagent.sqlite3`，组合 SQLite Repository/Starter/Finisher、离线 `development-tools` Runtime 和 InProcess Dispatcher，随后以 `ASAGENT_READY ` 前缀立即刷新输出不含 Token 的 JSON。服务关闭时先关闭 Dispatcher，再关闭 Finisher、Starter 与 Repository，避免活跃任务访问已关闭 SQLite。阶段 7 的 `desktop/src/main/backend_launcher.ts` 在开发模式拥有该 Python 子进程：它在 Main 内生成一次性 Token、经 stdin 写入 Bootstrap JSON，验证 stdout ready 记录的 loopback host、端口、PID 和协议版本，再以该 Token 轮询认证 Health；成功后才创建 BrowserWindow。Launcher 只暴露无敏感的 ready 状态给受来源校验的窄 Preload IPC，关闭时只终止自己持有的子进程。Renderer 仍没有 Token、端口、业务 HTTP 或 SSE 能力。Origin/CORS、Conversation 标题/编辑/删除、`Last-Event-ID` 兼容、真实 Provider 服务端配置与实际聊天 API 接入都保留给后续独立任务。

阶段 7 的后续只读接入已完成：`BackendLauncher` 以自身持有的 loopback endpoint 和仅 Main 可见的 Token 提供两个固定操作——列出 Conversation、读取指定 Conversation 的可见 Message。受来源校验的窄 Preload 只暴露这两个操作与无敏感的 Backend 状态；Renderer 没有 Token、端口、通用 HTTP、写入 API 或 SSE 能力。此前关于 Renderer 尚不能调用业务 API 的描述由此更新；提交 Message、Run 状态观察与 SSE 仍是后续独立任务。

Conversation 元数据现包含可空 `title`。创建 Conversation 的请求体仍严格为空对象；首次 `POST /api/v1/conversations/{conversation_id}/messages` 时，`RunSubmissionService` 将该用户文本规范化为空格分隔的单行，并生成至多 60 个字符的确定性标题（超出时以前 59 个字符加省略号表示）。已有标题不会被后续消息覆盖。更新后的 Conversation、首条 UserMessage 与 CREATED Run 由 `RunStarter` 在同一 SQLite 事务中提交，提交响应和列表响应均返回 `title`，Electron 侧栏立即以该响应更新显示。此标题不是模型生成摘要，也不是可编辑字段。

Conversation 列表按 `updated_at` 倒序、再按 `conversation_id` 倒序返回。首条或后续用户消息均会在与初始 Run 创建相同的事务中更新 Conversation 的 `updated_at`；Electron 在创建 Conversation 或提交 Message 后也按同一排序规则更新内存侧栏，无需刷新即可把最近活跃会话放在顶部。

阶段 7 的最小写入接入也已完成：同一 `BackendLauncher` 额外提供创建空 Conversation 与向指定 Conversation 提交非空 Message 的固定操作。Main 在调用前验证 IPC 参数，并继续检查 Renderer 来源；提交成功后 Renderer 仅显示 API 返回的 USER Message 和“等待响应”状态。运行中的 Run 仍未被 Renderer 查询或订阅，AssistantMessage 只会在后续手动重新读取历史时出现。

阶段 7 的实时观察现已通过 Main 私有的认证 fetch-based SSE 接入：提交返回的 `run_id` 只用于固定的 Main 生命周期管理，Main 将已解析的安全 RunEvent 经窄 Preload 推送给 Renderer；Renderer 不读取 SSE URL、Token 或端口。当前 UI 将本次 Run 的事件保留为临时 Activity 卡片，并在终态后重新读取用户可见 Message 历史以显示 AssistantMessage；Activity 不是持久化 Message，刷新后由已持久化的 RunEvent/Message 历史替代。Stop 只请求既有协作取消，最终状态仍以 RunEvent 为准。聊天布局将 composer 固定在窗口底部，只有消息区滚动。

阶段 7 的发布前 Sidecar 边界已自动化验证：`scripts/build_backend.py` 用 PyInstaller onedir 将 CLI、Alembic 配置和迁移脚本打包到 `desktop/build/dist/asagent-backend/`，并显式收集 `aiosqlite` 动态依赖。冻结 CLI 从 bundle 的 `sys._MEIPASS` 读取 Alembic 配置，运行时 SQLite 仍只由 `--app-home` 的 AppPaths 创建。`scripts/smoke_backend_bundle.py` 从独立临时目录启动该可执行文件，通过临时 stdin Token 验证 Health、会话创建与离线 Calculator 回合；它不依赖源码工作目录、不使用真实 Provider，也不改变 Electron 开发 Launcher。

## 4. 核心身份模型

### 4.1 ID 层级

```text
User
└── Conversation
    ├── Message
    └── Run
        └── ToolCall
```

| ID | 责任 |
| --- | --- |
| `user_id` | 用户身份，第一版固定为 `local-user` |
| `conversation_id` | 对话历史和上下文边界 |
| `message_id` | 一条用户可见 Message 的稳定身份，不承担排序职责 |
| `run_id` | 单次 Agent 执行、取消和事件关联键 |
| `tool_call_id` | 一次工具调用和结果配对键 |
| `event_id` | 运行事件的唯一标识和去重键 |

不要使用一个 `session_id` 同时承担这些职责。

事件顺序不依赖 `event_id` 或 `created_at`。每个 Run 另外维护从 1 开始单调递增的 `sequence`；数据库对 `(run_id, sequence)` 建立唯一约束。`event_id` 负责跨边界去重，`sequence` 负责回放排序和断线续传。

### 4.2 未来 Channel Identity

预留但暂不实现：

```python
class ChannelIdentity:
    channel: str
    external_user_id: str
    internal_user_id: str
```

外部 ID 通过映射关联内部 User，不直接充当 Conversation ID。

## 5. 状态模型

三种状态必须分开：

### 用户可见消息

```text
UserMessage
AssistantMessage
```

用于聊天界面和对话历史。

### 内部运行事件

```text
run.started
model.requested
model.delta
model.completed
tool.requested
tool.started
tool.progress
tool.completed
tool.failed
run.cancelled
run.limit_reached
run.completed
run.failed
```

用于流式 UI、审计、调试和回放。

阶段 0 的 `EventPublisher` 是异步 Core `Protocol`，只提供 `publish(event: RunEvent)`。它负责把运行时产生的事件交给后续的内存、持久化或 SSE 桥接实现；事件历史查询和回放仍由 `RunRepository` 负责，因此 Publisher 不提供查询或订阅方法。

### 模型上下文

发送给模型的标准化 Message 列表，可能包含摘要、历史文本、tool_use 和 tool_result。它是运行时材料，不等同于完整数据库历史。

## 6. Agent Runtime

Agent Runtime 按一次 `run_id` 执行，尽量不作为长期存活的有状态对象。

```text
RunRequest
→ 加载 Conversation
→ 构建上下文
→ 取得 Tool Snapshot
→ 调用模型
→ 解析文本或 ToolCall
→ 执行工具并追加 ToolResult
→ 重复直到结束、取消或达到上限
→ 保存最终消息和状态
```

Runtime 的核心依赖：

```python
class AgentRuntime:
    model: ModelProvider
    conversations: ConversationRepository
    runs: RunRepository
    tools: ToolRegistry
    executor: ToolExecutor
    events: EventPublisher
    context_builder: ContextBuilder
```

Runtime 不直接：

- 读取 Electron IPC。
- 操作 FastAPI Response。
- 创建 SQLite Connection。
- 读取具体模型厂商环境变量。
- 向某个渠道发送消息。

阶段 2 当前的 `agent.loop.AgentLoop` 是最小非流式编排器。它接收 `ModelProvider`、`ToolExecutor`、本次 Run 的 `ToolSnapshot` 和可选取消令牌，在内存中维护模型消息历史，并返回 `AgentLoopResult`。每次 `complete()` 响应消耗一个决策步骤，默认上限为 8；同一响应中的多个工具按稳定顺序执行但不额外消耗步骤。Provider 报告超时时，Loop 返回 `FAILED` 且不计入尚未取得响应的步骤。每次请求始终使用 Snapshot 导出的工具定义，工具结果再作为 TOOL message 进入下一次请求。可选 `ToolCallRecorder` 在已解析内部工具的调用结束后记录不可变 `ToolCall`：内部 `tool_call_id` 与模型 `model_call_id` 分离，原始成功结果不受模型上下文截断影响。若记录失败，Loop 停止后续调用并返回 `FAILED`。若注入 `EventPublisher`，调用方必须同时提供本次 `run_id`、`conversation_id`、事件 ID 工厂和时钟；Loop 从 1 递增发布事件。Publisher 未注入时保持无事件的最小执行；已注入但发布失败时，Loop 立即停止后续模型或工具调用并以 `FAILED` 返回。

阶段 3 的 `agent.run_submission.RunSubmissionService` 是“提交用户输入”这一应用层边界：它读取指定 Conversation，可选校验预期 `user_id`，生成 `UserMessage` 与 `CREATED` Run，并只通过 `RunStarter` 原子写入后返回不可变 `SubmittedRun`。未知 Conversation 与用户不可访问 Conversation 以不同的内部错误表达，入口可按其安全策略映射为同一外部响应；Starter 写入失败原样传播，不伪造成功。它不调用模型、不发布事件、不完成 Run，也不导入 SQLite 或 FastAPI。

`agent.persistent_runtime.PersistentAgentRuntime` 将提交与执行显式拆开：兼容入口 `run()` 先调用 Submission Service，再把结果委托给 `execute_submitted()`；后者只接受已有的 `SubmittedRun`，并只允许其中 Run 仍为 `CREATED`。它读取用户可见历史、转换为 ModelMessage 并调用预先配置的 `AgentLoop`；最后无论 Loop 成功、失败、取消或达到步骤限制，都用 `RunFinisher` 原子保存终态 Run。若读取历史或 Loop 出现未被其自身结果模型表达的意外 `Exception`，Runtime 会先尽力用同一 Finisher 写入无 AssistantMessage 的 `FAILED` Run，再原样传播异常给调用者；正常终态写入本身不放入该捕获范围，避免数据库故障被重复写入掩盖。仅 `COMPLETED` 且有最终文本时创建 AssistantMessage；`LIMIT_REACHED` 的文本可能来自未闭合工具回合，不能伪装为正常对话历史。Runtime 自己仅保留最终助手消息的 ID 工厂，避免 Service 同时负责两类消息身份。这个执行入口为后续 Dispatcher 消费 API 已提交 Run 提供边界，避免重复创建用户消息或 Run；它本身不调度后台 Task。SQLite 组合根负责把 `SqliteRunStarter`、`SqliteRunFinisher`、`RepositoryEventPublisher` 和 `RepositoryToolCallRecorder` 注入该链路。

最小 `agent.run_dispatcher.InProcessRunDispatcher` 是独立于 HTTP/SQLite/Provider 的进程内生命周期协调器：调用方提供“执行一个 SubmittedRun”的异步函数后，`dispatch()` 为该 Run 创建后台 Task 和同一 `run_id` 的 `RunCancellationToken`，并立即返回可等待 `RunDispatchHandle`。同一活跃 Run 不可重复调度；`cancel(run_id)` 仅设置协作式 Token 并报告是否找到活跃 Run，不强制取消协程。执行完成、协作式取消或执行函数抛出异常后，Dispatcher 都清理活跃 Token 与 Task；异常作为 `RunDispatchOutcome.error` 返回给 Handle，避免未取回的后台 Task 异常。`aclose()` 关闭 Dispatcher 后拒绝新调度，先对所有活跃 Token 请求协作取消，再在有限等待后强制取消仍未结束的 Task；组合根必须在关闭 SQLite 前调用它。Dispatcher 不读取模型消息，不决定是否/如何调用工具，也不持久化终态或调用 SSE；这些仍分别属于 Runtime、AgentLoop、ToolExecutor 和后续 API 观察层。

阶段 4 的 Context Builder 在每次模型调用前，从原始 Conversation、已确认的 Conversation Summary、用户记忆和本次工具 Snapshot 生成不可变 `ContextSnapshot`。Snapshot 明确记录模型本次实际可见的 system prompt、模型消息、工具定义、各组成部分的估算 Token 占用、预算、选中的 Message sequence/摘要身份和裁剪原因；Loop 只能消费该快照，不得在请求进行中由后台任务修改它。调试快照默认关闭且脱敏，不把用户文本、工具参数、结果或 Secret 写入 RunEvent。

阶段 4 的第一块基础已实现于 `agent.context_budget`：`ModelContextCapabilities` 表示模型 context window 硬上限，`ContextBudget` 表示用户输入上限与输出预留，并解析为不可变 `ResolvedContextBudget`；`TokenEstimator` 是可替换的估算边界，当前 `ConservativeUtf8TokenEstimator` 对 UTF-8 文本、消息结构、工具调用与工具 Schema 做确定性保守估算；`ContextUsage` 记录一次 `ModelRequest` 的 system prompt、工具 Schema 与消息分项占用、剩余预算及是否超限。该模块尚未构建完整 ContextSnapshot，也未接入 Loop、裁剪、摘要、Profile 或设置 UI。

阶段 4 的第二块基础位于 `agent.context_history`。`group_context_history()` 先验证模型历史：历史只能从 USER message 开始，SYSTEM prompt 只能通过 `ModelRequest.system_prompt` 单独提供；带 tool calls 的 ASSISTANT message 必须紧跟其声明顺序对应的 TOOL results，且 call ID 不得重复、缺失或错配。验证通过后，它返回不可变的 `ContextHistoryUnit` 元组，每个单元从一个 USER message 开始并延续到下一条 USER message 之前。后续 Context Builder 只能整体选择或丢弃这些单元，因而不会裁断工具调用链；当前模块不修改历史，也尚未接入 Loop 或实际裁剪。

`agent.context_history.select_recent_context_history()` 是该模块的确定性裁剪基础：调用方先从总输入预算扣除 system prompt、工具 Schema 等固定成本，得到 `max_message_tokens`，选择器再从最新 `ContextHistoryUnit` 向前累加 `TokenEstimator` 的消息估算。它只在完整单元仍能放入时保留，并按原时间顺序返回不可变 `ContextHistorySelection`；最新单元本身无法放入时返回空选择，不截断单元，也不跳过最新单元去选择更旧的历史。选择结果包含扁平化消息、已选 Token 和省略单元数量，供后续 ContextSnapshot 解释裁剪原因。当前 Context Builder 尚未调用它。

最小 `agent.context_builder.ContextBuilder` 现已组合这些基础：它先估算 system prompt 与工具定义的固定输入成本，以有效输入预算的剩余部分选择完整历史，再创建不可变 `ContextSnapshot`。Snapshot 持有唯一的 `ModelRequest`、`ResolvedContextBudget`、与请求一致的 `ContextUsage` 和 `ContextHistorySelection`，因此能说明本次模型实际可见的消息与预算使用。若固定成本已超限，或非空历史的最新完整单元无法装入，Builder 抛出 `ContextBudgetExceededError`，绝不静默丢弃当前用户问题后仍向模型发请求。它不读取 SQLite 或生成摘要；已注入 Builder 的 AgentLoop 会在每次模型调用前构建 Snapshot 并只传递其 `request`，超限时在调用模型前以 `FAILED` 结束。为避免尚未配置模型能力时硬编码窗口，Builder 暂为 Loop 的可选依赖。后续通过面向用户的模型能力解析层为已知模型自动提供窗口；只有自定义/未知模型才显示高级能力配置，不能要求普通用户直接填写 Profile 底层字段。

模型能力与用户策略分别建模：未来模型能力解析层为已知模型提供经维护的 `context_window_tokens` 硬上限，并允许未知/自定义模型经高级配置显式声明；用户上下文策略提供 `max_input_tokens`、`reserved_output_tokens` 与可选轮次保护。实际输入预算取用户上限和模型窗口扣除输出预留后的较小值。入口不得临时根据模型名称猜测窗口大小；未来设置界面应为已知模型自动填充能力，只在高级自定义路径请求用户提供窗口，且用户预算不得超过能力上限。

Context Builder 只从 SQLite 原始 Message 读取并生成请求副本，永不覆盖或删除原始历史。历史裁剪以完整用户回合与完整 assistant tool_calls/TOOL results 链为单位；没有可用摘要或摘要失败时，回退为确定性地保留预算内最近完整单元，不清空 Conversation。未来 Conversation Summary 按 Conversation、覆盖的 Message sequence 区间和策略版本建立稳定身份，以防并发或重试重复压缩；只有 READY 摘要可进入 Snapshot。

## 7. Agent Loop 状态机

```text
CREATED
  ↓
PREPARING
  ↓
CALLING_MODEL ←──────────────────┐
  ↓                              │
MODEL_RESPONDED                  │
  ├── final text → COMPLETED     │
  └── tool calls                 │
          ↓                      │
     EXECUTING_TOOLS             │
          ↓                      │
     APPENDING_RESULTS ──────────┘

任意阶段：
  cancel → CANCELLED
  error  → FAILED
  step limit → LIMIT_REACHED
```

`LIMIT_REACHED` 是明确终态，不伪装成成功完成，也不自动进入尚未实现的摘要流程。UI 可以展示已产生的文本和“达到最大步骤”提示；以后若增加一次禁用工具的收尾模型调用，需要单独决策和测试。

若最后一个允许的模型决策仍返回 tool calls，Loop 记录该 assistant 响应但不执行工具，并以 `LIMIT_REACHED` 返回。由于该终态不会再发出模型请求，这段未闭合的工具请求不能被当作可继续使用的模型历史；持久化和恢复策略留待后续 Run/Repository 任务定义。

必须防止：

- 同一工具和参数无限重复。
- 工具错误破坏 tool_use/tool_result 配对。
- 取消后留下不合法模型历史。
- 单个工具结果挤满上下文。
- 达到最大步骤后继续调用工具。

### 7.1 Run 内工具链完整性

一次工具回合从 assistant `tool_calls` 开始，到所有对应的 TOOL results 都追加到模型上下文后结束；它是不可拆分的上下文单元。Context Builder 只能在 Run 开始前或完整工具链之间裁剪历史，不能在当前 Run 内移除 assistant 请求、某个 TOOL result 或两者之一。

Loop 对一组 tool calls 按稳定顺序逐个执行。未知工具、参数错误和工具异常也必须为其 `tool_call_id` 形成明确的错误结果；这样下一次模型调用仍能看见完整事实，而非把失败静默丢失。若取消发生在已收到 tool calls 之后，Runtime 不得把这段未闭合的模型上下文用于后续调用；将来若需要保留或继续该上下文，必须先为未完成调用追加明确的取消结果。

阶段 2 的 `RunCancellationToken` 由 `run_id` 标识，调用方显式传给 Loop。取消是协作式的：检查点位于模型调用前、模型响应返回后、每个工具执行前及工具执行返回后；它不强制中断正在 await 的 Provider 或 Tool。若取消发生在 assistant tool calls 已写入后，已完成工具保留真实结果，尚未执行的调用补齐配对的取消结果，再进入 `CANCELLED`。未来 AgentRuntime/API 负责按 `run_id` 注册、查找和释放 Token，并由 Provider/Tool 的超时或原生取消能力缩短等待时间。

重复调用检测以内部 `tool_id` 和规范化 JSON 参数的组合为键，避免 Mapping 键顺序造成漏检。最小 Loop 默认只记录该计数而不阻断；调用方可显式设置每个组合允许的最大执行次数，超过时返回配对的 TOOL 错误结果。未来 Tool Policy 再按工具副作用和时效性选择不同阈值，不能只依赖向模型追加提示词。

最小 Loop 在将工具结果写入 TOOL message 前按字符数截断，默认最多 4,000 个字符；截断标记计入上限，因此单条模型可见结果绝不超过该配置。当前这只是阶段 2 防止单一输出挤满上下文的保护，未来阶段 4 以 token 预算统一管理。截断只影响发给模型的副本；后续 Run/ToolCall 持久化与审计必须保存原始结果或独立的受控产物，不得把截断副本当作唯一事实。

## 8. Chat 与 Channel 边界

阶段 1 先实现不依赖入口的最小 `ChatService`：调用方提供已创建的 `Conversation`、用户文本、模型名称和系统提示词；Service 保存 Conversation 与 UserMessage，读取该 Conversation 的可见历史并构造无工具的 `ModelRequest`，调用 `ModelProvider.complete()` 后保存并返回 AssistantMessage。时间和 Message ID 由构造函数注入，使 Service 不隐式依赖系统时间或随机数。当前不创建 Run、不处理流式或工具调用；Provider 异常时已保存的用户消息保留，工具调用响应会明确失败，等待阶段 2 的 Agent Loop。

阶段 1 的 `asagent` CLI 保留 `run_chat()` 作为无工具 ChatService 的离线测试入口。阶段 2 的默认命令则是独立的开发 Agent 垂直切片：它在进程内组合确定性的 `DevelopmentToolModelProvider`、三个内置工具、`AgentLoop` 和终端 `EventPublisher`，使用户可离线体验连续输入、工具回合与安全 RunEvent。每条输入创建新的内存态 Run，Conversation 上下文只在该进程存活；输入 `exit` 或 `quit` 时退出。

CLI 以显式 `--profile <name> --secret-env <environment-name> --app-home <root>` 启用真实 Provider 路径：入口通过 `AppPaths` 加载 `<root>/config/providers.toml`，将所选 Profile 的 `secret_id` 显式绑定到调用者选择的开发期环境变量，并拥有 `httpx.AsyncClient` 生命周期。源码开发可使用 `uv run --env-file .env asagent ...` 在进程启动前注入该变量；`.env` 仅是被忽略的开发便利文件，正式桌面端仍应使用系统 Secret Store。Profile、Key 或网络错误不会静默降级为离线 Provider。

阶段 3 的 `--persistent` 是 SQLite 持久化开关，可独立使用离线 `DevelopmentToolModelProvider`，也可与成对的 `--profile`、`--secret-env` 显式组合为真实 Provider 持久化开发模式。两种持久化模式都以 `AppPaths.data_dir / "asagent.sqlite3"` 初始化/升级 SQLite，组合 SQLite Conversation/Run Repository、RunSubmissionService、Starter、Finisher、Repository EventPublisher、Repository ToolCallRecorder 和 PersistentAgentRuntime。真实模式把由 Profile 创建的 `ModelProvider` 注入同一 Runtime；`httpx.AsyncClient` 的生命周期覆盖整个交互会话。未给 `--conversation-id` 时创建并打印新 Conversation 身份；提供该参数时只加载既有 Conversation，不存在即在模型调用前拒绝。默认 CLI 仍保持原来的内存态、终端事件开发模式。持久化模式只输出最终回答、错误或终态，安全 RunEvent 通过 SQLite 回放而不在此处实现多播或 SSE。

CLI、Local API 与未来渠道将通过同一个更完整的入口接口进入：

```python
class ChatRequest:
    user_id: str
    conversation_id: str | None
    content: str
    attachments: list[Attachment]
    source: str

class ChatService:
    async def send(self, request: ChatRequest) -> RunHandle: ...
```

未来的 Telegram、WeChat、Webhook 只负责：

```text
外部消息 → ChatRequest
RunEvent / AssistantMessage → 外部回复
```

Channel 不参与 Prompt 构建、模型路由、工具执行和数据库事务。

## 9. Model Gateway

第一版定义最小接口：

```python
class ModelProvider(Protocol):
    async def complete(self, request: ModelRequest) -> ModelResponse: ...
    def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]: ...
```

`complete()` 是 awaitable 的一次性调用；`stream()` 直接返回可由 `async for` 消费的异步迭代器。具体 Provider 可以将 `stream()` 实现为含 `yield` 的 `async def` 异步生成器。

`ModelRequest`、`ModelResponse` 和 `ModelEvent` 是 Provider-neutral 的模型交换数据类型：它们在定义 `ModelProvider` Protocol 前先完成，以避免 Protocol 使用未定义的类型、厂商 SDK 对象或无约束的 `dict`/`Any`。它们与用户可见 Message、内部 RunEvent 分开，专门表达向模型发送和从模型接收的运行时材料。

阶段 0 的最小契约还包括 `ModelMessage`、`ModelMessageRole`、`ModelToolDefinition` 和 `ModelToolCall`：请求使用标准化消息与 Provider 可见工具定义；响应和流事件使用 Provider 返回的 `call_id`、工具名称和参数。Provider `call_id` 不等同于内部 `ToolCallId`，后续 Runtime 通过 Run Tool Snapshot 映射两者。

阶段 2 的非流式工具消息契约已经补齐：assistant `ModelMessage` 可以携带零或多个 `ModelToolCall`；每条 TOOL `ModelMessage` 必须携带文本结果和与原请求配对的 `tool_call_id`。只有 assistant message 可以携带 `tool_calls`，只有 TOOL message 可以携带 `tool_call_id`。OpenAI-compatible Provider 将这两类消息映射为 Chat Completions 的 assistant `tool_calls` 和 tool `tool_call_id`；流式工具调用仍留给后续独立任务。

这项契约有两层不变量。单条消息层面由 `ModelMessage` 构造时校验：只有 assistant 可携带 `tool_calls`，只有 TOOL 可携带 `tool_call_id`，TOOL 必须有结果文本且不能再携带 `tool_calls`。跨消息层面由 Context Builder/Agent Loop 保证：每条 TOOL message 都必须对应同一轮中先前 assistant `tool_calls` 的一个 `call_id`，不得产生孤立、重复或未执行的结果。工具成功和失败都要形成可发送给模型的结果文本；不能以丢弃 TOOL message 的方式隐藏执行结果。

### 9.1 最小 Agent Loop 的前置条件

Agent Loop 不是只调用 `ModelProvider.complete()` 的控制流；它会把中间状态重新放回下一次模型请求。因此，在开始实现循环前，必须先满足并保持以下条件：

- Provider-neutral 模型上下文能够表示 assistant tool call 和配对的 TOOL result。
- 每次工具回合可构造合法的消息序列：assistant tool calls → 对应的 TOOL results → 下一次 model request。
- 目标 Provider 可以无损映射这段历史；至少有离线 HTTP 边界测试断言生成的请求负载。
- Fake Provider 可以脚本化“工具调用 → 最终文本”的两次响应，以测试 Loop，而不依赖网络。
- Loop 在把结果追加到上下文前验证配对关系；Provider 只负责协议映射，不替 Runtime 猜测或修复不合法历史。

这些条件成立后，最小非流式 Loop 才只需关注决策步数、调用工具、追加结果和终态。流式 tool call、持久化 Run Tool Snapshot、参数校验、权限、超时与审计仍按各自的独立任务推进，不能被这份最小上下文契约暗中替代。

标准化对象至少覆盖：

- System Prompt。
- Messages。
- Tool Schemas。
- Model name。
- Token/usage 信息。
- Text delta、reasoning metadata 和 tool calls。

第一版实现一个 OpenAI-compatible Provider 和一个完全离线的 Fake Provider。测试默认使用 Fake Provider，避免费用和不稳定响应。

阶段 0 的 `FakeModelProvider` 只用于离线测试：构造时分别提供一次性 `ModelResponse` 脚本和每次流式调用对应的一组 `ModelEvent` 脚本；每次调用按顺序消费一项。脚本耗尽时抛出明确错误，而不是生成默认响应，从而避免测试意外通过。Fake 同时保留只读请求历史，供测试断言传入模型边界的请求内容。

Provider 的代码实现与用户选择的配置 Profile 分开。`models.config.ProviderConfig` 是 Pydantic 的系统配置边界：它校验适配器类型、模型名、HTTP Base URL、`secret_id` 与正超时值，并拒绝未知字段；`timeout_seconds` 默认 180 秒，且每个 Profile 可覆盖。它约束单次模型 HTTP 请求，不是整个 Agent Run 的总时长。`ProviderProfiles` 保存多个非空命名 Profile。API Key 不进入 Profile、仓库、日志或测试夹具。`models.secrets.SecretProvider` 只声明按 `secret_id` 返回 Secret 或缺失值的能力，尚不绑定具体存储实现。阶段 1 使用 `config_dir/providers.toml` 管理多个命名 Profile，并由后续 Keychain/Secret Store 适配器实现该 Protocol；开发期环境变量只能作为入口层显式后备，业务代码不直接读取。

`models.profile_loader.load_provider_profiles(config_dir)` 是该文件进入系统的唯一当前加载路径：它只读取 `config_dir/providers.toml`，使用标准库 `tomllib` 解析后交给 `ProviderProfiles` 验证；文件不存在、TOML 语法错误和 Profile Schema 错误统一转换为脱敏 `ProviderConfigurationError`。加载过程不创建目录、不读取 Secret、环境变量或 Keychain，也不选择或实例化 Provider。

阶段 8 的通用外部连接基础将非敏感 `Connection` 与实际凭据分开：Connection 由稳定
`connection_id`、`user_id`、`service_id`、账户显示名、已授予 scope、状态和时间组成，并由
`ConnectionRepository` 持久化到 SQLite；refresh token、API Key 或其他不透明 credential 不进入
该表、`mcp.json`、日志或普通配置。Core 的 `CredentialStore` 只按 `connection_id` 读取、保存和删除
credential；首个边缘适配器 `MacOSKeychainCredentialStore` 通过当前 macOS 用户的 Keychain 实现它。
Windows Credential Manager 与 Linux Secret Service 以后实现同一 Protocol，未实现的平台必须明确报错，
不得静默降级到 `.env`、SQLite 或文件。当前 `mcp.json` 可为某一 Server 成对声明非敏感的
`connection_id` 和 `credential_environment_variable`；Sidecar 仅在存在该引用时构造 CredentialStore，
由 Manager 读取对应 credential 并只把它放入该 Server 子进程的指定环境变量。

第一个真实 Connection 流程将是 Gmail 的本地开发 OAuth：Electron Main 只负责通过系统默认浏览器
打开授权 URL，Python Sidecar 在内存生成 PKCE verifier、不可预测的 state 和 `127.0.0.1` 随机端口，
并独占一次性 loopback callback、state 验证与授权码交换。callback 成功后，Sidecar 保存不含 token 的
Connection 元数据，并把 refresh token 写入 Keychain；access token、授权码、state 和 verifier 都不写
入 SQLite、普通配置、日志或 Renderer。测试期仅允许 Google OAuth `Desktop app` client、External Testing
中的显式 Test user，以及 `gmail.readonly` 这一个只读 scope。该 scope 仍属于 restricted scope，Testing
授权会过期；它只用于当前本地开发体验，不能被表述为公开发布或长期生产授权。当前近期消费方是受控的
Gmail MCP Server，而不是 asAgent 内置 Gmail API Gateway；它将通过既有 `connection_id` 定向 credential
注入进入统一 ToolRegistry。原生 Email workspace、其专用 Local API 和直接 Gmail API Gateway 留待以后
真实产品需求出现时再设计；届时必须复用同一 Connection、OAuth 和 Keychain 生命周期，不能另建第二套
token 或账户主数据。当前 `bootstrap.gmail_oauth` 已提供离线可测的 Foundation：严格校验非敏感
Desktop client ID，生成 PKCE S256 verifier/challenge、state、`gmail.readonly` authorization URL，并仅能
一次性消费匹配 state 的 callback query。它不启动 listener、不打开浏览器、不联网交换 code、不保存
Connection 或 Keychain credential。真实 Gmail OAuth、自动刷新、Connection API、设置 UI 和 Gmail MCP
Tool 已明确后置到产品完善阶段。

开发入口可使用 `bootstrap.EnvironmentSecretProvider` 作为临时后备：入口显式传入环境 Mapping，并为每个 `secret_id` 提供允许的环境变量名称绑定。该适配器只读取绑定过且非空的值；它不导入 `os`、不扫描任意环境变量，也不被 Provider、ChatService 或 Core 直接构造。系统 Keychain/Secret Store 仍是后续正式实现。

`bootstrap.create_model_provider()` 是当前 Provider 组合根：它按 Profile 名称取得经验证配置，并将 `SecretProvider` 与由入口拥有生命周期的 `httpx.AsyncClient` 注入已实现的 Adapter。未知 Profile 与尚未实现的 Adapter 都转换为 `ProviderConfigurationError`；当前仅创建 OpenAI-compatible Adapter，Claude Profile 会明确拒绝而不伪装为兼容协议。

仓库提供 `scripts/check_deepseek.py` 作为可选手动连通性检查入口：它从被忽略的 `.local-data/config/providers.toml` 加载 Profile，并由该脚本显式将当前进程环境的指定变量绑定为 Secret。该脚本不属于 pytest 或 CLI 默认路径；它只在用户主动设置临时环境变量后发出一次最小请求，并只输出响应与 usage，不输出 Secret。

首个真实 Profile 为 `deepseek`，使用 `openai_compatible` Adapter。阶段 1 的 `OpenAICompatibleProvider` 使用注入的 `httpx.AsyncClient`、`ProviderConfig` 和 `SecretProvider` 发起 `POST /chat/completions`；它将标准化的 system/user/assistant Message、工具定义、一次性响应的文本/推理/工具调用/usage，以及 SSE 的文本和推理增量在边缘处互相映射。HTTP Client 的生命周期由未来组合根管理，Provider 不创建或关闭它。当前非流式 Agent Loop 已使用 Tool Message；流式 ToolCall 仍明确未实现，避免静默生成不完整事件。

Provider 边缘以 `ProviderError` 及其子类向上报告故障：配置/缺失 Secret、认证、余额、请求、响应格式、传输、超时、限流和服务端错误彼此可区分；错误仅携带安全的类别与可选 HTTP 状态码，不保留响应正文、请求或 Secret。OpenAI-compatible Provider 将 `httpx.TimeoutException` 转换为 `ProviderTimeoutError`，让 Loop 和未来入口能够对它作出明确处理。非流式 `complete()` 只对明确可重试的 HTTP 429 和 5xx 使用固定短延迟重试一次；401、402、400、422、响应格式错误、Secret 缺失及传输/超时均不重试。传输故障的结果可能不确定，自动重试会造成重复计费风险；流式调用一旦可能已产生增量，也绝不自动重试。后续入口可根据错误类别给用户可理解提示，后续可再评估 Provider 专用 backoff/Retry-After 支持。

未来 `openai` 或其他兼容 Chat Completions 服务只需增加 Profile，复用同一 Adapter；Claude 使用独立的 `anthropic_messages` Adapter，不能塞入 OpenAI-compatible Adapter 的条件分支。所有 Adapter 最终仍只向 Core 暴露 `ModelProvider`。

## 10. Tool 架构

### 10.1 工具定义

```python
class ToolDefinition:
    tool_id: str
    display_name: str
    description: str
    input_schema: dict
    risk_level: str
    required_permissions: set[str]
    requires_approval: bool
    timeout_seconds: float
```

阶段 0 的 `ToolDefinition` 是不可变 Core 数据对象：输入 Schema 在构造时保留只读顶层快照，权限使用不可变集合，且 `timeout_seconds` 必须为正数。它只声明工具元数据和安全要求，不执行 JSON Schema 校验、Policy 或工具本身；这些职责属于后续 Registry、Executor 和 Policy。

阶段 0 的 `Tool` 是异步 Core `Protocol`：它公开只读 `definition`，并接受已准备好的参数 Mapping 执行后返回文本结果。具体 Tool 不负责参数校验、权限、批准、超时、取消、审计或结果截断；这些横切职责由后续 `ToolExecutor` 与 Policy 管线统一处理。

内部 `tool_id` 必须命名空间化：

```text
builtin.calculator
builtin.current_time
filesystem.read_file
github.search_repositories
```

内部 ID 不直接假设能作为模型 Provider 的函数名。每个 Run 的 Tool Snapshot 还保存 Provider 映射：

```python
class ModelToolBinding:
    provider_name: str
    tool_id: str
    schema_hash: str
```

`provider_name` 由 Model Adapter 生成，满足具体 Provider 的字符和长度限制；模型返回工具调用后，必须通过 Snapshot 反查内部 `tool_id`。

### 10.2 工具执行管线

```text
ToolCall
→ 查找定义
→ JSON Schema 参数校验
→ Policy 权限判断
→ 可选用户批准
→ 超时和取消控制
→ 执行
→ 结果清洗、截断和序列化
→ 记录 ToolCall/Event
→ 返回 ToolResult
```

`ToolExecutor` 接受默认为空的不可变 `granted_permissions` 和可选异步 `ToolApprovalPolicy`；在查找内部 `tool_id` 后先使用 `jsonschema` 的 `Draft202012Validator` 校验 `ToolDefinition.input_schema`，再要求工具的 `required_permissions` 是已授予集合的子集，对 `requires_approval=True` 的工具请求 Policy 批准，最后才以该定义的 `timeout_seconds` 限制单次异步执行。参数无效时不会调用 Tool，并以 `ToolArgumentsValidationError` 返回至 Loop；缺少权限时以 `ToolPermissionDeniedError` 返回；缺少 Policy、缺失一次性 Approval Request 或审批拒绝时以 `ToolApprovalDeniedError` 返回；超时会取消正在等待的工具协程并转换为 `ToolTimeoutError`。AgentLoop 将这些错误都写为与原调用配对的 TOOL 结果，交回模型继续决策。该取消不能回滚已经发出的外部副作用，因此后续 Tool/Policy 仍需按风险级别规定清理、幂等和审计策略。

当前桌面端的最小审批由 `PendingToolApprovalPolicy` 完成：AgentLoop 只在 schema 与权限检查通过后，为当前 `run_id`、`conversation_id` 和 `tool_call_id` 创建 `ToolApprovalRequest`。若内存中已有同一 `conversation_id + definition.tool_id` 的会话授权，Policy 直接批准且不发事件；否则登记 pending、发布不含参数正文的 `tool.approval_requested` RunEvent，并等待一次 `deny` / `allow_once` / `allow_conversation` 决定。`allow_conversation` 只把该内部工具 ID 记入当前 Sidecar 进程的内存 grants，不写 SQLite。Local API 以本地 Bearer 认证读取待处理请求并接收字符串 `decision`；Electron Main 持有 Token 并转发具名 IPC，Renderer 在输入框上方显示英文横幅。取消 Run 或关闭 Sidecar 会拒绝尚未决定的请求、清空会话授权并解除等待。刷新桌面窗口或更换 Conversation / 工具 / Schema 版本仍需重新批准；跨会话长期授权、审批历史和审计仍是后续独立任务。

后续统一授权模型由三个独立维度组成：工具能力、资源范围和单次操作批准。文件根、浏览器 Profile/站点、OAuth scope、MCP Server 是不同资源范围，彼此不继承；因此全盘文件范围不授予浏览器、Gmail 或 MCP 能力，OAuth Token 也不授予本地文件权限。任何 `allow_all` 等通用开关都不得跨资源使用；Policy、Approval、Settings 和审计都必须携带资源类型与实际范围。

未来 Chat 以外的专用工作区（例如 Email、Calendar）还要携带明确的 `interaction_surface`。OAuth
连接只表示第三方服务向 asAgent 授予某个账户和 scope 的访问；它不自动授权模型在任意入口使用该访问。
用户可在 Email 工作区为已连接的账户显式启用低风险只读能力（如搜索、列出和读取邮件），该持久化偏好
只作用于该工作区、账户、scope 与具体工具，不能外溢到 Chat、其他账户或写入操作。发送邮件、删除、修改
标签/规则、授权范围扩大等副作用操作仍按风险要求逐次批准或拒绝。这个未来设置/撤销模型独立于当前
Sidecar 内存中的 Chat 会话授权，必须在引入 Gmail OAuth、Secret Store 和专用 UI 时一起实现。

### 10.3 Tool Snapshot

每个 Run 开始时确定一个工具快照，包含内部工具定义、Schema Hash 和 Provider 名称映射。即使 MCP Server 在运行中热更新，本次 Run 的 Schema 和名称映射保持稳定，下一个 Run 再使用新版本。

阶段 2 当前的最小运行时实现为 `tools.snapshot.ToolSnapshot`：它冻结按 Registry 顺序取得的 `ToolDefinition`、内部 `tool_id` 与 Provider 名称的双向 Binding，并导出对应的 `ModelToolDefinition`。当前 OpenAI-compatible 名称规则位于 `models.tool_names`，将不兼容字符规范化并限制为最多 64 个允许字符；名称碰撞在构造 Snapshot 时明确拒绝。Snapshot 还未写入 `Run` 或数据库，阶段 3 持久化时再将同一边界保存为可回放记录。

## 11. MCP 架构

阶段 8 才实现。结构为：

```text
config_dir/mcp.json
→ McpServerManager
→ McpClient
→ `server/discover`（现代协议版本与能力发现）
→ 每次请求携带协议版本、Client 身份与能力元数据
→ 仅对旧 stdio Server：隔离探测进程后回退 `initialize` / `notifications/initialized`
→ tools/list（处理分页和 listChanged）
→ 每个远程工具包装为 ToolDefinition + Tool
→ 注册到 ToolRegistry
```

第一版只支持 stdio。首选 MCP `2026-07-28` 的无会话请求格式；`McpClient` 对
未知或仅支持旧生命周期的 stdio Server 采用有界的 modern 探测，然后以全新子进程
回退到 `2025-11-25` 及以前的 `initialize` 生命周期。回退不能复用被未知探测请求
影响过的 stdin/stdout 会话。稳定后再支持 Streamable HTTP、OAuth 和工具检索。

阶段 8 的首个对端为 `tests/fixtures/mcp_test_server.py`，不是产品 Server 或运行时
依赖。它仅支持现代 `2026-07-28` 请求：要求每条请求带完整 `_meta`，以
`server/discover` 报告 `tools` 能力，并以 `tools/list` 暴露确定性的 `add` 工具、
以 `tools/call` 返回结果。协议格式错误、未知方法和未知工具使用 JSON-RPC error；
可由模型修正的 `add` 参数错误返回 `result.isError=true`。它严格让 stdout 只承载
一行一个 JSON-RPC 消息，启动日志写入 stderr，为未来 Client 的传输、错误和 fallback
测试提供可控对端。

当前最小实现位于 `tools.mcp`：`McpClient` 先以现代 `2026-07-28` 请求启动 stdio 子进程，
为每个 JSON-RPC Request 写入一行 JSON，并在同一受限连接上按递增 request id 等待配对
Response。现代 `server/discover` 返回 MCP 协议/远端错误时，Client 会关闭探测进程、重新启动
全新子进程，并以 `2025-11-25` 的 `initialize` 与 `notifications/initialized` 进入 legacy
生命周期；旧版后续 `tools/list` / `tools/call` 不携带现代 `_meta`，但仍返回同一统一的
`McpServerInfo`、工具描述和调用结果。可选 `working_directory` 必须是绝对路径，并作为子进程
`cwd`；省略时沿用宿主当前目录。相对路径在构造时拒绝，避免 Server 依赖调用方 cwd。当前 Agent Loop 的工具回合本来就是顺序执行，因此 Client
明确一次只允许一个在途请求，避免在尚无通知消费需求时引入后台读循环和复杂的响应分发器。
Client 完成 `server/discover`、`tools/list` 与 `tools/call`；JSON-RPC `error` 转为传输/远端
异常，而 `tools/call` 的 `result.isError` 由 `McpTool.execute` 变成以 `Error: ...` 前缀的
普通字符串结果返回模型，便于模型据结果修正参数。请求超时、EOF、无效 JSON 或 id 不匹配会
关闭该子进程并明确失败。测试 legacy Server 在收到现代探测后主动退出，因此仅当 Client 使用
新进程完成旧握手、列举和调用时才会通过。当前只支持文本 Tool content、无分页、无通知处理，
且尚未支持配置固定协议版本。

`McpTool` 把一次 `list_tools` 得到的远程描述包装为现有 `Tool` / `ToolDefinition`：
`display_name` 优先 MCP `title` 否则 `name`，description 与 `input_schema` 直接沿用远端描述，
`risk_level=medium`，`required_permissions={"mcp.execute"}`，且 `requires_approval=True`。
`register_mcp_tools(registry, client, server_name=...)` 负责列举并注册；`server_name` 来自
宿主导入时的显式命名空间，不强制等于远端 `serverInfo.name`。

`McpServerSession` 是当前最小生命周期所有者：它持有一个 `McpClient`、目标 `ToolRegistry`
和宿主 `server_name`，`start()` 只允许一次（discover + 一次性导入），启动失败会关闭 Client
并把 Session 标为已关闭；`aclose()` 幂等关闭子进程。它不是 Server Manager，也不读取
`mcp.json` 或自动接入应用组合根。

`tools.mcp_config` 是 MCP 非敏感配置的唯一加载边界。它读取可选的
`config_dir/mcp.json`：缺失文件等价于空 Server 集合，且不会创建目录；存在文件必须为严格
JSON，顶层只允许 `servers`。每个显式命名 Server 只声明非空的命令参数元组和绝对工作目录；
名称是受限的小写标识符，未知字段、相对工作目录与空参数都会被拒绝。该加载器不验证路径是否
存在、不启动进程、不读取环境变量或 Secret。可选的 `connection_id` 与
`credential_environment_variable` 必须成对出现，前者只是系统凭据的稳定引用，后者只是目标子进程
接收 credential 的环境变量名；两者都不是 Secret。Token、密码、API Key 和环境变量值都不能进入
此文件。可选 `allowed_tools` 是该 Server 的精确工具名称白名单：省略时保持导入全部工具的兼容行为；
空列表、重复或空名称会在配置加载时被拒绝；若启动后 Server 没有暴露所列名称，导入失败且不会污染正式
Registry。`save_mcp_server_configs()` 是此配置的唯一写回边界：显式保存时创建配置目录，先写临时文件再
替换 `mcp.json`，且以完整 `McpServerConfigs` 重新序列化，因此更新单个 Server 时不会丢失其他 Server。

`tools.mcp_manager.McpServerManager` 是多个已校验配置项的最小生命周期所有者。它为每个配置
创建带对应工作目录和显式子进程环境的 `McpClient` 与 `McpServerSession`，但先将远程工具导入临时 Registry；
只有所有 Session 均成功启动后，才检查工具 ID 冲突并合并到调用方的正式 Registry。任一启动
失败时，Manager 关闭已创建的 Session，正式 Registry 保持不变。关闭时它以反向创建顺序关闭
全部 Session，且之后拒绝再次启动。若某项配置引用 Connection，Manager 只从注入的
`CredentialStore` 读取该 `connection_id`，并仅在该项子进程环境中设置其声明的
`credential_environment_variable`；缺少 Store 或 credential 会在启动前失败并保持原子的无导入语义。
Manager 不读取文件、不管理热刷新、重连、分页或 legacy fallback。

MCP Server 的权限独立于宿主工具权限：stdio Server 使用显式工作目录、最小环境变量和自身配置；远程 Server 仅使用为该 Server 配置的 Token 与能力。它们不继承 asAgent 的文件范围、浏览器 Profile 或其他账户 Token。`McpClient` 默认以空环境启动子进程，避免独立调用时意外继承宿主 Secret；当前 Sidecar 组合根仅显式传入 `PATH`，不传模型 API Key、Local API Token 或任意 `.env` 值。

外部 Web Search 也遵循这一边界：首选由用户显式配置的 MCP Search Server 提供，而不是把某个模型厂商的
managed search 私有参数写入通用 Provider 或 Agent Core。用户选择 Server、其网络能力和凭据；Server 的
工具仍通过现有 Registry、`mcp.execute` 权限、审批、超时和审计链路。当前不提供内置搜索服务，也不假定
DeepSeek 或其他 OpenAI-compatible Profile 的 Chat Completions API 存在通用联网搜索参数。未来若接入
Provider-managed search，必须作为明确的 Provider 专用能力另行设计，不能伪装成可审计的本地 Tool。
首个真实 Search Server 选择 Tavily 官方的本地 stdio MCP Server；当前 Transport 尚未实现 Streamable HTTP，
因此不使用 Tavily 的远程 MCP URL。首次只允许其基础 search 能力，避免把搜索、网页提取、站点映射、爬取和
研究等不同成本与风险的能力一次性授权给模型；该限制由 Tavily 配置的 `allowed_tools` 实际执行，而不是
仅靠提示词或审批文案约定。

因此，MCP credential 不会绕过最小环境策略：未引用 Connection 的 Server 继续仅接收 Sidecar
显式允许的基础环境（当前为 `PATH`）；引用 Connection 的 Server 只额外接收自身声明变量名下的
credential，不会收到模型 API Key、Local API Token、其他连接的 credential 或完整宿主环境。
这一实现目前只支持 macOS Keychain；OAuth、刷新、Windows/Linux 系统存储以及除环境变量以外的受控交付
机制仍是后续独立工作。

首个桌面可配置的 API key 连接是 Tavily。`bootstrap.tavily_settings.TavilySettings` 协调 API key、
Connection 与 MCP 配置，但不成为新的通用设置框架：`GET` / `PUT` / disable / `DELETE`
`/api/v1/settings/tavily` 只在 Local API 已注入该对象时可用，仍受本地 Bearer 认证。保存或替换 key 时，
Keychain 保存 `connection-tavily` 的不透明值，SQLite 保存 `service_id="tavily"` 的非敏感 Connection，
而 `mcp.json` 只保存定向的 `TAVILY_API_KEY` 引用与 `allowed_tools=["tavily_search"]`。禁用只移除该
Server 配置；删除才同时删除配置、Keychain 值与 Connection。响应只包含 `enabled` 与 `api_key_saved`，
不返回 API key。设置变更不热更新当前 Tool Snapshot，必须重启 Sidecar 才会生效。

Electron 的现有 Preferences 页面已通过专用 Main IPC 接入上述 Tavily 操作：首次启用时 Renderer 只将密码
输入短暂传递给 `enableTavily()`，操作完成或失败后立即清空 state；已经保存的 key 永不回读或显示。关闭
只调用 disable，Replace 再次要求临时输入，Remove 在英文确认后调用完全删除。所有设置写操作完成后只提示
`Restart asAgent to apply this change.`，不会在活跃 Sidecar 内热加载或扩大 Renderer 权限。

桌面还可配置一个固定名称为 `desktop` 的 OpenAI-compatible Provider Profile。`providers.toml` 仅保存
adapter、model、base URL、secret ID 和 timeout；对应 API key 只以 `connection-desktop-model` 存在系统
CredentialStore。`ModelSettings` 经 Bearer Local API 和固定 Main/Preload IPC 暴露状态、保存与删除，响应只返回
是否已配置、是否已有 key、model 和 base URL。默认桌面 Sidecar 启动时，若这份 Profile 与 key 都存在，则以
`CredentialStoreSecretProvider` 创建真实 Provider；否则保持离线 Runtime。设置修改必须重启 Sidecar 才生效，
Renderer 不读取或保存 API key。保存 Tavily 或模型设置后，Renderer 可通过受来源校验的固定 Main IPC 请求
应用更新运行时：开发模式只重启自身持有的 Sidecar 后刷新现有 Renderer，避免重启 `electron-vite` 管理的
Electron 子进程导致开发服务器丢失；打包版才执行完整 Electron relaunch。两种路径都不要求用户手动退出再打开。

MCP 的 `tools/call` 成功结果可以省略可选的 `isError` 字段；`McpClient` 将其解释为 `False`。若 Server
显式给出非布尔值，仍按协议错误拒绝。这样兼容 Tavily 等合法的成功响应形式，同时不把损坏的错误标记静默
视为成功。

MCP 工具内部 ID：

```text
mcp:{server_name}:{tool_name}:{schema_hash}
```

其中 `schema_hash` 是对 `input_schema` 做稳定 JSON 规范化后的 SHA-256 截断。不同 Server
提供同名工具时不得覆盖。`asagent serve` 是当前唯一的 MCP 应用组合根：它在创建 Runtime 前读取可选
`config_dir/mcp.json`、启动 Manager，并将成功导入后的同一 Registry 交给 Tool Snapshot 与 ToolExecutor。缺失
配置保持只有内置工具；非空配置仅在全部 Server 成功启动后向该 Runtime 授予 `mcp.execute`。任一配置、启动
或导入失败都会阻止 Sidecar 输出 ready 记录；退出时 Manager 在数据库资源关闭前关闭子进程。该集合在一次
Sidecar 生命周期内固定，修改 `mcp.json` 后需要重启；当前持久化 CLI、热刷新和桌面 MCP 设置页不在范围内。
`tests/integration/test_mcp_agent_loop.py` 已验证最小完整链路：测试 MCP Server 经过
`McpClient`、`McpTool`、`ToolRegistry` 和 `ToolSnapshot` 后，脚本化 Model Provider 能看见
Provider 可见工具名并请求调用；`AgentLoop` 再经 `ToolExecutor` 的 `mcp.execute` 权限与批准
Gate 执行，配对 TOOL message 将结果返回下一轮模型上下文。这是受控集成测试，不表示当前
应用组合根会自动启动、导入或授予任意 MCP Server。

## 12. Workspace 架构

个人助手第一版采用简化结构：

```text
workspace/
├── profile/
│   ├── assistant.md
│   ├── user.md
│   └── rules.md
├── memory/                       # 可选的人类可读导出，不是运行时主数据
├── knowledge/                    # 用户知识文档的主数据
├── skills/                       # Skill 文件的主数据
├── files/                        # 用户交给助手处理的文件
└── runs/{run_id}/                # 临时或可清理的 Run 产物
```

逻辑作用域：

| 作用域 | 生命周期 | 内容 |
| --- | --- | --- |
| Personal Workspace | 长期 | Profile、Memory 导出、Knowledge、Skills、用户文件 |
| Conversation | 长期 | 对话消息、摘要和上下文边界 |
| Run Directory | 临时或可清理 | 中间文件、下载、输出和 scratch |

路径必须通过 `AppPaths` 和 `WorkspaceResolver` 提供。工具不得自行拼接用户主目录路径。

阶段 5 的第一块基础已实现于 `workspace.resolver.WorkspaceResolver`：它持有规范化后的 `workspace_root`、可选额外允许根和可选单文件允许项，将相对路径解释为 Workspace 内路径，并只返回位于任一允许根内、或与已授权单文件精确匹配的规范化目标。根目录必须是已存在的目录，单文件必须是已存在的普通文件；只有目录范围内的目标可以尚不存在，以支持后续安全创建文件。`resolve(strict=False)` 会解析已存在的符号链接，因此 `..` 或指向允许范围外的链接都会以 `WorkspacePathOutsideAllowedRootsError` 拒绝。Resolver 不创建目录、不读取或写入文件、不展开 `~`，也不自行扫描真实用户目录；File Tool 与 Policy 必须在执行前调用它。

`workspace.settings.ConversationWorkspaceSettings` 是当前桌面文件范围偏好的最小持久化边界。它将 `AppPaths.workspace_dir` 保留为 asAgent 自己的默认 Workspace 根；用户通过 Preferences 或 Chat Composer `+` 选择的额外文件夹与单文件，则按 `conversation_id` 分别写入 SQLite 的 `conversation_file_scopes`。保存时文件夹与文件都必须存在，符号链接会解析，重复项、默认 Workspace 及已被允许文件夹覆盖的单文件会被移除。文件夹授权其目录树，单文件只授权精确路径，绝不隐式授权父目录或同级文件。Local API 的固定 `GET`/`PUT /api/v1/conversations/{conversation_id}/file-access` 先验证本地用户对 Conversation 的归属，再返回或替换该 Conversation 的路径范围；Electron Main 持有原生文件/目录选择器和认证 API 调用，Preload 只暴露具名操作，Renderer 不获得 Node、文件系统、Token 或任意 HTTP 能力。不会把此前任何全局本地配置静默迁入所有 Conversation，以免扩大既有授权。保存路径不会读取或扫描内容，也不会授予写入、删除或 Shell 权限；但在每个后续 Run 中，当前 Conversation 显式选择的路径会作为不含文件正文的短暂系统上下文发送给模型，使“附加的文件夹”等自然语言指代有确定目标。

首个 File Tool 是 `tools.builtin.filesystem_list.FilesystemListTool`。它要求 `filesystem.read` 能力，先用 Resolver 验证目标，再非递归地列出一层目录项；结果只含文件、目录或符号链接的名称和类型，不读取正文、不跟随链接、不返回绝对路径。它使用稳定名称排序和 `offset`/`max_entries` 分页：默认每页 50、最多 100，结果始终说明目录总数、当前页范围，以及存在时的下一页 offset，因此模型和用户不会把截断结果误解为完整目录。

`tools.builtin.filesystem_read_file.FilesystemReadFileTool` 是对应的最小正文读取能力。它同样要求 `filesystem.read`，先由 Resolver 规范化并检查目标，再只读取一个存在的普通文件；当前仅接受严格 UTF-8 文本，并以 64 KiB 硬上限阻止大文件进入工具结果或模型上下文。目录、缺失文件、Workspace 外路径、超限文件和非 UTF-8 内容均返回明确错误。它不解析 DOCX、PDF、图片或其他二进制格式。

`tools.builtin.filesystem_search_files.FilesystemSearchFilesTool` 补足“已授权范围中但文件名未知”的发现能力。它同样要求 `filesystem.read`，只递归搜索当前 Conversation 可访问的目录；可选 `path` 指向一个已授权目录，省略时遍历已授权的 Workspace 根。搜索是大小写不敏感的字面匹配，检查文件名与严格 UTF-8 文本的前 64 KiB；它不支持正则、不建立索引、不后台扫描，也不读取或返回完整正文。每次最多扫描 1,000 个文件、最多返回 20 个含相对路径和短片段的匹配；符号链接、二进制、不可读或超限文件会跳过，任何扫描或结果上限都会在返回文本中明确标记。

持久化 Runtime 在每个 Run 开始时，以 Run 的 `conversation_id` 读取 `conversation_file_scopes`，构造该 Conversation 专属 `WorkspaceResolver`，再复制基础 ToolRegistry 并仅向这份 Run 专属 Registry 加入 `filesystem.list`、`filesystem.read_file` 与 `filesystem.search_files`。基础内置工具和已启动的 MCP Tool 实例保持可复用，但其他 Run 的 Snapshot 不会得到该 Resolver 或额外路径。Runtime 同时将当前 Conversation 明确选择的文件夹和单文件绝对路径附加到本次 `system_prompt`，并指示模型在用户引用附加资源时使用这些路径；该短暂上下文不进入用户可见 Message、SQLite 或工具结果，但会发送给当前模型 Provider，因此选择器 UI 必须继续清晰显示共享范围。这三个只读 Tool 因此总是只看见该 Conversation 的默认 Workspace、已授权文件夹和已授权单文件；调用越界路径会作为配对的 TOOL 错误返回模型。该机制已接入持久化开发、真实 Provider 和 Electron Sidecar Runtime；非持久化 CLI 不额外获得外部文件范围。

`tools.builtin.filesystem_write_file.FilesystemWriteFileTool` 是最小的受控副作用能力：它只在允许根内以独占创建方式写入一个新的 UTF-8 文件，要求 `filesystem.write`、标记为高风险且始终需要批准。它不创建父目录，64 KiB 以上的正文、目录目标和任何已存在文件都会被拒绝；因此它不能覆盖、追加或删除用户文件。当前通用 Approval Protocol 仅保证没有已授予权限或批准时不会进入工具协程；真正展示规范化路径、影响摘要和有效期限的批准请求仍待独立实现。

`filesystem.write` 目前是“写类操作”的能力门槛，不会扩大已注册 Tool 的实际语义；当前唯一写入 Tool 仍只允许 create-only。按 DEC-060，未来在引入覆盖、追加或删除前，必须先实现持久化 `FileChange`：每次操作先在 `AppPaths.data_dir` 私有快照目录保存必要的变更前正文，再写入 SQLite 元数据 `PREPARED`，完成文件操作并校验 SHA-256 后才成为 `APPLIED`。记录包含来源 Run、规范化根路径与相对路径、CREATE/REPLACE/DELETE 种类、变更前后哈希及相对快照引用；SQLite、RunEvent、ToolCall、日志和模型上下文均不保存快照正文。撤回只处理 asAgent 自己记录且仍处于预期磁盘状态的 APPLIED 变更：CREATE 删除 after hash 未变化的文件，REPLACE 原子恢复快照，DELETE 以独占创建恢复快照；任何不匹配均拒绝并报告冲突。初版快照单项最多 5 MiB、总量 100 MiB、默认保留 30 天，超限时拒绝新变更而不静默清理可撤回快照。create-only 可在该机制完成后纳入记录，以便删除仍未被后续修改的 Agent 新建文件；在此之前它不获得覆盖、追加、删除或撤回能力。

多格式文档能力将独立于基础 File Tool 演进：未来的 `document.extract_text` 负责 DOCX、带文本层 PDF 等格式的确定性正文提取；扫描型 PDF 与图片仅在显式 OCR 工具中处理。两者都必须在 Workspace 范围、文件/页数/输出大小、超时、权限和审计边界内执行，不能以“读取文件”为名自动扫描或上传用户文档。

文件系统范围是用户在每个 Conversation 中选择的持久、可撤销偏好：仅 Workspace（默认）、用户明确选择的文件夹或单文件，未来才考虑整台电脑。当前桌面已实现对当前 Conversation 的多个明确文件夹和单文件的保存、显示和撤销；整台电脑模式仍未实现。每次未来文件请求仍绑定操作类型、所属 Conversation 和规范化后的目标路径；路径穿越与符号链接都不得逃逸当前允许范围。整台电脑模式须经高风险二次确认和平台所需系统授权，且只扩大可寻址路径范围；它不会自动允许写入、删除、命令执行或敏感位置读取。用户也可以把外部文件导入 Workspace。

设置窗口展示当前范围、已授权根与撤销入口；整台电脑模式必须展示风险说明。逐次批准 UI 将展示精确目标或根目录、操作、权限、递归范围、影响摘要和有效期限，而非只展示宽泛工具能力。阶段 5 的审计记录授权/拒绝和所有文件变更的最小必要元数据，不保存文件正文、Secret 或无关路径。阶段 2 的 `granted_permissions` 仅决定工具类别是否有资格执行，不能代替路径范围与逐次高副作用批准。

MCP 非敏感配置位于 `config_dir/mcp.json`，不放在 Workspace。Token、密码和带凭据的环境变量不写入该文件，交给系统 Keychain/Secret Store；SQLite 中的 `mcp_servers` 只保存运行状态、缓存和索引。

## 13. Memory 分层

```text
Working Memory       当前 Run 的临时信息
Conversation Summary 当前 Conversation 的摘要
User Memory          local-user 的长期偏好和事实
Knowledge            用户主动或 Agent 整理的结构化资料
```

这四层不得混用：原始 Conversation 是可审计主数据；Conversation Summary 只服务同一 Conversation 的长历史连续性；User Memory 保存跨 Conversation 的稳定偏好、明确事实和长期事项；Skill 是用户维护、可版本化的操作说明，不能把自动学习到的偏好直接伪装为 Skill。阶段 4 只实现摘要/压缩接口和短期上下文边界；Conversation Summary 的持久化复用、User Memory 写入和跨 Conversation 检索都在阶段 10 实现。

阶段 10 的跨 Conversation 检索是可选的“历史参考”能力，而非每次请求默认扫描全部历史。它只检索用户可见 Message、已确认 Summary 和已确认 User Memory，不索引 RunEvent、ToolCall 参数或结果等内部材料；命中结果带来源 Conversation、Message sequence/摘要身份与时间，并在独立的低权重参考区进入 ContextSnapshot，而非进入 System Prompt。检索受用户选择的范围、相关度阈值、数量和 Token 预算限制；默认不跨所有 Conversation 静默检索。先用 SQLite 文本/关键词检索实现，并在实际使用证明不足后再评估 Embedding/向量索引。

User Memory 的自动候选与正式写入分开：系统可从对话提出候选，但默认须用户确认后才成为跨 Conversation 可见的偏好或事实；用户应能查看来源、编辑和删除。这样个人助手可逐步适应用户习惯，同时避免一次闲聊、错误推断或旧指令污染长期行为。

主数据规则：

- Conversation、Message、Run、RunEvent、ToolCall、Conversation Summary 和结构化 User Memory 以 SQLite 为主。
- Profile、Knowledge Markdown、Skills 和用户文件以 Workspace 文件为主。
- SQLite 可以保存文件的路径、Checksum、解析状态和搜索索引，但不与文件正文形成两个可独立修改的主副本。
- `workspace/memory/` 仅用于可选导出；导出内容可以重建，不能反向静默覆盖 SQLite Memory。

长期记忆写入需要判断：

- 是否长期有效。
- 是否属于用户偏好或事实。
- 是否包含敏感内容。
- 是否与现有记忆重复或冲突。
- 是否需要用户确认。

## 14. 存储边界

初始 SQLite 表建议：

```text
users
conversations
messages
runs
run_events
tool_calls
schema_migrations
```

阶段 3 的初始实现将上述六张业务表定义在 `storage.sqlite.schema` 的 SQLAlchemy Core `MetaData` 中；Alembic 使用同名的 `schema_migrations` 作为版本表，而非额外创建业务迁移表。迁移脚本可使用同步 SQLite 连接，未来运行时 Repository 则通过 `aiosqlite` 管理异步连接；两者共享 Schema，不共享连接生命周期或 SQLite 专有运行参数。

后续增加：

```text
conversation_summaries
memories
knowledge_documents
mcp_servers
```

Repository 接口属于 Core，SQLite 实现属于 Storage。事务边界由 ChatService/RunService 控制。

阶段 0 的最小 Repository 契约按运行时聚合划分，而不是一张未来数据库表一个接口：

- `ConversationRepository` 读取、列举和保存 `Conversation`，并追加、读取该 Conversation 的用户可见 `UserMessage` 与 `AssistantMessage`。
- `RunRepository` 读取、列举和保存 `Run`，并追加、读取其 `RunEvent` 与 `ToolCall`。

这两个接口均为异步 Core `Protocol`，不导入 SQLite 或 SQLAlchemy。读取方法返回不可变的元组快照；`RunRepository.list_events()` 通过 `after_sequence` 明确从 Run 内顺序点继续读取，不能依据时间戳排序或续传。`save()` 用于保存同一稳定 ID 的当前对象；`append_event()` 保持仅追加语义。

阶段 1 的 `InMemoryConversationRepository` 位于 `storage`，是 `ConversationRepository` 的进程内适配器，而不是 Core 的一部分。它按 `conversation_id` 覆盖保存 Conversation，按用户筛选 Conversation，并按追加顺序返回同一 Conversation 的用户可见 Message；向未保存的 Conversation 追加 Message 会明确失败，避免产生孤儿 Message。数据只存活到当前 Python 进程结束，阶段 3 的 SQLite 实现将替换这一适配器而不改变上层 Repository 依赖。

阶段 3 的 `storage.sqlite.conversation_repository.SqliteConversationRepository` 是首个持久化 `ConversationRepository` 实现。它只接收已经迁移的 SQLite 文件路径，不推导或创建用户目录；未来组合根负责由 `AppPaths.data_dir` 传入实际路径并管理迁移。`storage.sqlite.connection.create_sqlite_async_engine()` 是运行时连接的唯一工厂：每个连接启用 foreign keys、WAL、5 秒 busy timeout 与 `synchronous = FULL`。Conversation 按 `created_at`、稳定 ID 排序，Message 由数据库分配 Conversation 内 `sequence` 后读取。SQLite 不能保留时区信息，因此该适配器在写入和读取边界统一将时间规范化为 UTC-aware `datetime`。运行时连接的集成测试固定了这些 PRAGMA，以及异常事务回滚和短暂写锁下等待后提交的行为。

`storage.sqlite.database.upgrade_sqlite_database()` 是开发组合根使用的同步启动辅助函数：调用方显式提供数据库路径和 Alembic 配置路径；它确保数据库父目录存在，并执行 `upgrade head`。它不推导 AppPaths、不创建 Repository 或领域对象，迁移失败直接传播。组合根从 `AppPaths.data_dir` 计算 `asagent.sqlite3` 后调用它；已是最新 Schema 时可重复安全执行。

阶段 3 的 `storage.sqlite.run_repository.SqliteRunRepository` 完整实现 `RunRepository`：Run 按稳定 ID 覆盖保存并按创建时间、稳定 ID 列举；RunEvent 仅追加、按 `sequence` 回放并以 `after_sequence` 续传；ToolCall 按稳定 ID 覆盖保存并保留原始结果或错误。RunEvent 表不重复保存 `conversation_id`，写入时 Repository 校验其与 Run 一致，读取时从关联 Run 恢复。事件 `data` 与工具参数只在 Storage 边界转为普通 JSON object；领域对象保持不可变 Mapping 语义。ToolCall 在没有显式序号的当前 Schema 中以 `created_at`、`tool_call_id` 稳定排序。`storage.sqlite.run_starter.SqliteRunStarter` 以单一 SQLite 事务创建一条用户 Message 和初始 Run：先验证两者属于同一已存在 Conversation，再写入 Message 与 Run；任一插入失败则一并回滚。`storage.sqlite.run_finisher.SqliteRunFinisher` 对称地以单一 SQLite 事务完成已存在 Run：它只接受终态 Run，并在消息存在时同时追加同一 Conversation 的 AssistantMessage；任一写入失败则终态 Run 更新也回滚。二者都不生成 ID、时间或 RunEvent，也不实现请求幂等或 SSE 接入。`storage.event_publisher.RepositoryEventPublisher` 是通用 Storage 适配器：只依赖注入的 `RunRepository` 并将 `EventPublisher.publish()` 委托给 `append_event()`；当前注入 `SqliteRunRepository` 时，Agent Loop 的安全事件即可跨实例持久化并按 sequence 回放。`storage.tool_call_recorder.RepositoryToolCallRecorder` 同样仅依赖注入的 `RunRepository` 并将 `ToolCallRecorder.record()` 委托给 `save_tool_call()`；当前注入 SQLite Repository 时，工具调用的原始参数、成功结果或错误可跨实例审计。两个适配器都不创建 Engine、不改变领域对象、不重试或吞掉写入失败，失败由调用方既有的 Run 失败处理决定。

`run_events` 至少对 `(run_id, sequence)` 建立唯一约束。创建用户消息与 Run 时需要一个明确事务边界，避免 API 重试后产生孤立消息或重复 Run。

## 15. 并发与取消

- 使用 `asyncio` 作为主要并发模型。
- 每个 Conversation 默认使用异步锁，防止同一对话上下文并发修改。
- 不同 Conversation 可以并发运行。
- 阻塞工具通过受控线程池执行。
- 每个工具有超时。
- 取消定位到 `run_id`，而不是含义模糊的 session。
- Run 状态迁移必须原子保存。

## 16. 安全边界

- Local API 默认只监听 `127.0.0.1`。
- Electron 启动后端时生成临时访问 Token。
- Token 不通过命令行参数、URL、localStorage 或日志传递；优先使用子进程管道，环境变量仅作为可接受的本地后备方案。
- Local API 校验允许的 Origin，生产环境与开发环境使用各自明确的 Allowlist；CORS 只为这些来源开放，并正确处理 Authorization Header 的预检请求。
- Renderer 不直接读取 API Key 或启动进程。
- 文件工具必须解析真实路径并验证允许根目录。
- Shell 工具默认关闭或采用严格模式，后期再开放。
- 外部 URL 需要 SSRF 防护。
- Secret 与普通配置分开存储。
- 所有高风险操作保留审计事件。

## 17. 可观测性

每个日志或事件至少关联：

```text
user_id
conversation_id
run_id
sequence
tool_call_id（如适用）
```

Run 记录：模型、耗时、Token、工具选择、工具耗时、结束状态和错误代码。日志内容必须脱敏。

## 18. Local API v1 当前契约

Local API 是 Electron Renderer 与 Python Backend 的内部 HTTP 边界，不是公网服务，也不是 Core 的 Adapter。它只监听 `127.0.0.1`，每次 Backend 启动使用一次性、仅内存存在的 Bearer Token；“默认单用户”不免除该进程间访问能力校验。

当前所有 API 路由都要求：

```text
Authorization: Bearer <本次启动的 token>
```

缺失、格式错误或不匹配的凭据统一返回 `401` 与 `WWW-Authenticate: Bearer`，不区分具体原因。`api.auth.BearerTokenAuthenticator` 使用 FastAPI 的 `HTTPBearer(auto_error=False)` 只为运行时解析和 OpenAPI 声明共享同一 Bearer 语义；真正的 Token 比较仍由 asAgent 以常量时间函数完成。

当前已实现的 v1 表面如下：

| 方法与路径 | 成功响应 | 行为与数据边界 |
| --- | --- | --- |
| `GET /api/v1/health` | `200 {"status":"ok"}` | 仅表示当前 ASGI 应用可响应，不表示模型、Workspace 或完整 Runtime 就绪。 |
| `GET /api/v1/conversations` | `200 Conversation[]` | 仅列出 `local-user` 的 `conversation_id`、`created_at`、`updated_at`。 |
| `POST /api/v1/conversations` | `201 Conversation` | 仅接受空 JSON object；服务端创建 `conv_` ID 和 UTC 时间，为 `local-user` 保存空 Conversation；未知字段为 `422`。不创建 Message、Run 或事件。 |
| `POST /api/v1/conversations/{conversation_id}/messages` | `201 {"message": Message, "run": Run}` | 只接受含非空、非纯空白 `content` 的 JSON object；为 `local-user` 原子创建一条 USER Message 与一个 `created` Run，随后安排进程内后台执行。HTTP 不等待模型结果，因此响应中的 Run 状态仍为 `created`。不存在或不属于 `local-user` 的 Conversation 一律为 `404 {"detail":"conversation not found"}`；无效字段或内容为 `422`。 |
| `GET /api/v1/runs/{run_id}` | `200 Run` | 返回 `run_id`、完整 `status`、`created_at` 和 `updated_at`。先通过该 Run 所属 Conversation 确认 `local-user` 归属；不存在或不属于本地用户的 Run 一律为 `404 {"detail":"run not found"}`。不返回 Conversation、Message、Event、ToolCall 或模型正文。 |
| `POST /api/v1/runs/{run_id}/cancel` | `202 {"run_id": "...", "cancellation_requested": true}` | 仅请求进程内 Dispatcher 协作取消，不直接写入 Run 状态。不存在或不属于本地用户的 Run 为 `404 {"detail":"run not found"}`；存在但不活跃的 Run 为 `409 {"detail":"run is not active"}`。 |
| `GET /api/v1/conversations/{conversation_id}/messages` | `200 Message[]` | 按持久化 sequence 返回可见 USER/ASSISTANT message 的 ID、角色、正文和时间；不存在或不属于 `local-user` 的 Conversation 一律为 `404 {"detail":"conversation not found"}`。 |

时间以 UTC ISO 8601 JSON 字符串表示；API 不返回 `user_id`、内部 TOOL message、Run、RunEvent、ToolCall、Secret 或 Token。`POST /conversations` 暂无幂等键和 create-only Repository 原语，生产 UUID 碰撞虽可忽略，但重试/并发创建语义不能被假定为已解决。

FastAPI 从 App Factory 的类型化路由和 Pydantic 模型自动生成 `/openapi.json`。契约测试必须至少验证当前路径、方法、成功状态码和 `HTTPBearer` 安全方案；现有 HTTP 集成测试继续负责验证 401、404、422 等运行时行为。OpenAPI 不是第二套 API 或新增 Adapter，而是同一内部接口的机器可读描述。

当前 v1 已定义按 `sequence` 的认证 RunEvent SSE 回放与 `after_sequence` 续传；分页、`Last-Event-ID` 与 Electron fetch 连接细节仍待后续。当前后台执行只使用离线 `development-tools` Runtime；真实 Provider 的服务端配置、崩溃恢复/执行 claim 仍未实现。Electron 尚未接入前允许通过文档与契约测试审慎调整；Renderer 开始依赖后，任何破坏性修改必须新开版本或给出明确迁移策略。
