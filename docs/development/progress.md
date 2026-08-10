# asAgent 当前进度

## 1. 当前状态

- 项目阶段：阶段 3 已开始；阶段 2 的最小 ToolRegistry、ToolExecutor、三个内置工具、Agent Loop、安全边界、RunEvent、ToolCall 记录与内存态开发 CLI 垂直切片已完成；阶段 3 已完成 SQLite 初始 Schema、迁移基线、Conversation/Run Repository、Run 启动原子事务与运行时连接/事务基线
- 代码状态：已创建最小 `src/asagent` 包、Core ID 类型、不可变的 Conversation、用户可见 Message、Run、RunEvent、ToolCall 和 ToolDefinition 数据对象、Provider-neutral 模型交换数据类型、可脚本化的 `FakeModelProvider`、`ModelProvider`、Repository、`Tool`、`EventPublisher` 与 `SecretProvider` Protocol、`RunStatus` 状态枚举及 `AppPaths` 路径契约，并配置 pytest、pytest-asyncio、Ruff、strict mypy 与 `pydantic.mypy`；已提供内存版与 SQLite Conversation/Run Repository、最小 `ChatService`、开发 Agent CLI、OpenAI-compatible Provider、工具与 Agent Loop 能力，以及使用 SQLAlchemy Core、Alembic 与 SQLite 集成测试验证的初始持久化 Schema、连接 PRAGMA、事务行为、Run 回放查询和用户消息/初始 Run 的原子写入
- 项目路径：`/Users/yuting/Desktop/BityDev/asAgent`
- 当前日期：2026-08-10
- 当前目标：SQLite Run 启动原子事务已验证；下一步独立确定持久化 RunEvent 的 EventPublisher 适配边界

## 2. 已完成

- [x] 确认项目名称由 AsAgent 变更为 Ragent。
- [x] 确认最终项目名称恢复为 asAgent，并由 DEC-027 替代 Ragent 命名。
- [x] 完成 asAgent 命名迁移的本地质量验证。
- [x] 创建私有 GitHub 仓库、推送 `main`，并验证 GitHub Actions CI 首次成功运行。
- [x] 实现并验证阶段 2 的最小 ToolRegistry。
- [x] 实现并验证阶段 2 的最小 ToolExecutor。
- [x] 实现并验证阶段 2 的首个内置工具 `builtin.echo`。
- [x] 实现并验证阶段 2 的内置工具 `builtin.calculator`。
- [x] 实现并验证阶段 2 的内置工具 `builtin.current_time`。
- [x] 实现并验证阶段 2 的非流式工具消息契约与 OpenAI-compatible 映射。
- [x] 实现并验证阶段 2 的内部/Provider 工具名称映射与最小 Run Tool Snapshot。
- [x] 实现并验证阶段 2 的带 `max_steps` 最小非流式 Agent Loop。
- [x] 实现并验证阶段 2 的可配置重复工具调用检测。
- [x] 实现并验证阶段 2 的工具结果截断。
- [x] 实现并验证阶段 2 的基础 Run 取消令牌。
- [x] 实现并验证阶段 2 的最小 RunEvent 记录。
- [x] 实现并验证阶段 2 的内存态开发 CLI Agent 垂直切片。
- [x] 确认本地私有个人助手定位。
- [x] 确认默认单用户并预留 UserProvider。
- [x] 确认当前只实现本地对话入口。
- [x] 分析 CowAgent 的 Bridge、Workspace、Session 和 MCP 架构。
- [x] 识别 CowAgent 宏观架构可优化点。
- [x] 确认模块化单体目标架构。
- [x] 确认 Electron + Python Sidecar 边界。
- [x] 确认 HTTP + SSE 通信。
- [x] 确认 PyInstaller onedir 和 electron-builder 方向。
- [x] 确认 Docker 用于测试、CI 和可选 Server，而不是桌面依赖。
- [x] 确认 CowAgent 只作为按需、经用户确认的只读参考。
- [x] 建立开发路线和架构决策文档。
- [x] 完成跨文档一致性审查，修正阶段编号、取消/超时顺序、AppPaths 顺序和打包验证时点。
- [x] 明确 Backend 动态端口握手、SSE 认证/续传、RunEvent 顺序、Tool 名称映射和主数据边界。
- [x] 锁定阶段 0 技术选型：Python 3.13、uv、Pydantic 2、pytest/pytest-asyncio、Ruff 和 strict mypy。
- [x] 确认阶段 3 使用 SQLAlchemy 2.0 Core + aiosqlite + Alembic，不使用 ORM。
- [x] 实现并验证阶段 3 SQLite 初始 Schema、Alembic 迁移与约束集成测试。
- [x] 实现并验证阶段 3 SQLite Conversation Repository。
- [x] 实现并验证阶段 3 SQLite 运行时连接设置与事务基线。
- [x] 实现并验证阶段 3 SQLite Run Repository、RunEvent 回放与 ToolCall 持久化。
- [x] 实现并验证阶段 3 用户消息与初始 Run 的 SQLite 原子事务。
- [x] 初始化 Git 仓库。
- [x] 更新文档中的产品名、Python 包名、命令名和桌面资源名。
- [x] 将项目物理目录从 `AsAgent` 重命名为 `Ragent`。
- [x] 创建 Python 3.13 与 uv 最小项目骨架。
- [x] 配置 pytest、pytest-asyncio、Ruff、strict mypy 和 `pydantic.mypy`，建立最小质量检查闭环。
- [x] 创建 Core ID 类型：UserId、ConversationId、RunId、ToolCallId、EventId、MessageId。
- [x] 创建不可变的用户可见 `UserMessage` 和 `AssistantMessage` 模型。
- [x] 创建 `RunStatus` 状态枚举，并明确 `LIMIT_REACHED` 为终态。
- [x] 创建不可变的最小 `Run` 数据对象。
- [x] 创建可显式构造的 `AppPaths` 路径契约。
- [x] 创建不可变的最小 `RunEvent` 数据对象。
- [x] 创建不可变的最小 `ToolCall` 数据对象。
- [x] 创建 Provider-neutral 的模型交换数据类型。
- [x] 创建 `ModelProvider` Protocol。
- [x] 创建不可变的最小 `Conversation` 数据对象。
- [x] 创建 `ConversationRepository` 与 `RunRepository` Protocol。
- [x] 创建不可变的最小 `ToolDefinition` 数据对象。
- [x] 创建 `Tool` 与 `EventPublisher` Protocol。
- [x] 实现可脚本化的离线 `FakeModelProvider`。
- [x] 创建第一篇 `Conversation 与 Run` 学习笔记。
- [x] 添加最小测试 Dockerfile，并在干净 Linux 容器中验证。
- [x] 实现阶段 1 的内存版 Conversation Repository。
- [x] 实现阶段 1 的最小 ChatService。
- [x] 实现阶段 1 的 CLI 对话入口。
- [x] 确认阶段 1 首个真实模型 Provider 的选择与配置边界。
- [x] 定义并验证阶段 1 的 ProviderConfig 与 SecretProvider 边界。
- [x] 实现并离线验证阶段 1 的 OpenAI-compatible Provider。
- [x] 定义并验证阶段 1 的 Provider 错误转换与保守重试边界。
- [x] 实现并验证阶段 1 的 `providers.toml` 非敏感 Profile 配置加载。
- [x] 实现并验证阶段 1 的开发入口环境 Secret 后备。
- [x] 在组合根按 Profile 创建 OpenAI-compatible Provider。
- [x] 完成阶段 1 的可选真实 DeepSeek 手动连通性验证。
- [x] 在 Docker 干净 Linux 环境完成阶段 1 收尾验收。

## 3. 尚未开始

- [x] 创建阶段 1 收尾后的统一本地质量门禁 Pipeline。
- [x] 创建 GitHub Actions CI workflow，复用离线质量门禁。
- [x] 创建阶段 2 的最小 ToolRegistry。
- [x] 实现阶段 2 的最小 ToolExecutor。
- [x] 实现阶段 2 的首个内置工具 `builtin.echo`。
- [x] 实现阶段 2 的内置工具 `builtin.calculator`。
- [x] 实现阶段 2 的内置工具 `builtin.current_time`。
- [x] 实现阶段 2 的非流式工具消息契约与 OpenAI-compatible 映射。
- [x] 实现阶段 2 的内部/Provider 工具名称映射与最小 Run Tool Snapshot。
- [x] 实现阶段 2 的最小 Agent Loop 与最大决策步数。
- [x] 实现阶段 2 的可配置重复工具调用检测。
- [x] 实现阶段 2 的工具结果截断。
- [x] 实现阶段 2 的基础 Run 取消令牌。

## 4. 阶段 0（已完成）

### 目标

建立一个不依赖真实模型、Web、Electron 和数据库的可测试核心骨架。

### 建议执行顺序

1. 初始化 Git 和 Python 工程。
2. 建立最小目录，不提前创建所有未来空模块。
3. 定义领域对象和接口。
4. 实现 Fake Model。
5. 编写单元测试。
6. 记录第一篇学习笔记。
7. 添加最小测试 Dockerfile。
8. 更新本文件。

### 阶段 0 待办

- [x] 确认 Python 3.13，项目版本范围为 `>=3.13,<3.14`。
- [x] 确认 uv，并提交 `uv.lock`。
- [x] 确认 Pydantic 2 主要用于系统边界。
- [x] 确认 pytest + pytest-asyncio + Ruff。
- [x] 确认 strict mypy + `pydantic.mypy`。
- [x] 创建 `pyproject.toml`。
- [x] 配置测试、Lint、格式化和类型检查，并建立同步/异步测试约定。
- [x] 创建 `src/ragent/core/`。
- [x] 创建顶层 `src/ragent/paths.py`，定义可显式构造的 `AppPaths`。
- [x] 创建 ID 类型：UserId、ConversationId、RunId、ToolCallId、EventId、MessageId。
- [x] 创建不可变的用户可见 `UserMessage` 和 `AssistantMessage` 数据对象。
- [x] 创建 `RunStatus` 状态枚举；`LIMIT_REACHED` 是明确终态，不视为成功完成。
- [x] 创建不可变的最小 `Run` 数据对象。
- [x] 创建不可变的最小 RunEvent 数据对象；包含 `event_id`、从 1 开始的 `sequence` 和只读顶层 `data` 快照。
- [x] 创建不可变的最小 ToolCall 数据对象；包含调用参数快照，以及互斥的结果或错误。
- [x] 定义 Provider-neutral 的 `ModelMessage`、`ModelToolDefinition`、`ModelToolCall`、`ModelRequest`、`ModelResponse` 和 `ModelEvent` 数据类型。
- [x] 定义 `ModelProvider` Protocol，支持一次性 `complete()` 与异步迭代 `stream()`。
- [x] 创建不可变的最小 `Conversation` 数据对象；包含 Conversation 身份、所属用户和创建/更新时间。
- [x] 定义异步 `ConversationRepository` 与 `RunRepository` Protocol；事件查询使用 `after_sequence` 续传点。
- [x] 创建不可变的最小 `ToolDefinition`；包含工具元数据、顶层 Schema 快照、权限、批准要求与正数超时。
- [x] 定义异步 `Tool` 与 `EventPublisher` Protocol；工具执行与事件发布均不包含后续的横切实现细节。
- [x] 实现可脚本化的 `FakeModelProvider`；支持预设文本、工具调用和流式事件。
- [x] 为核心对象和 Fake Model 编写测试。
- [x] 创建 `docs/learning-notes/01-conversation-and-run.md`。
- [x] 添加最小测试 Dockerfile；使用提交的锁文件在干净 Linux 容器中运行测试、Ruff、mypy 和锁文件检查。

