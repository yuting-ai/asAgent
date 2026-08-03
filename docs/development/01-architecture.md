# Ragent 目标架构

## 1. 架构目标

Ragent 采用模块化单体。所有后端能力在一个 Python 应用中运行，但模块边界明确，允许独立测试和替换边缘实现。

目标不是建立最多的抽象，而是保证以下关系清楚：

- 输入入口与 Agent Core 分离。
- Conversation 与单次 Run 分离。
- 用户消息与内部事件分离。
- 模型选择工具与工具实际执行分离。
- 长期状态与运行时对象分离。
- 程序资源与用户可写数据分离。
- Electron、Docker 和源码运行共享同一个 Python Core。

Ragent 的架构必须能够独立成立。`/Users/yuting/Desktop/BityDev/CowAgent` 只是在用户许可下用于比较具体实现的外部参考目录，不出现在 Ragent 的 import path、包依赖、启动参数、构建输入或运行时查找路径中。

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
Ragent/
├── AGENTS.md
├── pyproject.toml
├── src/
│   └── ragent/
│       ├── core/                 # ID、消息、事件、错误和基础接口
│       ├── chat/                 # Conversation、Message、ChatService
│       ├── agent/                # Runtime、Agent Loop、Context Builder
│       ├── models/               # 模型 Provider
│       ├── tools/                # Registry、Executor、Policy、内置工具、MCP
│       ├── memory/               # 摘要、个人记忆、检索
│       ├── workspace/            # WorkspaceResolver、作用域和权限
│       ├── storage/              # SQLite、Repository 实现和迁移
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

## 8. Chat 与 Channel 边界

当前实现 CLI 和 Local API。未来渠道通过同一个接口进入：

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

标准化对象至少覆盖：

- System Prompt。
- Messages。
- Tool Schemas。
- Model name。
- Token/usage 信息。
- Text delta、reasoning metadata 和 tool calls。

第一版实现一个 OpenAI-compatible Provider 和一个完全离线的 Fake Provider。测试默认使用 Fake Provider，避免费用和不稳定响应。

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
