# Conversation 与 Run

## 1. 核心区别

`Conversation` 是一段可长期继续的对话边界；`Run` 是 Agent 对一条用户请求的一次具体执行。

同一个 Conversation 可以包含许多轮用户提问和助手回答，因此也会关联多个 Run。Conversation 解决“哪些历史属于同一段对话”的问题；Run 解决“这一次执行是否在调用模型、调用了什么工具、是否失败或被取消”的问题。

两者不应合并成一个含义模糊的 `session_id`。如果混在一起，长期历史、一次执行状态、取消目标、工具审计和失败记录都会竞争同一个身份。拆分后，可以独立管理对话生命周期和单次执行生命周期。

这不是为了增加 Agent 的自主性，也不限制模型的决策。特别地，RunEvent 的 `sequence` 由系统在一个 Run 内单调递增地分配，用于排序和回放；它不是由模型或 Agent 自由调整的策略变量。

## 2. Conversation：长期对话边界

第一版的 Conversation 属于固定本地用户 `local-user`。它可以跨越多次用户输入、助手回复和 Run：今天的问题与明天的追问只要在同一 Conversation 中，就共享对话历史和未来的上下文边界。

Conversation 是用户可见历史的归属范围。未来 Context Builder 会从这段历史中选择需要发送给模型的内容；阶段 3 会将 Conversation、Message 和关联的 Run 持久化到 SQLite，使应用重启后仍能继续同一段对话。

当前最小 `Conversation` 对象包含：

- `conversation_id`：该对话的稳定身份；
- `user_id`：该对话所属用户；
- `created_at`：创建时间；
- `updated_at`：最近一次更新的时间。

标题、消息集合、持久化和生命周期操作尚未实现。

## 3. Run：一次请求的执行边界

当用户在一个 Conversation 中发送一条新请求时，系统通常创建一个新的 Run。这样可以独立追踪这次执行的状态，例如是否正在准备上下文、调用模型、执行工具、完成、失败、取消或达到步骤上限。

Run 通过 `conversation_id` 关联到所属 Conversation。一次 Run 的失败或取消不会破坏同一 Conversation 中已经存在的消息和其他 Run。是否重试、重试是创建新 Run 还是在某个边界内继续，是后续服务层需要明确规定的策略；无论采用哪种策略，都不能无声覆写原有执行记录。

Runtime 应尽量无状态：它在需要时从 Repository 读取长期状态，执行后再保存结果，而不是把对话和执行真相只保存在进程内存中。这样未来进程重启、SQLite 持久化和不同入口调用时，不会出现内存状态与长期状态分叉。

当前最小 `Run` 对象包含 `run_id`、`conversation_id`、`RunStatus`、`created_at` 和 `updated_at`。当前阶段只定义对象和状态枚举，还没有实现状态迁移或 Agent Runtime。

## 4. Message、RunEvent、ToolCall 与模型上下文

| 对象 | 谁主要使用 | 表达什么 | 是否直接展示在聊天历史 |
| --- | --- | --- | --- |
| Message | 用户、聊天 UI、历史加载 | 用户或助手可见的对话文本 | 是 |
| RunEvent | Runtime、调试/审计、流式 UI、回放 | Run 过程中的结构化变化，例如模型请求、文本增量、工具开始/结束、失败和完成 | 通常否；UI 可以显示少量状态 |
| ToolCall | Runtime、未来 ToolExecutor、审计 | 一次内部工具调用的参数、结果或错误 | 否 |
| 模型上下文 | ModelProvider | 实际发送给模型的标准化材料，如系统提示、选定历史、摘要和工具调用链 | 否 |

Message 分为 `UserMessage` 与 `AssistantMessage`，它们表达用户可见历史。RunEvent 不只记录工具调用，也记录 `run.started`、`model.delta`、`run.completed` 等执行过程。ToolCall 既可以表示内置计算器，也可以表示未来 MCP 工具；它不等同于“第三方工具”。

模型上下文必须独立建模，因为它是一次运行时发送给模型的材料，而不是完整数据库历史。未来它可能包含摘要、裁剪过的历史和合法的工具调用链，但这些内部材料不应直接显示为聊天消息。

## 5. 示例：使用计算器回答问题

假设用户在已有 Conversation 中问“2 + 2 等于多少？”，未来完整流程如下：

1. 找到已有 Conversation；如果用户新建对话，则创建 Conversation。
2. 保存一条用户可见的 `UserMessage`。
3. 创建新的 Run，初始状态为 `CREATED`。
4. 加载该 Conversation 的相关历史，构建模型上下文，并固定本次 Run 的 Tool Snapshot。
5. 记录模型请求相关 RunEvent，调用模型。
6. 模型返回计算器工具请求；其中的 Provider `call_id` 是模型协议中的调用身份。
7. Runtime 通过 Tool Snapshot 将 Provider 可见名称映射为内部 `tool_id`，创建内部 `ToolCall`，再依次进行参数校验、权限策略、可选批准、超时控制和实际执行。
8. 记录工具开始、完成或失败等 RunEvent，并把工具结果作为运行时材料补入模型上下文。
9. 再次调用模型，获得最终文本。
10. 保存用户可见的 `AssistantMessage`，将 Run 置为 `COMPLETED`，并记录结束事件。

其中，UserMessage 和 AssistantMessage 属于可见历史；Run、RunEvent 和 ToolCall 属于内部运行过程。

Provider `call_id` 与内部 `ToolCallId` 不能混用：前者由模型 Provider 协议产生，后者是 Ragent 自己稳定的内部身份。`event_id` 用于事件唯一标识和去重；每个 Run 从 1 开始单调递增的 `sequence` 用于严格排序、回放和 SSE 断线续传。

## 6. 当前阶段尚未实现的部分

- `ChatService`：接收用户输入，并在明确事务边界中创建 Message 和 Run。
- Agent Loop：驱动模型与工具反复交互，直至产生最终文本、失败、取消或达到限制。
- `ToolExecutor`：统一执行参数校验、权限、批准、超时、审计和结果截断。
- 内存和 SQLite Repository 实现：当前只有 Repository Protocol；阶段 1 先实现内存版，阶段 3 再实现 SQLite。
- Context Builder：从 Conversation 历史构建受预算限制的模型上下文。
- SSE 事件回放：未来依据 RunEvent 的 `sequence` 补发持久化事件并续传实时事件。