### 阶段 0 验收

- [x] `pytest` 全部通过。
- [x] Ruff 检查通过。
- [x] 类型检查通过。
- [x] 测试无需网络和 API Key。
- [x] Core 不依赖 FastAPI、Electron、SQLite 或模型 SDK。
- [x] Fake Model 能预设文本响应和 ToolCall 响应。
- [x] AppPaths 的开发、测试和发布构造方式有测试，业务代码不读取或拼接用户主目录。

## 5. 新 Codex 任务启动提示词

在 asAgent 项目下创建新任务后，使用：

```text
请先完整阅读项目根目录 AGENTS.md，以及其中列出的 docs/development 全部文档。

暂时不要写代码。请先总结：
1. asAgent 的产品定位和当前范围；
2. Conversation、Run、Message、RunEvent、ToolCall 的关系；
3. Python Core、Local API、Electron、PyInstaller 和 Docker 的边界，以及 Backend 动态端口握手与 SSE 认证方式；
4. 已确认决策与仍待确认问题；
5. 阶段 0 的任务和验收条件。
6. CowAgent 参考策略，以及当前任务是否真的需要参考 CowAgent。
7. RunEvent 的 event_id/sequence 分工、Tool ID/Provider 名称映射，以及文件与 SQLite 的主数据边界。

总结完成后，提出阶段 0 的最小实施计划，等待我确认再开始编码。
```

## 6. 进度更新模板

每次完成工作后更新：

```markdown
## YYYY-MM-DD 工作记录

### 完成
- ...

### 验证
- 命令：...
- 结果：...

### 决策变化
- 无 / DEC-XXX

### 风险或问题
- ...

### 下一步
- ...
```

## 7. 当前风险

- 第一目标操作系统尚未正式确认。
- 首个真实 Provider 已选择 DeepSeek；系统 Secret Store 的具体接入实现尚未开始。

## 8. 重要提醒

- 当前计划是可调整的，但任何架构变化要先写入决策文档。
- 阶段 0 不开发 Electron UI、MCP、Memory 或真实 Channel。
- CowAgent 位于 `/Users/yuting/Desktop/BityDev/CowAgent`，但不能自动参考。只有用户主动要求，或 Codex 说明具体目的并获得确认后，才读取必要文件；不默认复制其代码，也不建立运行时依赖。
- 每个阶段都需要以可运行、可测试和可解释作为完成标准。

## 9. 2026-07-31 工作记录

### 完成

- 锁定阶段 0 Python 与工程工具链。
- 解决 SQLite 访问方式和迁移方案开放项。
- 同步架构决策、开发路线和当前进度。
- 将项目名称由 AsAgent 更新为 Ragent，并同步未来包名、命令名和桌面资源名。
- 将项目物理目录从 `AsAgent` 重命名为 `Ragent`，并同步决策与进度文档中的路径状态。
- 创建 `.python-version`、`pyproject.toml`、`uv.lock` 和 `src/ragent`，完成 Python 3.13 与 uv 最小工程骨架。
- 声明 Pydantic 运行时依赖和 pytest、pytest-asyncio、Ruff、mypy 开发依赖，配置统一测试、Lint、格式化和 strict 类型检查规则。
- 创建 `tests/unit/test_package.py`，验证 `src` 包导入和 pytest-asyncio 函数级事件循环。
- 创建 `core/ids.py` 和 ID 类型测试，使用 `NewType` 将六类字符串身份在静态检查中分离。
- 新增 `MessageId`，并通过 DEC-024 明确它只提供 Message 稳定身份，不承担 Conversation 内排序。
- 创建不可变的 `UserMessage` 和 `AssistantMessage` 数据对象及其单元测试；消息角色由类型表达，Message 不在此阶段关联 Run。
- 创建 `RunStatus` 的字符串枚举和 `is_terminal` 查询；状态集合与 Agent Loop 状态机一致，`COMPLETED`、`CANCELLED`、`FAILED` 与 `LIMIT_REACHED` 为终态。
- 创建不可变的最小 `Run` 数据对象，包含运行身份、所属 Conversation、状态和创建/更新时间；暂不关联具体 Message，也不实现状态迁移。
- 创建顶层 `AppPaths` 路径契约；入口通过 `from_root()` 或显式字段提供路径，业务代码不读取用户主目录，构造过程不创建目录。
- 创建不可变的最小 `RunEvent` 数据对象；`event_id` 用于唯一标识和去重，`sequence` 用于 Run 内排序与未来回放，事件数据保留只读顶层快照。
- 创建不可变的最小 `ToolCall` 数据对象；调用参数保留只读顶层快照，完成结果与错误互斥，二者都为空时表示待执行。
- 创建 Provider-neutral 的模型交换数据类型；请求、响应和流事件与用户可见 Message、内部 RunEvent 分开建模，Provider 工具调用保留独立的 `call_id`。
- 创建可运行时检查的 `ModelProvider` Protocol；一次性调用返回 `ModelResponse`，流式调用直接返回可由 `async for` 消费的 `AsyncIterator[ModelEvent]`。

### 验证

- 检查：全文搜索旧的 Python 3.12、mypy/pyright 和 SQLite 待选表述。
- 结果：通过；旧表述只保留在 DEC-022 的“替代方案”历史说明中。
- 检查：确认当前工作目录为 `/Users/yuting/Desktop/BityDev/Ragent`，Git 分支为 `main`，且目录重命名前工作区为 clean。
- 结果：通过；最新基线提交为 `cb99b48 chore: establish initial project baseline`。
- 检查：运行 `uv lock --check`，验证锁文件与项目元数据一致。
- 结果：通过；使用 CPython 3.13.14。
- 检查：运行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv lock --check` 和 `git diff --check`。
- 结果：通过；2 个测试通过，Ruff 与 strict mypy 无问题，锁文件和 diff 检查通过。
- 检查：运行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv lock --check` 和 `git diff --check`。
- 结果：通过；3 个测试通过，五种 ID 的运行时字符串语义和静态类型断言均已验证。
- 检查：运行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv lock --check` 和 `git diff --check`。
- 结果：通过；5 个测试通过，用户可见 Message 的字段保留与不可变性均已验证，Ruff、strict mypy、锁文件和 diff 检查无问题。
- 检查：运行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv lock --check` 和 `git diff --check`。
- 结果：通过；8 个测试通过，RunStatus 的稳定字符串值和终态判断均已验证，Ruff、strict mypy、锁文件和 diff 检查无问题。
- 检查：运行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv lock --check` 和 `git diff --check`。
- 结果：通过；10 个测试通过，Run 的字段保留与不可变性均已验证，Ruff、strict mypy、锁文件和 diff 检查无问题。
- 检查：运行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv lock --check` 和 `git diff --check`。
- 结果：通过；14 个测试通过，AppPaths 的稳定目录映射、显式构造、无副作用和不可变性均已验证，Ruff、strict mypy、锁文件和 diff 检查无问题。
- 检查：运行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv lock --check` 和 `git diff --check`。
- 结果：通过；17 个测试通过，RunEvent 的身份、顺序、顶层负载快照和不可变性均已验证，Ruff、strict mypy、锁文件和 diff 检查无问题。
- 检查：运行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv lock --check` 和 `git diff --check`。
- 结果：通过；21 个测试通过，ToolCall 的调用信息、待执行状态、参数快照和结果/错误互斥规则均已验证，Ruff、strict mypy、锁文件和 diff 检查无问题。
- 检查：运行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv lock --check` 和 `git diff --check`。
- 结果：通过；25 个测试通过，模型交换类型的请求、响应、流事件、工具调用与顶层参数 Schema 快照均已验证，Ruff、strict mypy、锁文件和 diff 检查无问题。
- 检查：运行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv lock --check` 和 `git diff --check`。
- 结果：通过；27 个测试通过，ModelProvider 的结构化兼容性、一次性调用和异步事件流均已验证，Ruff、strict mypy、锁文件和 diff 检查无问题。

### 决策变化

- 新增 DEC-022、DEC-023、DEC-024。

### 风险或问题

- 第一目标操作系统和第一家真实模型服务仍待确认，但不阻塞阶段 0。

### 下一步

- 在下一个独立任务中为 Repository Protocol 定义最小验收样例；本次不开始该任务。

## 2026-08-04 工作记录

### 完成

- 创建不可变的最小 `Conversation` 数据对象，作为后续 `ConversationRepository` 的类型完整返回值。
- Conversation 包含 `conversation_id`、`user_id`、`created_at` 与 `updated_at`；标题、消息集合、持久化和生命周期操作仍留给后续任务。
- 创建异步 `ConversationRepository` 与 `RunRepository` Protocol；前者管理 Conversation 与可见 Message，后者管理 Run、RunEvent 与 ToolCall。
- 创建不可变的最小 `ToolDefinition` 数据对象，保存工具元数据和执行前的安全要求，但不实现执行或策略。
- 创建异步 `Tool` 与 `EventPublisher` Protocol；具体 Tool 只执行准备好的参数，事件发布与事件历史查询保持分离。
- 创建可脚本化的离线 `FakeModelProvider`；按调用顺序消费预设的一次性响应或流事件脚本，并保留请求历史供测试断言。
- 创建第一篇学习笔记，说明 Conversation 与 Run 的不同生命周期，以及 Message、RunEvent、ToolCall 和模型上下文的职责边界。

### 验证

