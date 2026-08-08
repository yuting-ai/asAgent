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

必须防止：

- 同一工具和参数无限重复。
- 工具错误破坏 tool_use/tool_result 配对。
- 取消后留下不合法模型历史。
- 单个工具结果挤满上下文。
- 达到最大步骤后继续调用工具。

### 7.1 Run 内工具链完整性

一次工具回合从 assistant `tool_calls` 开始，到所有对应的 TOOL results 都追加到模型上下文后结束；它是不可拆分的上下文单元。Context Builder 只能在 Run 开始前或完整工具链之间裁剪历史，不能在当前 Run 内移除 assistant 请求、某个 TOOL result 或两者之一。

Loop 对一组 tool calls 按稳定顺序逐个执行。未知工具、参数错误和工具异常也必须为其 `tool_call_id` 形成明确的错误结果；这样下一次模型调用仍能看见完整事实，而非把失败静默丢失。若取消发生在已收到 tool calls 之后，Runtime 不得把这段未闭合的模型上下文用于后续调用；将来若需要保留或继续该上下文，必须先为未完成调用追加明确的取消结果。

取消检查点至少位于每次模型调用前、同一批工具的相邻执行之间，以及工具执行结束、结果追加前。重复调用检测以内部 `tool_id` 和规范化参数的组合为键；具体阈值和处置策略由实现任务通过测试确定，不能只依赖向模型追加提示词。

## 8. Chat 与 Channel 边界

阶段 1 先实现不依赖入口的最小 `ChatService`：调用方提供已创建的 `Conversation`、用户文本、模型名称和系统提示词；Service 保存 Conversation 与 UserMessage，读取该 Conversation 的可见历史并构造无工具的 `ModelRequest`，调用 `ModelProvider.complete()` 后保存并返回 AssistantMessage。时间和 Message ID 由构造函数注入，使 Service 不隐式依赖系统时间或随机数。当前不创建 Run、不处理流式或工具调用；Provider 异常时已保存的用户消息保留，工具调用响应会明确失败，等待阶段 2 的 Agent Loop。

阶段 1 的 `asagent` CLI 是薄的开发入口：它创建进程内 Conversation、`InMemoryConversationRepository` 和开发用 Echo Provider，再将终端的连续输入交给 `ChatService`。输入 `exit` 或 `quit` 时退出，Provider 异常显示为错误后返回输入循环。它不读取 API Key、不持久化历史，也不是正式产品界面；后续真实 Provider 与 Electron 入口复用同一 ChatService 边界。

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

Provider 的代码实现与用户选择的配置 Profile 分开。`models.config.ProviderConfig` 是 Pydantic 的系统配置边界：它校验适配器类型、模型名、HTTP Base URL、`secret_id` 与正超时值，并拒绝未知字段；`ProviderProfiles` 保存多个非空命名 Profile。API Key 不进入 Profile、仓库、日志或测试夹具。`models.secrets.SecretProvider` 只声明按 `secret_id` 返回 Secret 或缺失值的能力，尚不绑定具体存储实现。阶段 1 使用 `config_dir/providers.toml` 管理多个命名 Profile，并由后续 Keychain/Secret Store 适配器实现该 Protocol；开发期环境变量只能作为入口层显式后备，业务代码不直接读取。

`models.profile_loader.load_provider_profiles(config_dir)` 是该文件进入系统的唯一当前加载路径：它只读取 `config_dir/providers.toml`，使用标准库 `tomllib` 解析后交给 `ProviderProfiles` 验证；文件不存在、TOML 语法错误和 Profile Schema 错误统一转换为脱敏 `ProviderConfigurationError`。加载过程不创建目录、不读取 Secret、环境变量或 Keychain，也不选择或实例化 Provider。

开发入口可使用 `bootstrap.EnvironmentSecretProvider` 作为临时后备：入口显式传入环境 Mapping，并为每个 `secret_id` 提供允许的环境变量名称绑定。该适配器只读取绑定过且非空的值；它不导入 `os`、不扫描任意环境变量，也不被 Provider、ChatService 或 Core 直接构造。系统 Keychain/Secret Store 仍是后续正式实现。