- 检查：运行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv lock --check` 和 `git diff --check`。
- 结果：通过；29 个测试通过，Ruff 与 strict mypy 无问题，锁文件和 diff 检查通过。
- 检查：运行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv lock --check` 和 `git diff --check`。
- 结果：通过；31 个测试通过，两个类型完整的异步示例 Repository 满足 Protocol，Ruff 与 strict mypy 无问题，锁文件和 diff 检查通过。
- 检查：运行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv lock --check` 和 `git diff --check`。
- 结果：通过；34 个测试通过，ToolDefinition 的元数据、顶层 Schema 快照、正数超时与不可变性均已验证，Ruff 与 strict mypy 无问题，锁文件和 diff 检查通过。
- 检查：运行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv lock --check` 和 `git diff --check`。
- 结果：通过；36 个测试通过，示例 Tool 与事件收集器满足异步 Protocol，Ruff 与 strict mypy 无问题，锁文件和 diff 检查通过。
- 检查：运行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv lock --check` 和 `git diff --check`。
- 结果：通过；39 个测试通过，FakeModelProvider 的文本、工具调用、流事件、请求历史与未脚本化调用失败路径均已验证，Ruff 与 strict mypy 无问题，锁文件和 diff 检查通过。
- 检查：运行 `git diff --check`，并复核学习笔记中的领域关系和当前未实现范围。
- 结果：通过；笔记清楚区分 Conversation、Run、Message、RunEvent、ToolCall 和模型上下文，且没有将未来实现误记为当前能力。

### 决策变化

- 无；本次仅记录既有领域边界的学习笔记，不改变架构决策。

### 风险或问题

- 无。

### 下一步

- 添加最小测试 Dockerfile。

## 2026-08-05 工作记录

### 完成

- 创建 `docker/Dockerfile.test`，以 Python 3.13 和 uv 0.12.0 在干净 Linux 容器中安装锁定依赖。
- 创建 `.dockerignore`，排除 Git 元数据、本地虚拟环境、缓存、本地数据和环境变量，避免它们进入镜像构建上下文。
- 将 Docker 测试命令确定为直接构建并运行 `docker/Dockerfile.test`；当前阶段不需要 Docker Compose。

### 验证

- 检查：运行 `docker build --file docker/Dockerfile.test --tag ragent-tests:local .` 与 `docker run --rm ragent-tests:local`。
- 结果：通过；容器使用 Linux CPython 3.13.14，39 个测试通过，Ruff 检查与格式检查通过，strict mypy 无问题，`uv lock --check` 通过。
- 检查：运行本机完整质量门禁、`FakeModelProvider`/`AppPaths` 定向测试，以及 Core 依赖和网络/API Key/环境变量读取的静态搜索。
- 结果：通过；本机 39 个测试、Ruff、格式检查、strict mypy、锁文件与 diff 检查均通过；7 个定向测试通过；静态搜索无匹配，确认当前阶段的 Core 和离线测试边界。

### 决策变化

- 无；本次落实既有 Docker 测试/CI 边界，不改变 Docker 作为非桌面运行依赖的定位。

### 风险或问题

- 无。

### 下一步

- 阶段 0 已完成；在下一个独立任务中实现阶段 1 的内存版 Conversation Repository，本次不开始该任务。

## 2026-08-05 阶段 1 工作记录

### 完成

- 在 `storage` 创建 `InMemoryConversationRepository`，作为既有异步 `ConversationRepository` Protocol 的首个具体实现。
- Conversation 以稳定 `conversation_id` 覆盖保存并按 `user_id` 查询；Message 按追加顺序隔离保存，且拒绝向未保存 Conversation 写入孤儿 Message。
- 内存数据只在当前 Python 进程存活，后续 SQLite Repository 将保持同一 Protocol。

### 验证

- 检查：运行 `uv run pytest tests/unit/test_in_memory_conversation_repository.py`。
- 结果：通过；3 个测试覆盖 Protocol 兼容性、Conversation 覆盖与用户隔离、Message 顺序/隔离和孤儿 Message 拒绝。
- 检查：运行完整质量门禁。
- 结果：通过；42 个测试通过，Ruff、格式检查、strict mypy、锁文件和 diff 检查均无问题。

### 决策变化

- 无；内存实现遵循既有 Repository 边界，不改变长期 SQLite 主数据决策。

### 风险或问题

- 无；该实现按设计不跨进程持久化，不能替代阶段 3 的 SQLite Repository。

### 下一步

- 在下一个独立任务中实现最小 ChatService；本次不开始该任务。

## 2026-08-05 阶段 1 ChatService 工作记录

### 完成

- 在 `chat` 创建最小 `ChatService`，协调 Conversation Repository 与 ModelProvider 完成一次非流式文本对话。
- 每次发送先保存 Conversation 和 UserMessage，再将该 Conversation 的可见历史转换为 Provider-neutral `ModelRequest`；成功文本响应保存为 AssistantMessage。
- 时间和 Message ID 通过构造函数注入；Provider 失败时用户消息保留，工具调用响应明确拒绝，未提前实现 Run、流式或 Agent Loop。
- 修正架构文档中 CLI 与 Local API 已实现的旧表述；当前它们仍是后续入口。

### 验证

- 检查：运行 `uv run pytest tests/unit/test_chat_service.py`。
- 结果：通过；3 个测试覆盖连续历史、Provider 失败后保留用户消息和阶段 2 前拒绝工具调用。
- 检查：运行完整质量门禁。
- 结果：通过；45 个测试通过，Ruff、格式检查、strict mypy、锁文件和 diff 检查均无问题。

### 决策变化

- 无；本次实现既有 Chat/Model/Repository 边界，不新增架构决策。

### 风险或问题

- 无；当前 ChatService 只支持非流式文本响应，工具调用和 Run 生命周期按路线图留给后续阶段。

### 下一步

- 在下一个独立任务中实现 CLI 对话入口；本次不开始该任务。

## 2026-08-06 阶段 1 CLI 工作记录

### 完成

- 新增 `ragent` 控制台脚本，作为复用 ChatService 的最小开发入口。
- CLI 在进程内创建 Conversation、内存 Repository 和开发 Echo Provider；支持连续输入、`exit`/`quit` 退出、EOF 退出以及显示 Provider 错误后继续接收输入。
- 开发 Echo Provider 不读取网络、Secret 或 API Key，只用于验证 CLI 到 ChatService 的本地闭环。

### 验证

- 检查：运行 `uv run pytest tests/unit/test_cli.py`。
- 结果：通过；3 个测试覆盖连续多轮、Provider 错误恢复和 EOF 退出。
- 检查：运行 `uv run ragent`，输入 `hi` 后输入 `exit`。
- 结果：通过；终端显示 `Echo: hi` 并正常退出。
- 检查：运行完整质量门禁。
- 结果：通过；48 个测试通过，Ruff、格式检查、strict mypy、锁文件和 diff 检查均无问题。

### 决策变化

- 无；CLI 只是既有 ChatService 边界的开发适配器，首个真实 Provider 仍未选择。

### 风险或问题

- 首个真实模型 Provider 与对应 Secret/配置边界仍待用户确认，阶段 1 尚未完成。

### 下一步

- 在下一个独立任务中确认首个真实模型 Provider 的选择与配置边界；本次不开始该任务。

## 2026-08-06 Provider 配置决策工作记录

### 完成

- 确认 DeepSeek 为首个真实模型 Profile，使用 OpenAI-compatible Adapter。
- 确认以单一 `config_dir/providers.toml` 中的命名 Profile 管理非敏感 Provider 参数；OpenAI 等兼容服务复用 Adapter，Claude 使用独立原生 Adapter。
- 确认 API Key 仅由 `secret_id` 引用，后续从系统 Secret Store 获取，不进入配置文件或业务层。

### 验证

- 检查：复核 DeepSeek 与 Claude 官方 API 文档，以及现有 Provider-neutral `ModelProvider` 边界。
- 结果：通过；兼容服务与原生 Messages API 的协议差异已被明确隔离，当前设计不需要读取或复制 CowAgent。

### 决策变化

- 新增 DEC-025。

### 风险或问题

- SecretProvider、系统 Keychain/Secret Store 接入和真实 HTTP 调用尚未实现；测试仍必须默认离线。

### 下一步

- 在下一个独立任务中定义 ProviderConfig 与 SecretProvider 边界；本次不开始该任务。

## 2026-08-06 ProviderConfig 与 SecretProvider 工作记录

### 完成

- 新增 Pydantic `ProviderConfig` 与 `ProviderProfiles`，校验命名 Profile 的适配器、模型名、HTTP Base URL、`secret_id` 与正超时值，并拒绝未知字段和空 Profile 名称。
- 新增运行时可检查的 `SecretProvider` Protocol；它只按 `secret_id` 返回值或缺失值，未实现 Keychain、环境变量或任何真实 Secret 读取。
- 配置与 Secret 抽象位于 `models` 边界，Core、ChatService 和 CLI 保持不读取 API Key 的既有约束。

### 验证

- 检查：运行 Provider 配置和 Secret Protocol 的定向测试。
- 结果：通过；5 个 Provider 配置测试与 1 个 Secret Protocol 测试覆盖两种适配器、默认/显式超时、无效配置、Profile 名称和缺失 Secret。
- 检查：运行完整质量门禁。
- 结果：通过；54 个测试通过，Ruff、格式检查、strict mypy、锁文件与 diff 检查均无问题。

### 决策变化

- 无；本次落实 DEC-025 的配置与 Secret 引用边界，未改变真实 Provider、密钥存储或网络调用决策。

### 风险或问题

- 系统 Keychain/Secret Store 适配器、配置文件加载和真实 DeepSeek HTTP 调用仍未实现；当前测试继续完全离线，仓库中没有真实 API Key。

### 下一步

- 在下一个独立任务中实现使用 `ProviderConfig` 与 `SecretProvider` 的 DeepSeek OpenAI-compatible Provider；本次不开始该任务。

## 2026-08-07 OpenAI-compatible Provider 工作记录

### 完成

- 新增基于注入 `httpx.AsyncClient` 的 `OpenAICompatibleProvider`；它由 `ProviderConfig`、`SecretProvider` 和 Provider-neutral `ModelRequest` 组合，不引入 DeepSeek SDK 或厂商对象到 Core。
- 实现 `POST /chat/completions` 的 system/user/assistant Message、工具定义、文本/推理/工具调用、token usage 映射，以及 SSE 文本和推理增量映射。
- 缺失 Secret 时在请求前明确失败。Tool Message 与流式 ToolCall 因阶段 2 Agent Loop 尚未实现而明确拒绝，避免静默丢失协议信息。

### 验证

- 检查：使用 `httpx.MockTransport` 运行 OpenAI-compatible Provider 单元测试。
- 结果：通过；4 个离线测试覆盖一次性请求/响应映射、SSE 文本与推理增量、缺失 Secret 不发请求，以及流式 ToolCall 的明确拒绝。
- 检查：运行完整质量门禁。
- 结果：通过；58 个测试通过，Ruff、格式检查、strict mypy、锁文件与 diff 检查均无问题。

### 决策变化

- 无；本次使用 DEC-025 已确认的通用协议 Adapter 方案，未改变 Provider、Secret 或桌面架构决策。

### 风险或问题

- HTTP 状态错误转换、重试策略、配置文件加载、系统 Keychain/Secret Store，以及真实 Key 的手动连通性检查仍未实现；测试保持离线。

### 下一步

- 在下一个独立任务中定义 Provider 错误转换与重试边界；本次不开始该任务。

## 2026-08-07 Provider 错误与重试工作记录

### 完成

- 新增脱敏 `ProviderError` 分类：配置、认证、余额、请求、响应格式、传输、限流和服务端错误可被入口稳定区分，错误不保存服务端响应正文、请求或 Secret。
- `OpenAICompatibleProvider.complete()` 仅对 HTTP 429 和 5xx 以固定短延迟重试一次；其他 HTTP 状态、Secret 缺失、无效 JSON/响应及传输错误均明确不重试。
- 流式调用转换 HTTP、传输和响应格式错误，但不自动重试，避免重复展示已经产生的增量。

### 验证

- 检查：运行 OpenAI-compatible Provider 定向测试。
- 结果：通过；8 个测试覆盖正常映射、SSE、缺失 Secret、流式 ToolCall 拒绝、429 单次重试、401 不重试、传输错误不重试与无效 JSON 的脱敏包装。
- 检查：运行完整质量门禁。
- 结果：通过；62 个测试通过，Ruff、格式检查、strict mypy、锁文件与 diff 检查均无问题。

### 决策变化

- 新增 DEC-026：Provider 错误分类与保守重试。

### 风险或问题

- 当前固定重试延迟不解析 `Retry-After`，也未实现指数退避；真实连通性、配置文件加载和系统 Secret Store 仍未实现。

### 下一步

- 在下一个独立任务中加载 `providers.toml` 的非敏感 Profile 配置；本次不开始该任务。

## 2026-08-07 Provider Profile 配置加载工作记录

### 完成

- 新增 `load_provider_profiles(config_dir)`，从 `config_dir/providers.toml` 读取非敏感命名 Profile，并通过既有 Pydantic `ProviderProfiles` 验证。
- 使用 Python 标准库 `tomllib`，不增加依赖；文件缺失、无效 TOML 与无效 Profile 数据统一转换为脱敏 `ProviderConfigurationError`。
- 加载操作不创建目录，不读取 Secret、环境变量或 Keychain，也不改变 CLI 的离线 Echo Provider。

### 验证

- 检查：运行 Profile Loader 定向测试。
- 结果：通过；4 个测试覆盖有效多 Profile、缺失文件无副作用、无效 TOML 与无效配置数据。
- 检查：运行完整质量门禁。
- 结果：通过；66 个测试通过，Ruff、格式检查、strict mypy、锁文件与 diff 检查均无问题。

### 决策变化

- 无；本次落实 DEC-025 的 Profile 文件边界，不改变 Secret 存储或 Provider Adapter 决策。

### 风险或问题

- 当前没有系统 Secret Store 或开发入口后备实现，也尚未在组合根按 Profile 创建实际 Provider；CLI 继续默认离线。

### 下一步

- 在下一个独立任务中定义 SecretProvider 的开发入口后备实现；本次不开始该任务。

## 2026-08-07 开发环境 Secret 后备工作记录

### 完成

- 新增 `EnvironmentSecretProvider`，通过显式 `secret_id` 到环境变量名称的绑定从注入的环境 Mapping 读取开发 Secret。
- 未绑定、缺失或空 Secret 一律返回缺失值；适配器不导入 `os`，也不扫描任意系统环境变量。
- Provider、ChatService 与 Core 继续只依赖 `SecretProvider` Protocol；实际环境读取仍只允许由未来组合根显式执行。

### 验证

- 检查：运行 EnvironmentSecretProvider 定向测试和完整质量门禁。
- 结果：通过；3 个定向测试覆盖显式绑定、拒绝未绑定读取和缺失/空值；完整 69 个测试通过，Ruff、格式检查、strict mypy、锁文件与 diff 检查均无问题。

### 决策变化

- 无；本次实现 DEC-025 的开发期入口后备约束，不替代未来系统 Secret Store。

### 风险或问题

- 尚未实现正式 Keychain/Secret Store，也尚未由组合根创建真实 Provider；CLI 继续默认离线。

### 下一步

- 在下一个独立任务中在组合根按 Profile 创建 OpenAI-compatible Provider；本次不开始该任务。

## 2026-08-07 Provider 组合根工作记录

### 完成

- 新增 `create_model_provider()`，按命名 Profile 将 ProviderConfig、SecretProvider 和入口拥有的 AsyncClient 组合为 ModelProvider。
- 当前仅创建 OpenAI-compatible Adapter；未知 Profile 与未实现的 Anthropic Adapter 明确转换为 ProviderConfigurationError。
- 工厂不读取文件、环境变量或 Secret，也不创建、关闭或发起 HTTP Client 请求。

### 验证

- 检查：运行 Provider Factory 定向测试和完整质量门禁。
- 结果：通过；3 个定向测试覆盖 DeepSeek Adapter 创建、未知 Profile 与未实现 Adapter；完整 72 个测试通过，Ruff、格式检查、strict mypy、锁文件与 diff 检查均无问题。

### 决策变化

- 无；本次按 DEC-025 组合既有 Profile、Secret 与 Adapter 边界。

### 风险或问题

- CLI 仍只运行离线 Echo Provider；真实 DeepSeek 连通性验证必须保持可选，不能使用仓库或默认测试中的 Secret。

### 下一步

- 在下一个独立任务中设计可选的真实 DeepSeek 手动连通性验证；本次不开始该任务。

## 2026-08-07 DeepSeek 手动连通性验证工作记录

### 完成

- 新增可选 `scripts/check_deepseek.py`，作为开发入口显式加载本地忽略的 Profile 配置、绑定临时环境 Secret，并创建 OpenAI-compatible Provider 发起一次最小请求。
- 手动调用 DeepSeek 成功；响应为预期确认文本，记录到 95 输入 token 与 45 输出 token。
- 该脚本不属于默认 pytest 或开发 CLI；Profile 和 API Key 均不进入仓库。

### 验证

- 检查：运行脚本的 Ruff、Ruff check 与 strict mypy。
- 结果：通过；脚本格式、Lint 和类型检查均无问题。
- 检查：用户在当前终端临时设置环境变量后运行 `uv run python scripts/check_deepseek.py`。
- 结果：通过；真实 DeepSeek 返回预期文本与 usage，终端输出未包含 API Key。

### 决策变化

- 无；本次只验证既有 DEC-025 Provider 路径，不改变 CLI 默认离线策略。

### 风险或问题

- 临时环境变量应在验证结束后从当前 Shell 清除；系统 Keychain/Secret Store 和正式入口选择仍未实现。

### 下一步

- 确认阶段 1 的收尾范围与进入阶段 2 的前置条件；本次不开始下一阶段。

## 2026-08-07 阶段 1 Docker 收尾验收

### 完成

- 在 Docker 干净 Linux 环境重新构建并验证完整阶段 1 代码与锁定依赖。
- 阶段 1 的连续 CLI、离线 Fake 路径、Profile/Secret/Provider 组合、脱敏错误处理及可选真实连通性验证均已满足最小聊天目标；阶段 2 尚未开始。

### 验证

- 检查：运行 `docker build --file docker/Dockerfile.test --tag ragent-tests:local .` 与 `docker run --rm ragent-tests:local`。
- 结果：通过；Linux CPython 3.13.14 中 72 个测试通过，Ruff、格式检查、strict mypy 与 `uv lock --check` 均通过。构建与测试未使用本机 `.local-data` 或真实 API Key。

### 决策变化

- 无；本次确认阶段 1 的既有验收条件，不改变 Provider、Docker 或桌面边界。

### 风险或问题

- Claude 原生 Adapter、正式系统 Secret Store 与 usage 的持久化均为后续独立工作；它们不阻塞阶段 1 的最小聊天闭环。

### 下一步

- 在下一个独立任务中评估并创建 GitHub Actions CI，复用离线质量门禁；本次不开始该任务。

## 2026-08-07 本地质量门禁 Pipeline 工作记录

### 完成

- 新增可执行 `scripts/check.sh`，按固定顺序运行 pytest、Ruff Lint、Ruff 格式检查、strict mypy、锁文件检查和 diff 检查。
- 该入口作为每个独立小任务结束时的统一本地验收，不使用文件监听，也不替代 Docker 干净环境验证。

### 验证

- 检查：执行 `scripts/check.sh`。
- 结果：通过；72 个测试通过，Ruff、格式检查、strict mypy、锁文件与 diff 检查均无问题。

### 决策变化

- 无；本次落实路线图的阶段 1 收尾 Pipeline 计划，不引入 pre-commit 或远程 CI。

### 风险或问题

- 本地脚本不能替代独立 Runner；GitHub Actions CI 仍待在代码托管远端建立。

### 下一步

- 在下一个独立任务中评估并创建 GitHub Actions CI，复用离线质量门禁；本次不开始该任务。

## 2026-08-07 GitHub Actions CI 工作记录

### 完成

- 新增 `.github/workflows/ci.yml`；它在 `push` 和 `pull_request` 时运行一个 Ubuntu Runner。
- Workflow 从提交的 `.python-version` 设置 Python，安装 uv，并通过 `uv sync --locked` 安装锁定依赖。
- CI 最后复用 `scripts/check.sh`，因此云端与本地执行同一套 pytest、Ruff、mypy、锁文件和 diff 质量门禁。
- Workflow 权限限制为只读仓库内容，且不读取或配置任何真实模型 Secret。

### 验证

- 检查：本地运行 `scripts/check.sh` 与 `git diff --check`。
- 结果：通过；72 个测试通过，Ruff、格式检查、strict mypy、锁文件与 diff 检查均无问题。
- 检查：确认 `.github/workflows/ci.yml` 已创建。
- 结果：通过；当前本地仓库尚未配置 GitHub remote，故云端 Runner 尚未实际执行。

### 决策变化

- 无；本次落实既有阶段 1 收尾 Pipeline 计划，不改变测试、依赖或 Secret 边界。

### 风险或问题

- GitHub 的实际运行结果必须在创建远端仓库并推送后才能取得；该操作需要单独的用户授权与账户选择。

### 下一步

- 在下一个独立任务中创建或关联 GitHub 远端、推送当前分支并检查首个 CI 运行结果；本次不执行推送。

## 2026-08-07 asAgent 文档收尾工作记录

### 完成

- 以 DEC-027 为准，将 AGENTS、开发概览、架构、路线、桌面/Docker 文档、学习笔记和当前进度摘要中的有效命名统一为 `asAgent` / `asagent`。
- 同步 Python 包/CLI、后端 Sidecar、macOS 应用数据目录与 Docker 镜像标签的示例名称。
- 保留 DEC-023 与带日期工作记录中的 Ragent 表述，确保命名变更的历史可追溯。

### 验证

- 检查：搜索 `AGENTS.md` 与 `docs/` 中的 Ragent 相关命名，并运行 `scripts/check.sh`。
- 结果：通过；当前文档中仅保留历史决策和历史工作记录的 Ragent 表述；72 个测试通过，Ruff、格式检查、strict mypy、锁文件与 diff 检查均无问题。

### 决策变化

- 无；本次落实既有 DEC-027，不新增架构决策。

### 风险或问题

- GitHub Actions 尚未在云端 Runner 执行，需在创建或关联远端并推送后验证。

### 下一步

- 在下一个独立任务中创建或关联 GitHub 远端、推送当前分支并检查首个 CI 运行结果；阶段 2 仍不开始。

## 2026-08-07 GitHub 远端与首次 CI 验证工作记录

### 完成

- 创建私有 GitHub 仓库 `yuting-ai/asAgent`，并将本地 `main` 关联为其 `origin/main`。
- 首次 CI 因 `astral-sh/setup-uv@v8` 不存在而失败；将 Action 固定为受支持的 `v9.0.0` 提交后，提交并推送修复。
- GitHub Actions 的 `Quality gate` 已在 Ubuntu Runner 成功完成。

### 验证

- 检查：GitHub Actions run `ci: use supported setup-uv action #2`。
- 结果：通过；Checkout、Python、uv、锁定依赖安装与 `scripts/check.sh` 全部成功，运行耗时约 16 秒。
- 检查：本地 `git status --short` 与最新提交。
- 结果：通过；工作区 clean，当前 `main` 最新提交为 `340d167 ci: use supported setup-uv action`。

### 决策变化

- 无；本次只验证既有 CI 方案，未改变架构或产品范围。

### 风险或问题

- 无；CI 已在云端独立 Runner 验证。

### 下一步

- 阶段 2 尚未开始；在用户确认后，再领取一个边界清晰的最小任务。

## 2026-08-07 阶段 2 ToolRegistry 工作记录

### 完成

- 新增 `asagent.tools.ToolRegistry`，以内部命名空间化的 `tool_id` 注册和查询既有 `Tool` 实现。
- Registry 拒绝重复 ID，且保留原工具不被静默覆盖；查询未知 ID 会给出明确错误。
- Registry 只维护工具目录，不执行工具，不承担参数校验、权限、批准、超时、审计或模型 Provider 名称映射。

### 验证

- 检查：运行 `uv run pytest tests/unit/test_tool_registry.py` 与完整 `scripts/check.sh`。
- 结果：通过；3 个定向测试覆盖注册/查询、重复 ID 与未知 ID；完整 75 个测试通过，Ruff、格式检查与 strict mypy 无问题。
- 检查：推送 `feat: add tool registry` 后查看 GitHub Actions。
- 结果：通过；远端 Ubuntu Runner 的 Quality gate 成功完成，确认提交的测试与质量门禁在干净环境中可复现。

### 决策变化

- 无；本次落实既有 Tools/Registry 边界，不新增架构决策。