`bootstrap.create_model_provider()` 是当前 Provider 组合根：它按 Profile 名称取得经验证配置，并将 `SecretProvider` 与由入口拥有生命周期的 `httpx.AsyncClient` 注入已实现的 Adapter。未知 Profile 与尚未实现的 Adapter 都转换为 `ProviderConfigurationError`；当前仅创建 OpenAI-compatible Adapter，Claude Profile 会明确拒绝而不伪装为兼容协议。

仓库提供 `scripts/check_deepseek.py` 作为可选手动连通性检查入口：它从被忽略的 `.local-data/config/providers.toml` 加载 Profile，并由该脚本显式将当前进程环境的指定变量绑定为 Secret。该脚本不属于 pytest 或 CLI 默认路径；它只在用户主动设置临时环境变量后发出一次最小请求，并只输出响应与 usage，不输出 Secret。

首个真实 Profile 为 `deepseek`，使用 `openai_compatible` Adapter。阶段 1 的 `OpenAICompatibleProvider` 使用注入的 `httpx.AsyncClient`、`ProviderConfig` 和 `SecretProvider` 发起 `POST /chat/completions`；它将标准化的 system/user/assistant Message、工具定义、一次性响应的文本/推理/工具调用/usage，以及 SSE 的文本和推理增量在边缘处互相映射。HTTP Client 的生命周期由未来组合根管理，Provider 不创建或关闭它。当前 Agent Loop 尚未存在，因此 Tool Message 和流式 ToolCall 明确拒绝而非静默生成不完整请求或事件。

Provider 边缘以 `ProviderError` 及其子类向上报告故障：配置/缺失 Secret、认证、余额、请求、响应格式、传输、限流和服务端错误彼此可区分；错误仅携带安全的类别与可选 HTTP 状态码，不保留响应正文、请求或 Secret。非流式 `complete()` 只对明确可重试的 HTTP 429 和 5xx 使用固定短延迟重试一次；401、402、400、422、响应格式错误、Secret 缺失及传输/超时均不重试。传输故障的结果可能不确定，自动重试会造成重复计费风险；流式调用一旦可能已产生增量，也绝不自动重试。后续入口可根据错误类别给用户可理解提示，后续可再评估 Provider 专用 backoff/Retry-After 支持。

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

### 10.3 Tool Snapshot

每个 Run 开始时确定一个工具快照，包含内部工具定义、Schema Hash 和 Provider 名称映射。即使 MCP Server 在运行中热更新，本次 Run 的 Schema 和名称映射保持稳定，下一个 Run 再使用新版本。

阶段 2 当前的最小运行时实现为 `tools.snapshot.ToolSnapshot`：它冻结按 Registry 顺序取得的 `ToolDefinition`、内部 `tool_id` 与 Provider 名称的双向 Binding，并导出对应的 `ModelToolDefinition`。当前 OpenAI-compatible 名称规则位于 `models.tool_names`，将不兼容字符规范化并限制为最多 64 个允许字符；名称碰撞在构造 Snapshot 时明确拒绝。Snapshot 还未写入 `Run` 或数据库，阶段 3 持久化时再将同一边界保存为可回放记录。

## 11. MCP 架构

阶段 8 才实现。结构为：

```text
config_dir/mcp.json
→ McpServerManager
→ McpClient
→ initialize（协议版本和能力协商）
→ notifications/initialized
→ tools/list（处理分页和 listChanged）
→ 每个远程工具包装为 ToolDefinition + Tool
→ 注册到 ToolRegistry
```

第一版只支持 stdio。稳定后再支持 Streamable HTTP、OAuth 和工具检索。

MCP 工具内部 ID：

```text
mcp:{server_name}:{tool_name}:{schema_hash}
```

不同 Server 提供同名工具时不得覆盖。

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

MCP 非敏感配置位于 `config_dir/mcp.json`，不放在 Workspace。Token、密码和带凭据的环境变量不写入该文件，交给系统 Keychain/Secret Store；SQLite 中的 `mcp_servers` 只保存运行状态、缓存和索引。

## 13. Memory 分层

```text
Working Memory       当前 Run 的临时信息
Conversation Summary 当前 Conversation 的摘要
User Memory          local-user 的长期偏好和事实
Knowledge            用户主动或 Agent 整理的结构化资料
```

第一版只做 Conversation History。Memory 按路线图后置，并先实现文本和关键词方案，再评估 Embedding。

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