### 风险或问题

- 无；参数校验、权限、批准、超时、审计和执行仍明确留给后续 `ToolExecutor`。

### 下一步

- 在用户确认后，单独实现阶段 2 的最小 ToolExecutor；本次不开始该任务。

## 2026-08-08 阶段 2 ToolExecutor 工作记录

### 完成

- 新增 `asagent.tools.ToolExecutor`，通过 `ToolRegistry` 查找内部 `tool_id` 并异步调用对应 `Tool`。
- Executor 正常返回工具文本结果；未知工具 ID 与工具自身异常保持可观察，不被静默吞没。
- 参数校验、权限、批准、超时、取消、审计与结果截断仍未实现，留给后续独立任务。

### 验证

- 检查：运行 `uv run pytest tests/unit/test_tool_executor.py` 与完整 `scripts/check.sh`。
- 结果：通过；3 个定向测试覆盖委派执行、未知 ID 与工具异常；完整 78 个测试通过，Ruff、格式检查、strict mypy 与锁文件检查无问题。

### 决策变化

- 无；本次落实既有 Executor/Registry 分层，不新增架构决策。

### 风险或问题

- 无；最小 Executor 故意不承担尚未引入的安全横切策略。

### 下一步

- 在用户确认后，单独实现阶段 2 的首个内置工具 `builtin.echo`；本次不开始该任务。

## 2026-08-08 阶段 2 builtin.echo 工作记录

### 完成

- 新增无副作用的 `EchoTool`，内部 ID 为 `builtin.echo`，输入 Schema 声明必填字符串字段 `text`。
- EchoTool 返回带 `Echo: ` 前缀的输入文本，作为后续 Agent Loop 的确定性离线工具。
- 本轮只声明工具 Schema；JSON Schema 参数校验仍留给后续 Executor 扩展。

### 验证

- 检查：运行 `uv run pytest tests/unit/test_echo_tool.py` 与完整 `scripts/check.sh`。
- 结果：通过；2 个定向测试覆盖 Tool Protocol/定义与执行结果；完整 80 个测试通过，Ruff、格式检查、strict mypy 与锁文件检查无问题。
- 检查：推送 `feat: add echo tool` 后查看 GitHub Actions。
- 结果：通过；远端 Ubuntu Runner 的 Quality gate 成功完成，确认本地质量门禁可在干净环境复现。

### 决策变化

- 无；本次落实路线图既有的安全内置工具范围，不新增架构决策。

### 风险或问题

- 无；参数 Schema 目前仅为元数据，尚未参与实际执行前校验。

### 下一步

- 在用户确认后，单独实现阶段 2 的内置工具 `builtin.calculator`；本次不开始该任务。

## 2026-08-08 阶段 2 builtin.calculator 工作记录

### 完成

- 新增 `CalculatorTool`，内部 ID 为 `builtin.calculator`，接受必填字符串 `expression`。
- 使用 `ast.parse(..., mode="eval")` 与节点白名单计算数字、一元正负、括号和 `+`、`-`、`*`、`/`；未使用 `eval()`。
- 函数调用、变量、属性访问、幂运算、整除和取模等语法会明确拒绝。

### 验证

- 检查：运行 `uv run pytest tests/unit/test_calculator_tool.py` 与完整 `scripts/check.sh`。
- 结果：通过；3 个定向测试覆盖 Tool Protocol/定义、运算优先级/括号与 Python 代码拒绝；完整 83 个测试通过，Ruff、格式检查、strict mypy 与锁文件检查无问题。

### 决策变化

- 无；本次落实路线图既有安全内置工具范围，不新增架构决策。

### 风险或问题

- 无；当前算术白名单有意保持较小，复杂运算需单独评估资源限制与错误语义。

### 下一步

- 在用户确认后，单独实现阶段 2 的内置工具 `builtin.current_time`；本次不开始该任务。

## 2026-08-08 单人 Git 工作节奏记录

### 完成

- 确认每个通过本地质量门禁的小任务都创建本地 commit。
- 确认仅在每日收尾、阶段子里程碑、风险改动前或需要 GitHub Actions 验证时 push。
- 确认 GitHub Actions 成功不再单独触发 `progress.md` 更新。

### 验证

- 检查：复核已提交的本地质量门禁与 GitHub Actions 流程。
- 结果：通过；本地 commit 提供小步回退，定期 push 保留远端备份与独立 Runner 验证。

### 决策变化

- 新增 DEC-028：单人开发使用本地 Commit 与定期 Push 节奏。

### 风险或问题

- 本地未 Push 的提交不具备异地备份，必须在约定时机同步到 GitHub。

### 下一步

- 提交本次文档约定后，在下一个独立任务中实现 `builtin.current_time`。

## 2026-08-08 阶段 2 builtin.current_time 工作记录

### 完成

- 新增 `CurrentTimeTool`，内部 ID 为 `builtin.current_time`，不接受参数并返回 UTC ISO 8601 时间字符串。
- 将时间函数注入 Tool；生产默认使用 UTC 当前时间，测试传入固定时间，避免依赖机器时钟。
- 拒绝 naive datetime，确保返回结果始终带时区偏移。

### 验证

- 检查：运行 `uv run pytest tests/unit/test_current_time_tool.py` 与完整 `scripts/check.sh`。
- 结果：通过；3 个定向测试覆盖 Tool Protocol/定义、固定 UTC 时间和 naive 时间拒绝；完整 86 个测试通过，Ruff、格式检查、strict mypy 与锁文件检查无问题。

### 决策变化

- 无；本次落实路线图既有的内置工具范围，不新增架构决策。

### 风险或问题

- 无；时区语义固定为 UTC，后续若需用户时区应由入口或配置层显式提供。

### 下一步

- 在用户确认后，单独设计阶段 2 最小 Agent Loop 的输入、步骤限制与终态；本次不开始该任务。

## 2026-08-08 阶段 2 非流式工具消息契约工作记录

### 完成

- 扩展 Provider-neutral `ModelMessage`：assistant message 可携带 `tool_calls`，TOOL message 必须携带结果文本和配对的 `tool_call_id`。
- OpenAI-compatible Provider 现在可将 assistant tool call 历史及 tool result 映射为合法 Chat Completions 请求。
- 保持流式 tool call 明确未实现；本轮只建立非流式 Agent Loop 所需的回传边界。

### 验证

- 检查：运行模型契约、OpenAI-compatible Provider 定向测试与完整 `scripts/check.sh`。
- 结果：通过；14 个定向测试、完整 88 个测试通过，Ruff、格式检查、strict mypy 与锁文件检查无问题。

### 决策变化

- 无；本次落实既有 tool_use/tool_result 合法配对与 Provider 名称映射边界，不新增架构决策。

### 风险或问题

- 流式工具调用、Run Tool Snapshot 的内部/Provider 名称映射及 Agent Loop 仍未实现。

### 下一步

- 在下一个独立任务中实现带 `max_steps` 的最小非流式 Agent Loop；本次不开始该任务。

## 2026-08-08 阶段 2 Agent Loop 前置条件文档加固

### 完成

- 明确工具往返的两层约束：`ModelMessage` 负责单条消息字段合法性，Agent Loop/Context Builder 负责跨消息的 call/result 配对。
- 将 Agent Loop 的开工门槛写入架构：上下文必须可表达完整工具往返，Provider 必须有离线请求映射测试，Fake Provider 必须可脚本化两次模型响应。
- 调整阶段 2 路线顺序，并新增 DEC-029，禁止在这些前提未满足时先实现 Loop 控制流。

### 验证

- 检查：复核架构、路线图、决策与当前已验证的工具消息契约；运行 `git diff --check`。
- 结果：通过；文档变更无空白错误，不涉及业务代码或远端 CI。

### 决策变化

- 新增 DEC-029：Agent Loop 以完整模型上下文往返为实现前提。

### 风险或问题

- Run Tool Snapshot 的持久化、流式 tool call 和工具安全管线仍未实现；它们不会被最小 Loop 的文档前提掩盖。

### 下一步

- 在用户确认后，先完成内部/Provider 工具名称映射与最小 Run Tool Snapshot，再实现带 `max_steps` 的最小非流式 Agent Loop；本次不开始该任务。

## 2026-08-08 CowAgent 工具循环参考结论

### 完成

- 在用户授权下只读比较 CowAgent 的工具循环、消息配对清理与取消实现，未引入代码、依赖或运行时关系。
- 将可借鉴的 Run 内工具链完整性、失败结果保留、取消安全检查点和基于内部工具身份/参数的重复检测写入架构与路线图。
- 新增 DEC-030；明确不采用 CowAgent 的长期可变会话、静默合成或删除历史、以及超限后的额外总结模型调用。

### 验证

- 检查：复核 CowAgent 参考模块与 asAgent 的 Runtime、Provider-neutral 消息和阶段 2 边界；运行 `git diff --check`。
- 结果：通过；文档变更无空白错误，不涉及业务代码或远端 CI。

### 决策变化

- 新增 DEC-030：Run 内工具链保持完整并设置明确安全检查点。

### 风险或问题

- 当前仅记录规则，尚未实现取消令牌、上下文裁剪、错误结果或重复调用检测。

### 下一步

- 在用户确认后，先完成内部/Provider 工具名称映射与最小 Run Tool Snapshot；本次不开始该任务。

## 2026-08-08 阶段 2 Tool Snapshot 工作记录

### 完成

- 新增 `ToolSnapshot` 与不可变 `ToolBinding`，冻结内部 `tool_id`、Provider 名称和 ToolDefinition，并提供双向查询及 `ModelToolDefinition` 导出。
- 新增 OpenAI-compatible 名称规范化；不兼容字符转换为下划线，超过 64 个字符或名称碰撞会明确拒绝。
- ToolRegistry 新增按注册顺序返回定义的只读快照入口；当前 Snapshot 只在运行时存在，未提前改变 Run 或数据库模型。

### 验证

- 检查：运行 ToolSnapshot/Registry 定向测试、Ruff、strict mypy 与完整 `scripts/check.sh`。
- 结果：通过；7 个定向测试、完整 92 个测试通过，71 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 无；本次落实 DEC-021、DEC-029 与既有阶段 2 Snapshot 边界，不新增架构决策。

### 风险或问题

- Schema Hash 与 Snapshot 的 SQLite 持久化留给阶段 3；其他 Provider 的命名规则在新增对应 Adapter 时单独实现。

### 下一步

- 在用户确认后，实现带 `max_steps` 的最小非流式 Agent Loop；本次不开始该任务。

## 2026-08-09 阶段 2 最小非流式 Agent Loop 工作记录

### 完成

- 新增 `AgentLoop` 与不可变 `AgentLoopResult`；Loop 在内存中协调 ModelProvider、ToolExecutor、Run Tool Snapshot 与标准化消息历史，尚未接入 Repository 或 RunEvent。
- 每次模型响应消耗一个决策步骤，默认 `max_steps=8`；同一响应中的多个工具按顺序执行并将成功、未知工具或执行失败结果作为配对 TOOL message 回填。
- 达到最后一个允许步骤且模型仍请求工具时，Loop 不执行工具并进入 `LIMIT_REACHED`；空文本/无工具、空调用 ID 和重复调用 ID 明确进入 `FAILED`。

### 验证

- 检查：运行 AgentLoop 定向测试、Ruff、strict mypy 与完整 `scripts/check.sh`。
- 结果：通过；6 个定向测试覆盖文本完成、工具往返、步骤上限、未知工具、工具异常和无效上限；完整 98 个测试通过，74 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-031：最小 Agent Loop 以模型决策计数并在上限处停止工具执行。

### 风险或问题

- 取消、模型/工具超时、参数校验、重复调用检测、结果截断、RunEvent 和持久化仍未实现；`LIMIT_REACHED` 的未闭合工具请求不会被继续用于模型调用。

### 下一步

- 在用户确认后，实现基于内部 `tool_id` 与规范化参数的重复工具调用检测；本次不开始该任务。

## 2026-08-09 阶段 2 重复工具调用检测工作记录

### 完成

- AgentLoop 现在按每次 Run 的内部 `tool_id` 与规范化 JSON 参数统计调用次数；不同 Mapping 键顺序的等价参数视为同一组合。
- `max_calls_per_tool_input` 默认 `None`，不阻断可能合法的时间敏感或轮询调用；调用方显式设置正整数时，达到上限后返回配对的 TOOL 错误结果而不执行工具。
- 增加测试：显式上限为 2 时，前两次等价调用正常执行，第三次被阻断；同时验证该上限必须为正数。

### 验证

- 检查：运行 AgentLoop 定向测试、Ruff、strict mypy 与完整 `scripts/check.sh`。
- 结果：通过；7 个定向测试通过，完整本地质量门禁通过。

### 决策变化

- 新增 DEC-032：重复工具调用检测默认关闭并按策略启用。

### 风险或问题

- 当前仅有 Loop 级可选上限；工具级重复策略、参数校验、超时、取消、结果截断、RunEvent 和持久化仍未实现。

### 下一步

- 在用户确认后，实现工具结果截断；本次不开始该任务。

## 2026-08-09 阶段 2 工具结果截断工作记录

### 完成

- AgentLoop 新增 `max_tool_result_chars`，默认将单条模型可见工具结果限制为 4,000 个字符；截断标记计入总上限。
- 截断在工具执行返回后、生成 TOOL message 前发生，仅影响下一次模型请求看到的副本；未提前定义或改变未来原始 ToolCall 审计记录。
- 增加长工具结果测试与截断上限配置校验。

### 验证

- 检查：运行 AgentLoop 定向测试、Ruff、strict mypy 与完整 `scripts/check.sh`。
- 结果：通过；8 个定向测试、完整 100 个测试通过，74 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-033：工具结果截断仅限制模型上下文副本。

### 风险或问题

- 当前使用字符数而非 token 预算；工具超时、取消、参数校验、RunEvent、审计与持久化仍未实现。

### 下一步

- 在用户确认后，实现基础 Run 取消令牌；本次不开始该任务。

## 2026-08-09 阶段 2 基础 Run 取消令牌工作记录

### 完成

- 新增携带 `run_id` 的 `RunCancellationToken`；调用方可显式请求取消，并将 Token 传入 AgentLoop。
- Loop 在模型调用前、模型响应返回后、每个工具执行前和执行返回后检查取消；取消前不发起模型调用。
- 若工具批次中途取消，已完成工具结果保留，尚未执行调用追加配对的取消结果，Loop 返回 `CANCELLED`。

### 验证

- 检查：运行 AgentLoop 定向测试、Ruff、strict mypy 与完整 `scripts/check.sh`。
- 结果：通过；10 个定向测试、完整 102 个测试通过，75 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-034：基础 Run 取消采用协作式 Token 与安全检查点。

### 风险或问题

- Token 不会强制中断已在 await 的 Provider 或 Tool；取消注册表、Run 状态/事件持久化、模型超时和工具超时仍未实现。

### 下一步

- 在用户确认后，实现模型调用超时；本次不开始该任务。

## 2026-08-09 阶段 2 模型调用超时工作记录

### 完成

- `ProviderConfig.timeout_seconds` 的默认值调整为 180 秒；命名 Provider Profile 仍可按模型或服务商覆盖该单次 HTTP 请求的传输超时。
- OpenAI-compatible Provider 将 `httpx.TimeoutException` 转换为明确的 `ProviderTimeoutError`，并沿用不自动重试的安全策略。
- AgentLoop 捕获模型超时后返回 `FAILED`、安全错误文本和原有消息历史；未取得模型响应不会消耗决策步骤。

### 验证

- 检查：运行 Provider 配置、OpenAI-compatible Provider 与 AgentLoop 定向测试，随后运行 Ruff、strict mypy 与完整 `scripts/check.sh`。
- 结果：通过；26 个定向测试、完整 104 个测试通过，75 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-035：模型请求超时由 Provider Profile 管理。

### 风险或问题

- 当前 180 秒只约束单次模型 HTTP 请求，不是整个 Run 的总 deadline；工具执行超时、后台长任务、RunEvent、审计与持久化仍未实现。

### 下一步

- 在用户确认后，实现工具执行超时；本次不开始该任务。

## 2026-08-09 阶段 2 工具执行超时工作记录

### 完成

- `ToolExecutor` 现在以每个 `ToolDefinition.timeout_seconds` 为单次异步执行上限；超时将请求取消工具协程，并以 `ToolTimeoutError` 向上报告。
- AgentLoop 将工具超时转成与原 `tool_call_id` 配对的 TOOL 错误结果，再将该历史交回模型继续决策，而非直接终止 Run。
- 增加测试，验证挂起工具收到取消，以及模型可接收配对超时结果并完成下一轮回答。

### 验证

- 检查：运行 ToolExecutor 与 AgentLoop 定向测试，随后运行 Ruff、strict mypy 与完整 `scripts/check.sh`。
- 结果：通过；16 个定向测试、完整 106 个测试通过，76 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-036：工具超时由工具定义执行，并作为可恢复的 TOOL 结果。

### 风险或问题

- 协程取消不能回滚已经发出的外部副作用；参数校验、权限、批准、审计、Run 总 deadline、后台长任务、RunEvent 与持久化仍未实现。

### 下一步

- 在用户确认后，实现工具参数校验；本次不开始该任务。

## 2026-08-09 阶段 2 工具参数校验工作记录

### 完成

- 新增 `jsonschema` 运行时依赖及 strict mypy 所需的 `types-jsonschema` 开发期存根；Executor 使用 Draft 2020-12 校验每个 `ToolDefinition.input_schema`。
- 参数无效时，Executor 抛出 `ToolArgumentsValidationError` 且不调用 Tool；AgentLoop 将其写为与原 `tool_call_id` 配对的通用错误结果，再让模型继续决策。
- 增加测试，验证无效参数不会执行工具，且模型可收到配对错误并完成后续回答；重复调用检测测试改用 Schema 明确允许的可选参数。

### 验证

- 检查：运行 ToolExecutor 与 AgentLoop 定向测试，随后运行 Ruff、strict mypy 与完整 `scripts/check.sh`。
- 结果：通过；18 个定向测试、完整 108 个测试通过，76 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-037：工具参数在 Executor 以固定 JSON Schema Draft 校验。

### 风险或问题

- Schema 元校验、格式检查、参数归一化、权限、批准、审计、Run 总 deadline、后台长任务、RunEvent 与持久化仍未实现。

### 下一步

- 在用户确认后，实现最小工具权限策略；本次不开始该任务。

## 2026-08-09 阶段 2 最小工具权限策略工作记录

### 完成

- `ToolExecutor` 新增默认为空的 `granted_permissions`；仅当工具的 `required_permissions` 全部已被显式授予时才进入执行。
- 缺少授权时抛出 `ToolPermissionDeniedError`，不调用工具协程；AgentLoop 生成与原 `tool_call_id` 配对的权限拒绝结果，再让模型继续决策。
- 增加测试，验证显式授权允许执行、默认拒绝阻止执行，以及模型能收到并处理配对的权限拒绝结果。

### 验证

- 检查：运行 ToolExecutor 与 AgentLoop 定向测试，随后运行 Ruff、strict mypy 与完整 `scripts/check.sh`。
- 结果：通过；20 个定向测试、完整 110 个测试通过，76 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-038：最小工具权限策略默认拒绝并显式注入授权集合。

### 风险或问题

- 当前权限集合尚未按 `user_id`、Workspace 或 Run 持久化；用户批准、审计、Run 总 deadline、后台长任务、RunEvent 与持久化仍未实现。

### 下一步

- 在用户确认后，实现用户批准机制；本次不开始该任务。

## 2026-08-09 阶段 2 最小用户批准 Gate 工作记录

### 完成

- 新增异步 `ToolApprovalPolicy` Protocol；Executor 仅对 `requires_approval=True` 的工具调用它。
- 没有注入审批 Policy 或 Policy 拒绝时，Executor 默认抛出 `ToolApprovalDeniedError`，不会执行工具协程。
- AgentLoop 将审批拒绝作为与原 `tool_call_id` 配对的 TOOL 错误结果回填，让模型可继续回答或调整方案。
- 增加测试，验证明确批准可以执行、缺少 Policy 默认拒绝，以及模型能接收配对的拒绝结果。

### 验证

- 检查：运行 ToolExecutor 与 AgentLoop 定向测试，随后运行 Ruff、strict mypy 与完整 `scripts/check.sh`。
- 结果：通过；23 个定向测试、完整 113 个测试通过，77 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-041：最小用户批准以异步 Policy Gate 默认拒绝。

### 风险或问题

- 当前没有真实审批窗口、请求 ID、审计、过期时间或等待审批时的取消处理；这些必须结合 DEC-039/DEC-040 在未来独立实现。RunEvent 与持久化仍未实现。

### 下一步

- 在用户确认后，实现最小 RunEvent 记录；本次不开始该任务。

## 2026-08-09 阶段 2 最小 RunEvent 记录工作记录

### 完成

- `AgentLoop` 可选注入 `EventPublisher`；启用时，调用方显式传入 Run/Conversation 身份、事件 ID 工厂和时钟。
- Loop 在 Run 内从 1 单调递增发布启动、模型、工具和四类终态事件；事件仅包含步骤数、工具身份和工具调用 ID，不写入模型文本、工具参数或结果正文。
- 工具成功与失败分别发布 `tool.completed` 和 `tool.failed`，但模型上下文仍保持原有的配对 TOOL 结果语义。
- 已配置 Publisher 的发布失败会停止后续工具与模型调用，并返回 `FAILED`；未配置 Publisher 时保持原有最小 Loop 行为。

### 验证

- 检查：运行 `uv run ruff format src/asagent/agent/loop.py tests/unit/test_agent_loop.py`、`uv run pytest tests/unit/test_agent_loop.py`、`uv run ruff check src/asagent/agent/loop.py tests/unit/test_agent_loop.py`、`uv run mypy`、`scripts/check.sh` 和 `git diff --check`。
- 结果：通过；19 个 AgentLoop 定向测试、完整 117 个测试通过，77 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-043：最小 RunEvent 由 Loop 发布安全元数据，发布失败停止 Run。

### 风险或问题

- 当前事件仍未持久化、查询、回放或通过 SSE 发送；ToolCall 审计与完整运行记录留待后续独立任务。

### 下一步

- 在用户确认后，实现内存态开发 CLI 的 Agent 垂直切片；本次不开始该任务。

## 2026-08-09 阶段 2 开发 CLI Agent 垂直切片工作记录

### 完成

- 默认 `asagent` CLI 现在以确定性的离线 Development Provider 组合 AgentLoop、Echo/Calculator/CurrentTime 工具和终端 EventPublisher；用户可连续输入并观察完整工具回合。
- 新增显式真实路径 `--profile <name> --secret-env <environment-name> --app-home .local-data`；它复用 Profile Loader、EnvironmentSecretProvider、Provider Factory 和已实现 Adapter，不改变测试默认离线的规则。
- 新增被忽略的 `.env.example`，并记录开发时由 `uv run --env-file .env` 在入口前加载调用者选择的环境变量；应用代码不读取 `.env`，正式 Secret Store 仍待后续实现。
- 保留 `run_chat()` 作为阶段 1 ChatService 的测试入口，不将无工具聊天服务与 AgentLoop 生命周期混合。

### 验证

- 检查：运行 CLI 定向测试、Ruff、strict mypy、完整 `scripts/check.sh` 与 `git diff --check`。
- 结果：通过；5 个 CLI 定向测试、完整 119 个测试通过，78 个源码文件 Ruff 与 strict mypy 无问题。
- 检查：运行 `printf 'calculate 2 * (3 + 4)\\nexit\\n' | uv run asagent`。
- 结果：通过；离线 CLI 显示 8 个安全 RunEvent，并返回 `Tool result: 14`。
- 检查：用户使用被忽略的本地 `.env` 和当时的 DeepSeek CLI 映射，分别要求真实模型调用 Calculator 与 Current time 工具。
- 结果：通过；DeepSeek 在两个独立 Run 中均生成一次合法工具调用，Loop 分别执行 `builtin.calculator` 与 `builtin.current_time`，回填配对 TOOL 结果后由第二次模型调用完成回答。每个 Run 都按顺序发布 8 条安全 RunEvent；终端输出未包含 API Key。
- 后续修正：真实 CLI 入口已去除硬编码的 `ASAGENT_DEEPSEEK_API_KEY` 和仅 DeepSeek 限制，改为 `--profile` 与 `--secret-env` 必须成对显式提供；该改动的定向与完整验证结果记录在下一工作项。

### 决策变化

- 新增 DEC-044：开发 CLI 默认离线，真实 DeepSeek 仅由显式 Profile 启用。

### 风险或问题

- 真实 DeepSeek 仍需用户主动设置 Key 并手动运行，会产生费用；当前 CLI 事件和 Conversation/Run 都不持久化。

### 下一步

- 在用户确认后，实现最小 ToolCall 记录；本次不开始该任务。

## 2026-08-09 开发 CLI 通用 Secret 环境映射修正

### 完成

- 真实 Provider CLI 不再硬编码 `deepseek` Profile 或 `ASAGENT_DEEPSEEK_API_KEY`；任意已实现 Adapter 的 Profile 都可通过成对的 `--profile <name>` 与 `--secret-env <environment-name>` 显式启用。
- 入口继续将所选 Profile 的逻辑 `secret_id` 映射到调用者给出的开发期环境变量；Provider、AgentLoop 和 Tool 仍不知道环境变量或 `.env`。
- `.env.example` 改为通用的 `ASAGENT_MODEL_API_KEY` 示例，正式桌面端 Secret Store 仍以 `secret_id` 查询。

### 验证

- 检查：运行 CLI 定向测试、Ruff、strict mypy、完整 `scripts/check.sh` 和 `git diff --check`。
- 结果：通过；5 个 CLI 定向测试、完整 119 个测试通过，78 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 更新 DEC-044 的实现细节：开发期 Secret 映射由显式 `--secret-env` 提供，不猜测 Provider 专属环境变量名。

### 风险或问题

- 本次没有再次发起真实网络请求；现有 DeepSeek 端到端验证仍适用，只需在启动命令中补充 `--secret-env`。

### 下一步

- 在用户确认后，实现最小 ToolCall 记录；本次不开始该任务。

## 2026-08-09 阶段 3 SQLite Schema 与迁移基线工作记录

### 完成

- 引入 SQLAlchemy 2.0 Core、aiosqlite 与 Alembic；初始 Schema 保持在 `storage.sqlite.schema`，不引入 ORM。
- 新增首个 Alembic 迁移，创建 `users`、`conversations`、`messages`、`runs`、`run_events` 与 `tool_calls`；Alembic 版本表显式命名为 `schema_migrations`。
- 固定数据库不变量：Conversation 内 `messages.sequence` 唯一、Run 内 `run_events.sequence` 唯一、外键完整性、正序号、Message 角色范围及 ToolCall 的结果/错误互斥。
- 集成测试仅使用临时 SQLite 文件；本次未创建真实应用数据目录、SQLite Repository、远程 PostgreSQL 或同步功能。

### 验证

- 检查：运行 SQLite Schema 定向迁移集成测试、Ruff、strict mypy、完整 `scripts/check.sh` 和 `git diff --check`。
- 结果：通过；空数据库升级与重复升级、表存在性、外键、顺序唯一性和 ToolCall 约束均通过；完整 122 个测试通过，86 个文件格式正确，82 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-046：以 SQLAlchemy Core Schema 与 Alembic 管理本地 SQLite 迁移，版本表使用 `schema_migrations`。

### 风险或问题

- 当前只有 Schema 和迁移，尚无 SQLite Repository、运行时 PRAGMA、事务服务、重启恢复或事件回放；远程 PostgreSQL 与同步仍不在当前范围。

### 下一步

- 在用户确认后，实现最小 SQLite Conversation Repository；本次不开始该任务。

## 2026-08-09 阶段 3 SQLite Conversation Repository 工作记录

### 完成

- 新增 `storage.sqlite.conversation_repository.SqliteConversationRepository`，作为既有异步 `ConversationRepository` Protocol 的 SQLite 适配器；Repository 接收已迁移数据库路径并提供显式 `aclose()`，不推导或创建个人数据目录。
- Conversation 保存时自动确保所属 User 存在；同一稳定 Conversation ID 可覆盖保存。Message 只可追加到已存在 Conversation，并由单条 SQL 语句分配该 Conversation 内的递增 `sequence`，读取时按该顺序返回。
- SQLAlchemy 使用 `[asyncio]` extra 和 aiosqlite 方言；每个 SQLite 连接开启 foreign keys。SQLite 读写边界将时间统一规范化为 UTC-aware datetime。
- 集成测试覆盖跨 Repository 实例持久化、用户隔离、覆盖保存、Message 顺序、孤儿 Message 拒绝和非 UTC 时间的 UTC 规范化。

### 验证

- 检查：运行 SQLite Conversation Repository 定向集成测试、Ruff、strict mypy、完整 `scripts/check.sh` 和 `git diff --check`。
- 结果：通过；4 个定向集成测试通过，完整 126 个测试通过，88 个文件格式正确，84 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-047：SQLite Conversation Repository 在存储边界规范化 UTC 时间，并显式使用 SQLAlchemy asyncio extra。

### 风险或问题

- 尚未固定 WAL、busy timeout、synchronous、跨进程锁等待和多写者事务策略；Run、RunEvent、ToolCall 的 SQLite Repository、原子创建 Message 与 Run、重启恢复入口和回放查询仍未实现。

### 下一步

- 在用户确认后，先确定 SQLite 运行时连接设置与并发/事务集成测试边界；本次不开始该任务。

## 2026-08-10 阶段 3 SQLite 运行时连接与事务基线工作记录

### 完成

- 新增统一异步 SQLite Engine 工厂；每个连接启用 foreign keys、WAL、5 秒 busy timeout 与 `synchronous = FULL`。
- SQLite Conversation Repository 改为复用该工厂，不再自行注册仅包含外键的连接事件。
- 集成测试固定连接 PRAGMA，并验证事务异常会回滚，以及第二个写者会在短暂 `BEGIN IMMEDIATE` 写锁释放后继续并成功提交。

### 验证

- 检查：运行 SQLite 连接定向集成测试、Ruff 自动整理导入、Ruff 检查、strict mypy 与完整 `scripts/check.sh`。
- 结果：通过；7 个定向集成测试通过，完整质量门禁通过，86 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-048：SQLite 运行时连接使用 WAL、有限锁等待与 FULL 同步。

### 风险或问题

- 当前仍未实现 SQLite Run、RunEvent 与 ToolCall Repository，也未定义“创建用户消息与 Run”的业务级原子事务和锁超时的入口错误映射。

### 下一步

- 在用户确认后，实现最小 SQLite Run Repository；本次不开始该任务。

## 2026-08-10 阶段 3 SQLite Run Repository 工作记录

### 完成

- 新增 `SqliteRunRepository`，完整实现既有异步 `RunRepository` Protocol；Run 可跨 Repository 实例保存、读取、按 Conversation 列举与更新。
- RunEvent 以 JSON 保存安全数据，保持仅追加语义，按 `sequence` 回放并支持 `after_sequence`；写入时拒绝未知 Run 及与 Run 不一致的 Conversation 身份。
- ToolCall 保存完整未截断的参数、结果或错误，并在没有业务序号的当前 Schema 中按创建时间与稳定 ID 返回。
- 修复不可变 `mappingproxy` 不能被标准 JSON 编码器直接序列化的问题：仅在 Storage 边界复制为普通字典，领域对象保持不可变。

### 验证

- 检查：运行 SQLite RunRepository 定向集成测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；3 个定向集成测试通过，完整质量门禁通过。

### 决策变化

- 新增 DEC-049：SQLite Run Repository 以 Run 关联回放事件并保存原始 ToolCall。

### 风险或问题

- 尚未实现将 `EventPublisher` 与 `ToolCallRecorder` 接到该 Repository，也未定义“创建用户消息与 Run”的业务级原子事务、幂等键及锁超时的入口错误映射。

### 下一步

- 在用户确认后，先定义并实现创建用户消息与 Run 的最小原子事务服务；本次不开始该任务。

## 2026-08-10 阶段 3 SQLite Run 启动原子事务工作记录

### 完成

- 新增 `SqliteRunStarter`，在同一 SQLite 事务内创建用户 Message 与初始 Run；它只接收调用方已构造的领域对象，不生成 ID、时间或事件。
- 写入前拒绝 Message/Run Conversation 不一致和未知 Conversation；Run 插入失败会回滚已经尝试插入的 Message，不留下孤儿用户消息。
- 集成测试覆盖成功写入、不一致/未知 Conversation 的无副作用拒绝，以及重复 Run ID 触发的跨表回滚。

### 验证

- 检查：运行 SQLite RunStarter 定向集成测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整质量门禁通过，136 个测试通过，94 个文件格式正确，90 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-050：用户消息与初始 Run 由 SQLite 单一事务创建。

### 风险或问题

- 当前没有 API 幂等键、每 Conversation 的异步锁、RunEvent Publisher 持久化适配、ToolCall Recorder 持久化适配或锁超时的用户可见错误映射。

### 下一步

- 在用户确认后，实现持久化 RunEvent 的最小 EventPublisher 适配；本次不开始该任务。

## 2026-08-10 阶段 3 RunEvent 持久化 EventPublisher 工作记录

### 完成

- 新增 `storage.event_publisher.RepositoryEventPublisher`，实现 Core `EventPublisher` Protocol，并将安全 RunEvent 原样委托给注入的 `RunRepository.append_event()`。
- 使用 `SqliteRunRepository` 注入时，事件可在关闭并重新创建 Repository 后按 Run 内 `sequence` 回放，并继续支持 `after_sequence` 续传。
- 单元测试固定 Repository 写入异常会原样传播；集成测试验证跨实例持久化与乱序写入后的 sequence 回放。集成测试文件命名为 `test_repository_event_publisher.py`，避免与 unit 测试形成 Python 顶层模块同名冲突。

### 验证

- 检查：运行 EventPublisher unit/integration 定向测试、Ruff 格式化与检查、strict mypy、完整 `scripts/check.sh` 和 `git diff --check`。
- 结果：通过；2 个定向测试通过，完整 138 个测试通过，97 个文件格式正确，93 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-051：RunEvent 通过注入的 Repository 持久化。

### 风险或问题

- 适配器目前不创建 Engine、不重试或吞掉写入异常；Agent Loop 的既有失败路径负责处理传播的异常。SSE、Run 状态更新和 ToolCall 持久化仍未接入。

### 下一步

- 在用户确认后，实现同样注入 `RunRepository` 的最小 ToolCallRecorder 持久化适配；本次不开始该任务。

## 2026-08-10 阶段 3 ToolCall 持久化 Recorder 工作记录

### 完成

- 新增 `storage.tool_call_recorder.RepositoryToolCallRecorder`，实现 Core `ToolCallRecorder` Protocol，并将完整 ToolCall 原样委托给注入的 `RunRepository.save_tool_call()`。
- 使用 `SqliteRunRepository` 注入时，成功与失败工具调用的模型调用 ID、内部工具 ID、参数、结果或错误可跨 Repository 实例持久化并按既有稳定顺序读取。
- 单元测试固定 Repository 写入异常会原样传播；集成测试验证跨实例持久化，以及 Recorder 不改变成功或失败 ToolCall 的审计内容。

### 验证

- 检查：运行 ToolCallRecorder unit/integration 定向测试、Ruff 格式化与检查、strict mypy、完整 `scripts/check.sh` 和 `git diff --check`。
- 结果：通过；完整质量门禁通过，100 个文件格式正确，96 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-052：ToolCall 通过注入的 Repository 持久化。

### 风险或问题

- 当前两个持久化适配器仍未在正式 Runtime/API 组合根中共同注入；Run 状态更新、SSE、请求幂等、Conversation 锁与重启恢复入口仍待后续独立任务。

### 下一步

- 在用户确认后，设计并实现最小持久化 Runtime 组合或 API 入口；本次不开始该任务。

## 2026-08-10 阶段 3 SQLite Run 结束原子事务工作记录

### 完成

- 新增 `SqliteRunFinisher`，要求输入为终态 Run，并在单一 SQLite 事务中更新 Run 状态与时间，以及可选地追加同一 Conversation 的 AssistantMessage。
- 拒绝非终态 Run、未知或身份不匹配的 Run/Message；AssistantMessage 插入失败时 Run 更新一并回滚，不产生“完成状态与可见回答脱节”的记录。
- 集成测试覆盖成功完成、失败 Run 无可见消息、身份不匹配的无副作用拒绝和消息主键冲突导致的跨表回滚。

### 验证

- 检查：运行 RunFinisher 定向集成测试、Ruff 格式化与检查、strict mypy、完整 `scripts/check.sh` 和 `git diff --check`。
- 结果：通过；102 个文件格式正确，98 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-053：终态 Run 与可见 AssistantMessage 由 SQLite 单一事务完成。

### 风险或问题

- 仍未将 Starter、Loop、Finisher 与两个持久化适配器组合成正式 Runtime；没有请求幂等、Conversation 锁、SSE 或 API 入口。

### 下一步

- 在用户确认后，实现最小持久化 Agent Runtime 服务，组合已有生命周期协调器和持久化适配器；本次不开始该任务。

## 2026-08-10 阶段 3 最小持久化 Agent Runtime 工作记录

### 完成

- 新增 Core `RunStarter` 与 `RunFinisher` Protocol，使 Agent 应用层可使用既有 SQLite 生命周期协调器而不导入 SQLite。
- 新增 `PersistentAgentRuntime`：验证 Conversation 后原子创建用户消息与 CREATED Run，读取可见历史执行已配置 Loop，再原子保存终态 Run 和可选最终 AssistantMessage。
- 真实 SQLite 集成测试覆盖普通完成与 RunEvent 回放、工具回合的 ToolCall 审计、失败 Run 无 AssistantMessage，以及未知 Conversation 在模型调用前拒绝。
- `LIMIT_REACHED` 的可能文本不会写入 Conversation，因为它可能仍关联未完成 ToolCall；只有 COMPLETED 的最终文本成为用户可见消息。

### 验证

- 检查：运行持久化 Runtime 定向集成测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；105 个文件格式正确，101 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-054：持久化 Agent Runtime 依赖生命周期 Protocol 与预配置 Loop。

### 风险或问题

- Runtime 尚未成为 CLI/API 的实际入口；没有请求幂等、每 Conversation 锁、取消 Token 注册、SSE、流式输出或重启后未完成 Run 的恢复策略。

### 下一步

- 在用户确认后，为持久化 Runtime 设计最小的运行时组合根与可手动体验的 SQLite 开发入口；本次不开始该任务。

## 2026-08-10 阶段 3 SQLite 应用数据库启动器工作记录

### 完成

- 新增 `upgrade_sqlite_database()`：调用方显式提供数据库与 Alembic 配置路径；函数确保父目录存在并将 Schema 升级至 head。
- 集成测试验证由 `AppPaths.data_dir` 计算的数据库路径可首次初始化、重复升级保持单一迁移版本，以及底层迁移错误不会被吞掉。

### 验证

- 检查：运行 SQLite 数据库启动器定向集成测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整 150 个测试通过，107 个文件格式正确，103 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-055：SQLite 启动迁移由显式数据库初始化函数执行。

### 风险或问题

- 该函数目前服务源码开发环境；正式打包时 Alembic 配置与迁移脚本的资源携带方式仍待 Electron/PyInstaller 阶段确认。它尚未接入 CLI。

### 下一步

- 在用户确认后，实现最小持久化开发 CLI 组合根，以同一 Conversation 跨进程使用 SQLite Runtime；本次不开始该任务。

## 2026-08-10 阶段 3 持久化开发 CLI 工作记录

### 完成

- 新增显式 `--persistent` 与 `--conversation-id` CLI 参数；默认内存态开发 CLI 与真实 Profile 入口的既有行为保持不变。
- 持久化模式从 `AppPaths.data_dir` 推导 `asagent.sqlite3` 并升级 Schema，组合 SQLite Repository、Starter、Finisher、RunEvent/ToolCall 持久化适配器与 PersistentAgentRuntime。
- 未指定 Conversation 时创建本地用户 Conversation 并显示其 ID；指定 ID 时复用既有 Conversation，不存在则在模型调用前明确拒绝。
- 集成测试验证同一 Conversation 跨两次独立 SQLite 组件组合保留完整用户/助手消息与两个完成 Run；持久化模式使用离线 DevelopmentToolModelProvider，不产生真实模型费用。

### 验证

- 检查：运行 CLI unit/integration 定向测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整 152 个测试通过，108 个文件格式正确，104 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-056：持久化开发 CLI 以显式模式组合 SQLite Runtime。

### 风险或问题

- 此入口仍是开发工具，不是正式 API 或桌面界面；没有事件终端多播/SSE、真实 Provider 持久化组合、请求幂等、Conversation 锁、取消注册或未完成 Run 恢复。

### 下一步

- 在用户确认后，手动运行持久化离线 CLI，验证跨进程 Conversation 续接与 SQLite RunEvent/ToolCall 审计；本次不开始该任务。

## 2026-08-10 阶段 3 持久化开发 CLI 手动验收记录

### 完成

- 用户以 `uv run asagent --persistent --app-home .local-data` 创建 Conversation，并完成 Calculator 与 Echo 两个离线工具 Run；随后在新进程中使用同一 `--conversation-id` 完成 CurrentTime Run。
- SQLite 查询确认同一 Conversation 产生的三个 Run 均为 `completed`；抽样 Calculator Run 的 RunEvent 严格按 sequence 记录 `run.started`、模型请求/完成、工具请求/完成及 `run.completed` 共八条事件。
- ToolCall 审计查询确认 Calculator 调用保存内部 `tool_id = builtin.calculator`、原始结果 `56088` 且无错误。

### 验证

- 检查：两次独立持久化 CLI 进程、SQLite `runs`、`run_events` 和 `tool_calls` 查询。
- 结果：通过；Conversation 身份可跨进程续接，事件顺序和工具审计与持久化 Runtime 契约一致。

### 风险或问题

- 仍没有事件终端多播/SSE、真实 Provider 持久化模式、请求幂等、Conversation 锁、取消注册或未完成 Run 恢复。

### 下一步

- 在用户确认后，设计真实 Provider 与持久化 Runtime 的显式开发组合，或开始阶段 4 的上下文预算与摘要基础；本次不开始该任务。

## 2026-08-10 阶段 3 真实 Provider 持久化开发组合工作记录

### 完成

- `--persistent` 现可与成对的 `--profile`、`--secret-env` 显式组合；真实模型的 Conversation、Run、RunEvent 和 ToolCall 与离线持久化模式走同一 SQLite Runtime 生命周期。
- 新增通用 `build_persistent_agent_runtime(model=...)` 组合函数；它只依赖 `ModelProvider` Protocol，负责为任意模型注入既有 SQLite EventPublisher 与 ToolCallRecorder。离线开发模式继续使用其专用确定性 Provider，默认非持久化 CLI 行为不变。
- CLI 在真实持久化会话期间拥有 `httpx.AsyncClient`，退出时关闭；Profile 与 secret-env 仍必须成对提供，错误不会降级为离线模型。
- 集成测试以 FakeModelProvider 覆盖通用 Provider 组合路径，确认最终回答和 completed Run 被持久化；自动化测试不读取真实 Secret 或发起网络请求。

### 验证

- 检查：运行真实 Provider 持久化 CLI 的 unit/integration 定向测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整 153 个测试通过，108 个文件格式正确，104 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 新增 DEC-057：真实 Provider 可显式组合到持久化开发 Runtime。

### 风险或问题

- 真实 Provider 持久化入口尚未进行人工网络验收，调用会产生模型费用；它仍没有请求幂等、每 Conversation 锁、取消注册、SSE/流式输出或未完成 Run 恢复。

### 下一步

- 在用户确认后，先手动验收一次真实 Provider 的持久化 Conversation 与 SQLite 审计，或开始阶段 4 的上下文预算与摘要基础；本次不开始该任务。

## 2026-08-10 阶段 3 真实 Provider 持久化 CLI 手动验收记录

### 完成

- 用户以真实 DeepSeek Profile 创建持久化 Conversation `conv_47e42c802be848e1a17d9b31cc6330c1`，要求调用 Calculator 计算 `123 * 456`。
- 该 Conversation 的 Run `run_f8bada09b9b54e969bd0347dda3bf14e` 为 `completed`；RunEvent 严格按 sequence 保存启动、两次模型请求/完成、工具请求/完成及完成事件，共八条。
- ToolCall 审计保存 `builtin.calculator`、Provider `model_call_id` 与原始结果 `56088`，错误字段为空，证明真实 Provider 使用的持久化组合与离线模式走同一审计路径。

### 验证

- 检查：真实 `--persistent --profile deepseek --secret-env ASAGENT_MODEL_API_KEY` CLI 会话，以及 SQLite 对 runs、run_events 与 tool_calls 的查询。
- 结果：通过；真实模型完成工具回合并写入 SQLite，状态、事件顺序和工具审计均符合 Runtime 契约。

### 风险或问题

- SQLite 的 datetime 回读为 UTC 时间；`sqlite3` 默认以未附时区的值显示，因此与本机时区存在显示偏移，但领域与 Storage 边界均按 UTC 解释，符合 DEC-047。

### 下一步

- 在用户确认后，开始阶段 4 的上下文预算与摘要基础；本次不开始该任务。
