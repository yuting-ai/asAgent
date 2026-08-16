# asAgent 当前进度

## 1. 当前状态

- 项目阶段：阶段 7 进行中；阶段 0–6 的 Core、Agent Loop、SQLite 持久化、Context Builder 基础、受控 Workspace Tool 边界与 Local API/SSE 已完成，当前继续 Electron 最小集成。
- 代码状态：已具备 Provider-neutral Core、内存/SQLite Repository、最小 Chat 与持久化 Agent Runtime、OpenAI-compatible Provider、工具与安全执行管线、Context Builder 基础、受控文件工具，以及仅监听回环地址并使用一次性 Bearer Token 的 FastAPI Local API。当前 API 已提供 Health、Conversation 列表/创建（响应含可空 title，创建请求仍禁止 title）、可见 Message 查询/提交、按 Run ID 查询状态、协作取消，以及基于持久化 RunEvent 的认证 SSE 回放/实时观察。首条消息提交会在 RunStarter 同事务中生成会话标题。
- 项目路径：`/Users/yuting/Desktop/BityDev/asAgent`
- 当前日期：2026-08-11
- 当前目标：桌面 Chat 已能显示并按最近活跃排序的会话；下一项在用户确认后继续阶段 7 体验回顾与下一真实用户价值路径。

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

## 2026-08-10 阶段 4 Context 与 Memory 边界设计记录

### 完成

- 确认模型 context window 硬上限与用户可配置输入预算、输出预留和轮次保护分开建模；未来设置窗口只能在模型能力范围内调整。
- 确认每次模型调用使用不可变 ContextSnapshot，记录实际可见组成、来源、预算与裁剪原因，后台摘要不得修改已经开始的请求。
- 明确原始 Conversation、Conversation Summary、User Memory、Skill 与跨 Conversation 历史检索的职责和数据边界；User Memory 默认以候选加用户确认方式写入。
- 确认跨 Conversation 检索是阶段 10 的可选历史参考能力，先采用 SQLite 关键词/文本检索，默认不无范围扫描全部 Conversation，也不索引内部运行材料。

### 验证

- 检查：对照阶段 4/10 路线、现有 SQLite 主数据边界、完整工具链约束和经用户授权读取的 CowAgent 上下文/记忆模块；运行 `git diff --check`。
- 结果：通过；设计不改变当前代码或持久化 Schema，且与 DEC-016、DEC-020、DEC-030 和阶段 4/10 的职责边界一致。

### 决策变化

- 新增 DEC-058：上下文压缩、长期记忆与历史检索分层并以快照确定模型可见内容。

### 风险或问题

- ContextBudget、TokenEstimator、ContextSnapshot、完整工具链分组和摘要接口均尚未实现；当前 CLI 仍把完整可见历史直接交给 Runtime。

### 下一步

- 在用户确认后，实现阶段 4 的第一个最小任务：Context Budget、分项 Token 估算和不可变使用量快照；本次不开始该任务。

## 2026-08-10 阶段 4 Context Budget 与使用量快照工作记录

### 完成

- 新增 `ModelContextCapabilities`、`ContextBudget` 与 `ResolvedContextBudget`，将模型 context window 硬上限和用户输入/输出策略分开，并以两者较小的可用输入空间作为有效预算。
- 新增运行时可替换的 `TokenEstimator` Protocol；当前 `ConservativeUtf8TokenEstimator` 确定性计算 UTF-8 文本字节数和消息、tool call、工具 Schema 的结构开销，不冒充任何 Provider 的精确 tokenizer。
- 新增不可变 `ContextUsage`，可从一次 `ModelRequest` 分别统计 system prompt、工具 Schema 和消息 Token 估算，公开总输入、剩余输入预算与是否超限。
- 本任务不接入 AgentLoop，因此当前 CLI/真实 Provider 的请求内容与输出行为不变；后续 Context Builder 将消费这些预算和使用量数据决定裁剪或摘要。

### 验证

- 检查：运行 Context Budget 定向单元测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整 159 个测试通过，110 个文件格式正确，106 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 无；本次落实 DEC-058 的预算与可观察性基础，未改变既有数据或压缩策略决策。

### 风险或问题

- 当前估算器为保守近似，可能早于 Provider 精确 tokenizer 触发未来裁剪；Model Profile 能力配置、完整 ContextSnapshot、工具链分组、裁剪与摘要接口仍未实现。

### 下一步

- 在用户确认后，实现阶段 4 的下一最小任务：ModelMessage 历史的合法性检查与完整工具调用链分组；本次不开始该任务。

## 2026-08-10 阶段 4 模型历史合法性与工具链分组工作记录

### 完成

- 新增 `agent.context_history`：在 Context Builder 之前验证 `ModelMessage` 历史，并将其划分为不可变的 `ContextHistoryUnit`。
- 明确模型历史必须从 USER message 开始；SYSTEM prompt 不允许混入历史，继续由 `ModelRequest.system_prompt` 单独承载。
- 带 tool calls 的 ASSISTANT message 现在必须紧跟声明顺序对应的 TOOL results；缺少、错配、孤立或重复的 call ID 会以 `ContextHistoryValidationError` 明确拒绝。
- 分组以新的 USER message 作为边界，完整的 assistant tool calls 与全部 TOOL results 因此始终属于同一可整体保留或裁掉的历史单元。
- 本任务不改 AgentLoop、SQLite 主数据或模型请求内容，尚未实际执行裁剪。

### 验证

- 检查：运行 Context History 定向单元测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整 168 个测试通过，112 个文件格式正确，108 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 无；本次落实 DEC-058 已确认的完整工具链裁剪约束，未改变 ContextSnapshot 或摘要策略。

### 风险或问题

- 目前只产生安全的历史单元；Context Builder 尚未按预算选择单元，也没有生成 ContextSnapshot、持久化 Summary 或接入 Loop。

### 下一步

- 在用户确认后，实现阶段 4 的下一最小任务：基于 Context Budget 与完整历史单元的确定性最近历史选择；本次不开始该任务。

## 2026-08-10 阶段 4 最近完整历史选择工作记录

### 完成

- 在 `agent.context_history` 新增不可变 `ContextHistorySelection` 与 `select_recent_context_history()`。
- 选择器使用现有可替换 `TokenEstimator`，由调用方提供扣除固定成本后的消息预算；它从最新完整单元向前累加，并保持最终消息的原时间顺序。
- 若加入一个更旧单元会超限，选择立即停止；若最新单元自身超限，返回空选择并省略全部历史，而不是截断该单元或跳过最新单元选择更旧内容。
- 选择结果公开已选单元、扁平化消息、消息 Token 估算和省略单元数量，方便下一任务构造可解释的 ContextSnapshot。
- 本任务仍未接入 AgentLoop、Provider、SQLite 或摘要；当前 CLI 请求内容不变。

### 验证

- 检查：运行 Context History 定向单元测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整 173 个测试通过，112 个文件格式正确，108 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 无；本次按 DEC-058 实现确定性降级的最小选择规则，未改变摘要、记忆或 Snapshot 决策。

### 风险或问题

- 当前 API 接收的只是历史消息预算；尚未由 Context Builder 统一扣除 system prompt、工具 Schema 或未来摘要成本，也未生成模型请求快照。

### 下一步

- 在用户确认后，实现阶段 4 的下一最小任务：最小不可变 `ContextSnapshot` 与 Context Builder，组合固定成本、完整历史选择和 `ModelRequest`；本次不开始该任务。

## 2026-08-10 阶段 4 最小 ContextSnapshot 与 Context Builder 工作记录

### 完成

- 新增不可变 `ContextSnapshot`，以单一 `ModelRequest` 保存本次实际可见的 model、system prompt、完整历史消息和工具定义，并关联有效预算、分项使用量与历史选择结果。
- 新增 `ContextBuilder`：先计算 system prompt 与工具 Schema 的固定成本，再把剩余消息预算交给完整历史选择器，最后生成与 `ContextUsage` 一致的请求快照。
- 固定成本超出输入预算、或最新完整历史单元无法装入预算时，明确抛出 `ContextBudgetExceededError`；不构造遗漏当前用户问题的空请求。
- 单元测试覆盖固定成本扣除、完整工具链保留、两种超限路径、空历史快照和不可变性。
- 本任务不接入 AgentLoop、Provider、SQLite 或摘要；现有 CLI 的实际模型请求仍不变。

### 验证

- 检查：运行 Context Builder 定向单元测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整 179 个测试通过，114 个文件格式正确，110 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 无；本次落实 DEC-058 的不可变快照与确定性降级边界，未改变摘要、记忆或运行时组合策略。

### 风险或问题

- Snapshot 尚未包含摘要、用户记忆、来源 sequence、裁剪原因枚举或默认脱敏调试导出；当前 Loop 仍直接自行构造 `ModelRequest`。

### 下一步

- 在用户确认后，实现阶段 4 的下一最小任务：让 AgentLoop 通过 Context Builder 在每次模型调用前创建并消费 ContextSnapshot；本次不开始该任务。

## 2026-08-10 阶段 4 AgentLoop ContextSnapshot 接入工作记录

### 完成

- `AgentLoop` 现可选注入 `ContextBuilder`；注入后，每一个模型决策步骤都先构建新的不可变 `ContextSnapshot`，并且 `ModelProvider.complete()` 只接收其中的 `request`。
- Context Builder 以当前完整内存历史重建快照，因此工具回合后的下一次模型调用也重新应用预算与完整工具链选择；Loop 自己继续保留完整运行历史用于执行结果和审计。
- `ContextBudgetExceededError` 在模型调用前收敛为 `FAILED`、安全错误文本 `context budget exceeded`，不发布 `model.requested`，也不触发 Provider 网络调用。
- 未注入 Builder 时保留既有请求构造路径。当前尚无 Provider Profile 的 context window 配置，故不硬编码默认窗口；后续组合根会显式注入 Builder 后再让实际路径默认启用。

### 验证

- 检查：运行 AgentLoop 定向单元测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整 181 个测试通过，114 个文件格式正确，110 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 无；本次落实 DEC-058 的“快照确定模型可见内容”，未硬编码模型窗口，也未改变 Summary/Memory 边界。

### 风险或问题

- CLI 与持久化 Runtime 尚未从 Profile/用户设置解析 context window 和预算，因此当前真实运行仍沿用未注入 Builder 的兼容路径；Snapshot 也尚未持久化或作为调试信息导出。

### 下一步

- 已调整后续顺序：不要求普通用户在 Provider Profile 填写窗口。先进行真实 Provider 的多轮人工体验；模型能力目录、用户设置和自定义模型高级配置在具备相应 UI/配置体验后再作为独立任务设计，见 DEC-059。

## 2026-08-10 阶段 4 Context 能力配置体验边界调整记录

### 完成

- 确认现有 `context_budget`、`context_history`、`context_builder` 与 AgentLoop 接入已达到当前合适的基础模块粒度，不继续预建裁剪原因、摘要或记忆等横向抽象。
- 取消“要求每个 Provider Profile 必填 `context_window_tokens` 并立刻默认注入 Builder”的后续计划。
- 确认模型窗口是内部硬能力：已知模型由未来模型能力目录自动解析；仅未知/自定义模型在设置中的高级路径配置窗口。用户输入/输出预算始终是独立策略。
- 阶段 4 下一步优先进行真实 Provider 多轮人工体验，依据实际问题决定是否需要开发期显式预算开关或后续能力目录。

### 验证

- 检查：复核现有 Context Builder、AgentLoop 可选注入、阶段 4 路线和用户体验边界。
- 结果：通过；调整不改代码、不改变已验证运行行为，并与 DEC-058 的能力/策略分离一致。

### 决策变化

- 新增 DEC-059：模型窗口能力面向用户自动解析，自定义模型才高级配置。

### 风险或问题

- 当前真实 CLI 仍未使用 ContextBuilder，故无法在人工体验中触发实际裁剪；这是有意避免未经验证的模型能力猜测，后续以显式开发配置或正式能力目录解决。

### 下一步

- 在用户确认后，执行真实 Provider 多轮人工验收，观察工具调用、上下文连续性、长输出与持久化 Run 审计；本次不开始该任务。

## 2026-08-10 阶段 4 真实 Provider 多轮人工验收记录

### 完成

- 用户以真实 DeepSeek Profile 在持久化 Conversation `conv_3a3ad645dc6040798920d6c9ee019e3d` 完成四轮对话。
- 模型在后续回合正确保持临时代号“蓝鲸-42”，并在明确要求时调用 Calculator 得到 `123 × 456 = 56088`；之后完成十条安全设计清单与最终回顾，未在要求禁止时调用工具。
- SQLite 查询确认四个 Run 均为 `completed`。Calculator Run `run_018f32d1e0054c89a0c5bc371b55031e` 保存 `builtin.calculator`、原始结果 `56088` 且无错误。
- 该工具 Run 的 RunEvent 严格按 sequence 保存启动、两次模型请求/完成、工具请求/完成及完成事件，共八条，与既有持久化工具回合契约一致。

### 验证

- 检查：真实 `--persistent --profile deepseek --secret-env ASAGENT_MODEL_API_KEY` 多轮 CLI 会话，以及 SQLite 的 `runs`、`tool_calls` 与 `run_events` 查询。
- 结果：通过；真实模型的上下文连续性、工具选择、长输出与持久化审计均符合当前 Runtime 行为。

### 决策变化

- 无；本次是人工体验验收，不改变 DEC-058/DEC-059 的 Context Builder 与模型能力配置边界。

### 风险或问题

- 当前真实 CLI 仍未自动注入 ContextBuilder，因此该验收不覆盖实际 token 裁剪、超预算失败或 ContextSnapshot 调试输出；长 Conversation 在现阶段仍会完整送入模型。

### 下一步

- 在用户确认后，评估本次体验是否暴露新的 Context 问题；若无阻塞问题，阶段 4 的基础建设到此收束，后续 Context 功能只在实际需要时以单独任务推进，不提前实现摘要或记忆。

## 2026-08-10 阶段 5 WorkspaceResolver 路径边界工作记录

### 完成

- 新增 `workspace.resolver.WorkspaceResolver`，以规范化的 Workspace 根和可选额外根处理未来文件工具的目标路径。
- 相对路径固定以 Workspace 为基准；绝对路径仅在明确允许根内通过。不存在但仍位于允许根内的目标可返回，为后续受控创建文件预留。
- 路径穿越、Workspace 外绝对路径，以及经符号链接逃逸到允许根外的目标均以明确错误拒绝。
- Resolver 不扫描、读取、创建、修改或删除文件；它只是后续自动化文件能力的安全前置检查。

### 验证

- 检查：运行 WorkspaceResolver 定向单元测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整 189 个测试通过，117 个文件格式正确，113 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 无；本次落实 DEC-039 的路径规范化与允许根边界，未改变权限、审批或自动化范围。

### 风险或问题

- 当前没有 File Tool、用户可配置根、批准 UI、文件变更审计或 Scheduler；Resolver 的额外根只是未来 Policy/设置层的注入边界。

### 下一步

- 在用户确认后，实现最小只读 `filesystem.list` 工具，并在执行前使用 WorkspaceResolver；本次不开始该任务。

## 2026-08-10 阶段 5 分页目录列出工具工作记录

### 完成

- 新增只读 `filesystem.list` Tool，要求 `filesystem.read`，并在列出目录前通过 `WorkspaceResolver` 验证路径。
- 工具只非递归列出一层文件、目录和符号链接的名称/类型，不读取正文、不跟随链接、不输出绝对路径，也不注册到当前 CLI。
- 目录项按名称稳定排序；默认每页 50、单页最多 100，支持 `offset`。结果明确包含总条目数、当前显示区间和可继续调用的下一页 offset。
- 空目录、空页、Workspace 越界、文件目标和无效直接参数均有明确测试行为。

### 验证

- 检查：运行 FilesystemListTool 定向单元测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整 201 个测试通过，119 个文件格式正确，115 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 无；本次落实 DEC-039 的低风险只读能力与范围检查，未改变权限范围、审批或自动化策略。

### 风险或问题

- `filesystem.read` 尚未由实际 CLI/Runtime 授予，工具尚未接入 Registry；用户授权根、读取文件正文、写入、审计、审批与 Scheduler 仍是独立后续任务。

### 下一步

- 在用户确认后，实现最小只读 `filesystem.read_file` 工具，并复用 WorkspaceResolver、明确文件大小/文本编码限制；本次不开始该任务。

## 2026-08-10 阶段 5 最小文本文件读取工具工作记录

### 完成

- 新增只读 `filesystem.read_file` Tool，要求 `filesystem.read`，并在读取前通过 `WorkspaceResolver` 验证目标。
- 工具只读取单个存在的 UTF-8 文本文件；目录、缺失文件、Workspace 越界、非 UTF-8 内容和超过 64 KiB 的文件均以明确错误拒绝。
- 读取以固定字节上限完成，避免将大文件完整载入内存或交给模型；空文本文件保留为空字符串这一真实内容。
- 工具尚未注册到 CLI 或真实 Provider 路径，未新增文件写入、文档解析、OCR、审批或审计行为。

### 验证

- 检查：运行 FilesystemReadFileTool 定向单元测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整 209 个测试通过，121 个文件格式正确，117 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 无；本次继续落实 DEC-039 的低风险只读能力与范围检查。DOCX/PDF 文本提取和 OCR 的分层计划已写入阶段 5 路线图，尚未开始实现。

### 风险或问题

- 当前只支持 UTF-8 纯文本（例如 Markdown、TXT、代码与常见文本配置）；DOCX、带文本层 PDF、扫描 PDF、图片、表格和其他二进制格式都不应交给本工具。
- `filesystem.read` 尚未由实际 CLI/Runtime 授予，工具尚未接入 Registry；用户授权根、写入、文档提取、OCR、审计、审批与 Scheduler 仍是独立后续任务。

### 下一步

- 在用户确认后，选择阶段 5 的下一项受控文件能力；DOCX/PDF 正文提取与 OCR 只在基础文件边界、依赖和产品体验准备好后，以独立任务推进。

## 2026-08-10 阶段 5 Create-only 文件写入工具工作记录

### 完成

- 新增高风险 `filesystem.write_file` Tool，要求 `filesystem.write` 且 `requires_approval=True`；未授予权限或没有明确批准时，Executor 不会进入写入协程。
- 工具只创建允许 Workspace 根内尚不存在的 UTF-8 文本文件，使用独占创建避免覆盖竞争；它不创建父目录，也不会覆盖、追加或删除已有文件。
- 单次内容按 UTF-8 编码限制为 64 KiB；路径越界、目录目标、缺失/非目录父路径、已有目标、超限内容和无效参数均有明确拒绝行为。
- 未注册到 CLI 或真实 Provider 路径；本次未实现真实审批 UI、写入审计、覆盖、删除、备份或撤回。

### 验证

- 检查：运行 FilesystemWriteFileTool 定向单元测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整 218 个测试通过，123 个文件格式正确，119 个源码文件 Ruff 与 strict mypy 无问题。

### 决策变化

- 无；本次按 DEC-009、DEC-038 和 DEC-039 落实副作用工具的参数、权限、审批与允许根边界。后续可撤回文件变更已写入路线图，尚未改变持久化模型或执行行为。

### 风险或问题

- 当前 Approval Protocol 尚不能展示规范化路径、变更摘要或有效期限；因此该 Tool 仅作为未注册的安全基础，不能视为完整的用户可交互写入流程。
- 当前不支持覆盖、追加、删除或撤回。`filesystem.write` 是写类操作的能力门槛，不会扩大这个 create-only Tool 的实际能力；在引入覆盖、追加或删除前必须先完成 FileChange/撤回机制。该机制就绪后也可记录 create-only 操作，以安全删除仍未被后续修改的 Agent 新建文件。

### 下一步

- 在用户确认后，选择阶段 5 的下一项受控文件能力；覆盖、追加或删除必须以前置的持久化且可冲突检测 `FileChange`/撤回机制为条件。create-only 的撤回记录可在该机制中一并设计；本次不开始该任务。

## 2026-08-11 阶段 5 FileChange 与撤回边界设计记录

### 完成

- 确认覆盖、追加和删除不会直接实现；它们必须先满足 DEC-060 的持久化 FileChange、私有快照与哈希冲突检测前置条件。
- 固定 FileChange 的来源 Run、规范化根路径与相对路径、变更种类、变更前后哈希、可选快照引用及 `PREPARED`/`APPLIED`/`REVERTED`/`CONFLICTED` 生命周期。
- 固定撤回规则：仅处理 asAgent 自己记录且未被后续修改的变更；CREATE 删除未变化的新文件，REPLACE 原子恢复快照，DELETE 仅在目标仍不存在时独占恢复。任何状态不匹配均拒绝而不覆盖用户数据。
- 快照正文位于 `AppPaths.data_dir` 私有目录，不进入 SQLite、RunEvent、ToolCall、日志、模型上下文或 Git；初版配额为单项 5 MiB、总量 100 MiB、默认保留 30 天。

### 验证

- 检查：复核阶段 5 既有 WorkspaceResolver、create-only 文件写入、SQLite/AppPaths 边界及 DEC-009、DEC-038、DEC-039。
- 结果：通过；设计与现有“默认拒绝、显式批准、文件根隔离、用户正文不进入运行审计”的边界一致，未改变运行时代码。

### 决策变化

- 新增 DEC-060：可撤回文件变更先于覆盖、追加和删除，并以持久化 FileChange、私有快照和哈希冲突检测保证安全恢复。

### 风险或问题

- 当前 Tool Protocol 没有传入 Run 身份，SQLite Schema 也没有 FileChange 表或快照管理；因此上述设计尚未接入 create-only Tool，不能宣称当前已经可撤回。
- 根移动后的恢复不会搜索猜测；快照加密与系统 Keychain 的结合要等正式设置/桌面存储设计再决定。

### 下一步

- 在用户确认后，实现 DEC-060 的第一个代码任务：Core FileChange 不可变数据模型与 FileChangeRepository Protocol；本次不开始该任务。

## 2026-08-11 阶段 5 FileChange 实现时机调整记录

### 完成

- 确认 DEC-060 的设计继续有效，但当前不提前实现 Core FileChange 模型、Repository、SQLite 表、快照目录或撤回操作。
- 原因是现有 `filesystem.write_file` 仅能 create-only，不能覆盖、追加或删除既有用户文件；在它尚未接入真实 Runtime/UI 前，文件版本、崩溃恢复、配额清理和 Run 关联的实现成本超过当前体验收益。
- 确认未来一旦开放覆盖、追加或删除，必须先完成 DEC-060，不能以当前的 create-only Tool 绕过该前置条件。

### 验证

- 检查：复核 create-only 文件写入的独占创建语义、DEC-060 触发条件和阶段 5 路线图。
- 结果：通过；延后实现不削弱当前安全边界，也不改变已提交代码。

### 决策变化

- 无；这是 DEC-060 的实施时机调整，不修改其数据安全与冲突处理要求。

### 风险或问题

- 当前没有可撤回文件变更；这是有意范围限制。任何未来覆盖、追加或删除任务都必须先重新领取并完成 DEC-060 的 Core/Storage/快照链路。

### 下一步

- 在用户确认后，设计最小 `document.extract_text` 文档文本提取能力，优先支持 DOCX 和带文本层的 PDF；扫描型 PDF 与图片 OCR 保持后续独立任务。本次不开始该任务。

## 2026-08-11 阶段 5 文档提取实施时机调整记录

### 完成

- 确认 `document.extract_text`、DOCX/PDF 文本层解析和 OCR 不作为当前阶段 5 的下一项实现。
- 文档提取将在阶段 6/7 形成真实 Local API 与桌面交互后，依据实际体验选择常用离线格式的内置 Tool，或采用独立工作目录、权限和凭据的 MCP Tool；OCR 继续单列，不能以普通读取名义隐式执行。
- 当前阶段 5 的 WorkspaceResolver、只读工具和 create-only 写入边界保持不变；不因延后文档提取而扩大任何文件权限。

### 验证

- 检查：复核阶段 5 文件工具范围、MCP 独立资源边界与阶段 6/7 路线。
- 结果：通过；延后解析依赖和 OCR 不阻塞当前已验证的核心、持久化或文件安全基础。

### 决策变化

- 无；这是能力优先级调整，仍遵守 DEC-017 的 MCP 隔离和 DEC-039 的文件范围要求。

### 风险或问题

- 当前没有 DOCX/PDF/OCR 支持；用户文件不会被自动扫描、解析或上传。

### 下一步

- 在用户确认后，开始阶段 6 的第一个独立任务：最小 Local API 组合边界与 `/api/v1/health` 健康检查设计。本次不开始该任务。

## 2026-08-11 阶段 6 最小 Local API 健康检查工作记录

### 完成

- 新增 FastAPI 运行依赖，并以 `api.app.create_app()` 建立 Local API 的唯一 App Factory。
- 新增 `GET /api/v1/health`，固定返回 HTTP 200 与最小 liveness JSON `{"status": "ok"}`。
- 集成测试通过 HTTPX ASGITransport 验证版本化 HTTP 契约，不绑定真实网络端口。
- Health 不访问 SQLite、Agent Runtime、Provider、Secret、文件工具或后台任务；本次不引入 Uvicorn、认证、CORS、Conversation/Run 路由或 SSE。

### 验证

- 检查：运行 API Health 定向集成测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整 219 个测试通过，126 个文件格式正确，122 个源码文件 Ruff 与 strict mypy 无问题，锁定依赖解析为 40 个包。

### 决策变化

- 新增 DEC-061：阶段 6 使用 FastAPI App Factory 建立最小 Local API，先以无副作用 Health 契约验证 HTTP 边界。

### 风险或问题

- 当前 Health 只表示 ASGI 应用可响应，不代表 SQLite 已迁移、Runtime 已构造或真实模型可用；它也尚未成为监听 `127.0.0.1` 的实际 Backend 进程。
- 未实现 Token、Origin/CORS、启动握手、端口配置、业务 API 或 SSE，不能被 Electron 或外部客户端当作正式连接入口。

### 下一步

- 在用户确认后，设计并实现阶段 6 的 Server 启动边界：显式 host/port 配置、仅绑定 `127.0.0.1`、Uvicorn 生命周期与可测试的实际端口报告；本次不开始该任务。

## 2026-08-11 阶段 6 Local API Server 启动边界工作记录

### 完成

- 新增 Uvicorn 运行依赖与 `api.server.LocalApiServer`，封装单次 Local API 服务生命周期。
- Server 仅接受 `127.0.0.1`；端口只允许 `0` 或 `1–65535`。Backend 先自行绑定 TCP listener，再交给 Uvicorn，因此端口 `0` 的实际分配不依赖“先探测、后绑定”。
- 服务启动后生成不可变 `ServerReady`，包含 host、实际 port、当前 PID 与协议版本；开发 CLI 新增兼容原有聊天参数的 `serve` 命令，并以 `ASAGENT_READY ` 前缀输出单条 JSON ready 记录。
- 集成测试在真实 TCP 端口调用 `/api/v1/health`，并受控关闭 Server；同时覆盖非回环 host、越界端口与布尔端口拒绝。

### 验证

- 检查：运行 LocalApiServer 与 CLI 参数定向测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整 225 个测试通过，128 个文件格式正确，124 个源码文件 Ruff 与 strict mypy 无问题，锁定依赖解析为 42 个包。

### 决策变化

- 无；本次实现 DEC-018 的 Backend 自主回环绑定与动态端口要求，并沿用 DEC-061 的 App Factory 边界。

### 风险或问题

- ready 记录只证明 HTTP Server 已启动，不证明认证、SQLite、Runtime、Workspace 或真实模型可用；当前 Health 仍无认证。
- Server 尚未接收 Token/AppPaths/Workspace 参数，也没有 Origin/CORS、业务 API、SSE、生产日志配置、Electron 子进程握手或重启策略。

### 下一步

- 在用户确认后，设计阶段 6 的本地 API Token Bootstrap 与业务端点认证边界；本次不开始该任务。

## 2026-08-11 阶段 6 Local API Token Bootstrap 与 Health 认证工作记录

### 完成

- 新增只在内存中存在的 `LocalApiToken` 与 Bearer 认证器；凭据使用常量时间比较，缺失、格式错误或错误 Token 统一返回 401 和 `WWW-Authenticate: Bearer`。
- `create_app()` 现在显式接收本次启动 Token；当前唯一的 Health 路由也受相同认证保护，避免回环地址被错误视为身份验证。
- 新增一次性 JSON Bootstrap 读取器。开发 `asagent serve` 仅在 `--bootstrap-stdin` 模式从 stdin 读取 `{"token":"..."}`，Token 不会进入命令行、ready JSON、配置、SQLite 或日志。
- 真实手动验收确认服务输出的 `ASAGENT_READY` 仅含 host、port、PID 和协议版本；使用正确 `Authorization: Bearer ...` 请求回环 Health 返回 200 与最小 liveness JSON。

### 验证

- 检查：运行 Bootstrap/CLI/API Health/真实 TCP Server 定向测试、Ruff 格式化与检查、strict mypy 与完整 `scripts/check.sh`。
- 结果：通过；完整 236 个测试通过，131 个文件格式正确，127 个源码文件 Ruff 与 strict mypy 无问题，锁定依赖解析为 42 个包。
- 检查：以 stdin Bootstrap Token 启动 `asagent serve --bootstrap-stdin --port 0`，再以正确 Bearer Header 调用 ready 记录所示回环端口的 Health。
- 结果：通过；HTTP 200 返回 `{"status":"ok"}`，ready 记录未暴露 Token。

### 决策变化

- 新增 DEC-062：本地 API 使用一次性 stdin Bootstrap Token 并认证 Health。

### 风险或问题

- 当前 stdin Bootstrap 是源码开发与未来 Electron 子进程管道的最小 Backend 契约；Electron Main 尚未生成 Token、持有子进程 stdin、校验 ready PID/版本或轮询 Health。
- 还没有 Origin/CORS、业务 API、SSE、Token 轮换、Shutdown Endpoint 或正式 Renderer 内存传递；因此不能将当前 Server 视为完整桌面连接链路。

### 下一步

- 在用户确认后，实现阶段 6 的最小 Conversation HTTP 查询接口，并复用当前 Bearer 认证；本次不开始该任务。

## 2026-08-11 阶段 6 Conversation 列表 Local API 工作记录

### 完成

- 新增认证后的 `GET /api/v1/conversations`，固定只查询 `local-user` 的 Conversation，并仅返回 `conversation_id`、`created_at` 和 `updated_at`。
- App Factory 显式接收 Core `ConversationRepository` Protocol，因而 API 路由不依赖 SQLite；SQLite 集成测试通过注入 `SqliteConversationRepository` 验证真实读取与用户隔离。
- `serve` 组合根现在从 `--app-home` 的 AppPaths 定位数据库、执行既有迁移、构造 SQLite Conversation Repository 并在服务结束时关闭它；Token Bootstrap、回环绑定与 ready 输出语义保持不变。
- 真实手动请求确认 `.local-data` 已有的三个持久化 Conversation 能经带 Bearer Header 的 API 返回，响应不包含用户身份、消息、Run 或审计正文。

### 验证

- 检查：运行 API Health、实际 TCP Server 与 Conversation API 定向集成测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整 238 个测试通过，132 个文件格式正确，128 个源码文件 Ruff 与 strict mypy 无问题，锁定依赖解析为 42 个包。
- 检查：使用 stdin Bootstrap Token 启动 `serve`，再通过正确 Bearer Header 查询 `/api/v1/conversations`。
- 结果：通过；返回三条 `local-user` Conversation 的元数据，UTC 时间以 JSON ISO 8601 字符串表示。

### 决策变化

- 无；本次落实既有 Core Repository 注入和 DEC-062 认证边界，不新增存储或授权模型。

### 风险或问题

- 当前列表没有分页、标题、单条详情或消息读取；随着 Conversation 数量增长，列表查询策略需要单独设计，不能在本任务中无界扩展。
- 当前服务启动会确保 SQLite 已迁移并构造 Conversation Repository，但尚不构造 Agent Runtime、模型 Provider、Workspace 或 Run 管理；Health 仍不能代表它们可用。

### 下一步

- 在用户确认后，实现阶段 6 的最小单条 Conversation 消息查询接口，并明确 404、用户可见消息边界与响应排序；本次不开始该任务。

## 2026-08-11 阶段 6 Conversation 消息查询 Local API 工作记录

### 完成

- 新增认证后的 `GET /api/v1/conversations/{conversation_id}/messages`，在读取前确认 Conversation 存在且属于固定 `local-user`。
- 响应仅映射用户可见的 USER/ASSISTANT Message：稳定 `message_id`、角色、正文与创建时间；它不暴露 Conversation 身份、user_id、内部 Tool message、Run、RunEvent 或 ToolCall。
- Message 顺序直接沿用 Repository 的 Conversation 内持久化 sequence，而不是按时间猜测；其他用户 Conversation 与不存在的 Conversation 统一返回 `404 {"detail":"conversation not found"}`，避免泄露存在性。
- 真实 API 查询确认一段已有多轮工具对话以用户/助手交替顺序完整返回，其中模型工具调用细节只体现为最终可见回答，不进入此端点。

### 验证

- 检查：运行 API Health、实际 TCP Server 与 Conversation API 定向集成测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整 242 个测试通过，132 个文件格式正确，128 个源码文件 Ruff 与 strict mypy 无问题，锁定依赖解析为 42 个包。
- 检查：通过有效 Bearer Token 查询持久化 Conversation `conv_3a3ad645dc6040798920d6c9ee019e3d` 的 messages。
- 结果：通过；返回四组用户/助手可见消息及其 UTC ISO 8601 时间，未包含内部运行材料。

### 决策变化

- 无；本次复用既有单用户、Repository 注入与 DEC-062 API 认证边界。

### 风险或问题

- 当前消息接口没有分页、单条 Message 查询、Conversation 创建、编辑或删除；长 Conversation 的增量/分页读取要与 UI 滚动体验一并单独设计。
- 当前返回正文是预期的聊天显示契约；响应不得被写入 RunEvent、日志或其他审计材料，日志脱敏策略仍保持不变。

### 下一步

- 在用户确认后，实现阶段 6 的最小创建 Conversation HTTP 接口，并明确请求验证、ID/时钟生成及成功状态码；本次不开始该任务。

## 2026-08-11 阶段 6 创建 Conversation Local API 工作记录

### 完成

- 新增认证后的 `POST /api/v1/conversations`。请求体当前只允许空 JSON object；未知字段明确以 422 拒绝，避免在尚无标题或设置模型时静默接受无效客户端状态。
- API 服务端生成 `conv_` Conversation ID 与 UTC 创建/更新时间，固定保存到 `local-user`；新 Conversation 没有 Message、Run 或内部事件。
- App Factory 为测试可注入 ID 工厂和时钟，生产默认使用随机 UUID 与 UTC 当前时间；成功响应为 201，并只返回 Conversation 元数据。
- 真实 API 请求确认 stdin Bootstrap 认证后可创建 Conversation，返回 `conv_fb3f6b2692bc4c549c630f98ca53f5da` 及 UTC ISO 8601 时间。

### 验证

- 检查：运行 API Health、实际 TCP Server 与 Conversation API 定向集成测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整 245 个测试通过，132 个文件格式正确，128 个源码文件 Ruff 与 strict mypy 无问题，锁定依赖解析为 42 个包。
- 检查：通过有效 Bearer Token 向 `/api/v1/conversations` POST 空 JSON object。
- 结果：通过；HTTP 201 返回新 Conversation ID、创建时间和更新时间，未创建 Message 或 Run。

### 决策变化

- 无；本次复用既有单用户、Repository 注入、服务端 ID/时间生成与 DEC-062 API 认证边界。

### 风险或问题

- `ConversationRepository.save()` 是既有稳定 ID 的覆盖保存接口；生产 UUID 生成使碰撞可忽略，但尚无专用的 API 幂等键或 create-only Repository 原语。请求幂等和并发创建语义须在 API 契约中单独确定。
- 继续逐条即兴增加路由会使 API 语义分散；下一项应先整理阶段 6 Local API v1 契约，明确已实现与计划中的资源、状态码、错误、分页、Run 与 SSE 续传规则，再继续业务端点。

### 下一步

- 在用户确认后，定义阶段 6 Local API v1 契约与 OpenAPI 验收规则；本次不开始该任务。

## 2026-08-11 阶段 6 Local API v1 契约与 OpenAPI 验收工作记录

### 完成

- 在架构文档中固定当前 Local API v1 的内部通信定位、Bearer Token 语义、已实现端点、数据暴露边界、错误语义和尚未实现的 Run/SSE 范围。
- 认证器改用 FastAPI `HTTPBearer(auto_error=False)` 解析 Header，使运行时仍由 asAgent 统一返回 401 的同时，自动生成的 OpenAPI 正确声明 Bearer 安全方案。
- 新增 OpenAPI 契约测试，验证当前路径、方法、成功状态码与 `HTTPBearer` 安全方案；既有 HTTP 集成测试继续负责 401 等运行时行为。

### 验证

- 检查：运行 API Health 与 OpenAPI 契约定向测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；完整 246 个测试通过，133 个文件格式正确，129 个源码文件 Ruff 与 strict mypy 无问题，锁定依赖解析为 42 个包。

### 决策变化

- 无；本次落实阶段 6 路线图既有的版本化 API 与 OpenAPI/JSON 契约测试要求，沿用 DEC-018、DEC-061 与 DEC-062。

### 风险或问题

- OpenAPI 是内部 HTTP 接口的机器可读描述，不是第二套 API、公开服务或新增 Adapter；它不能替代真实 HTTP 认证、404/422 行为或未来 SSE 生命周期测试。
- 当前 v1 仍没有消息提交、Run 创建/查询/取消、分页、Origin/CORS 或 SSE；在 Electron 依赖前可以谨慎演进，但不得继续无契约地新增业务端点。

### 下一步

- 在用户确认后，实现阶段 6 的最小“提交用户消息并原子创建 Run”HTTP 入口，并先明确请求幂等、Run 身份和失败响应；本次不开始该任务。

## 2026-08-11 原子 Run 提交应用服务工作记录

### 完成

- 新增 `agent.run_submission.RunSubmissionService` 与不可变 `SubmittedRun`，统一负责读取 Conversation、可选校验预期用户、生成用户 Message 与 `CREATED` Run，并通过既有 `RunStarter` 原子提交。
- 未知 Conversation、其他用户不可访问的 Conversation 与 Starter 写入失败均不会伪造成功；Service 不调用模型、不发布事件、不完成 Run，也不依赖 SQLite/FastAPI。
- `PersistentAgentRuntime` 与两种持久化 CLI 组合路径已改为复用 Submission Service；Runtime 仅保留生成最终 AssistantMessage 身份的职责，未改变现有模型、工具、事件与终态语义。

### 验证

- 检查：运行 Submission Service 单元测试与持久化 Runtime 集成测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；定向 7 个测试、完整 249 个测试通过，135 个文件格式正确，131 个源码文件 Ruff 与 strict mypy 无问题，锁定依赖解析为 42 个包。

### 决策变化

- 无；本次复用已有 RunStarter 原子事务边界，避免 Future Local API 与持久化 CLI 重复构造用户消息/初始 Run 生命周期。

### 风险或问题

- Service 的可选 `user_id` 用于入口层的资源归属校验；当前持久化 CLI 不传该值，保持其既有“按显式 Conversation ID 运行”的开发语义。Local API 必须固定传入 `local-user`，并将未知与无权访问统一映射为 404。
- 该 Service 不包含幂等键、后台执行器、取消注册、SSE 或模型调用。HTTP 客户端请求丢失响应后的安全去重仍需单独设计和持久化支持。

### 下一步

- 在用户确认后，实现阶段 6 的最小 `POST /api/v1/conversations/{conversation_id}/messages`：验证非空内容，调用 Submission Service，返回新 Message 与 `CREATED` Run 的稳定身份；本次不开始该任务。

## 2026-08-11 阶段 6 提交 Message 与创建 Run Local API 工作记录

### 完成

- 新增认证后的 `POST /api/v1/conversations/{conversation_id}/messages`。请求只接受非空、非纯空白的 `content`，未知字段、缺失字段与空白内容均为 422；原始非空文本不会被 API 裁剪或改写。
- 路由固定以 `local-user` 调用 `RunSubmissionService`，原子持久化 UserMessage 与 `CREATED` Run；成功以 201 返回嵌套的用户可见 Message 和 Run 身份、状态与 UTC 时间。
- 不存在与不属于本地用户的 Conversation 均映射为同一 404，避免存在性泄漏；响应不包含 user_id、内部事件、ToolCall、Token 或模型输出。
- App Factory 显式注入 Submission Service；开发 `serve` 组合根构造并关闭 `SqliteRunStarter`，但本任务不启动 Provider、Agent Loop、后台 Task 或 SSE。
- OpenAPI 契约已增加该 POST 的 Bearer 保护、201 与 422 成功/验证表面断言。

### 验证

- 检查：运行 Health、真实 TCP Server、Conversation API 与 OpenAPI 契约定向测试，随后运行 Ruff、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；定向 27 个测试、完整 256 个测试通过，Ruff 格式化与检查、strict mypy、锁文件检查均通过；mypy 检查 131 个源码文件。

### 决策变化

- 无；本次按已确认的 Local API v1 契约复用 RunSubmissionService 与 RunStarter 原子事务，不改变 Provider、Runtime 或 SSE 架构。

### 风险或问题

- 每次成功 POST 都会创建一个新 Message 与 Run；当前无 idempotency key，因此客户端在响应丢失时不得自动重试并假定可去重。
- CREATED Run 当前只被持久化，尚无执行调度器、取消令牌注册、Run 查询或 SSE；这避免 HTTP 请求被模型调用阻塞，但尚未形成端到端回复闭环。

### 下一步

- 在用户确认后，设计并实现阶段 6 的最小 CREATED Run 执行调度边界：明确何时启动、如何持有/释放取消令牌、何时将 Runtime 结果持久化，以及 HTTP/SSE 如何只观察而不承担执行；本次不开始该任务。

## 2026-08-11 Persistent Runtime 已提交 Run 执行边界工作记录

### 完成

- `PersistentAgentRuntime.run()` 现在仅负责通过 Submission Service 提交用户输入，随后委托新的 `execute_submitted()` 完成模型与工具执行。
- `execute_submitted()` 只消费已经持久化的 `SubmittedRun`，并要求其 Run 状态为 `CREATED`；它不会再次创建用户 Message 或 Run。
- 已验证直接执行已有提交时，模型上下文看见原始用户消息，数据库最终只保留一个 Run、一条原用户消息与正常的最终助手消息；非 CREATED 输入在任何模型调用前被拒绝。

### 验证

- 检查：运行 Persistent Runtime 集成测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；定向 6 个测试、完整 258 个测试通过，Ruff 格式化与检查、strict mypy、锁文件检查均通过；mypy 检查 131 个源码文件。

### 决策变化

- 无；本次只是将既有 Submission/执行生命周期显式化，为后续 API Dispatcher 消费已提交 Run 消除重复写入风险。

### 风险或问题

- `execute_submitted()` 假定调用方只传入已经由 Submission Service 原子持久化的对象；它不自行重新查询或领取 Run，也没有后台 Task、取消令牌注册、崩溃恢复或并发 claim 语义。
- 当前 Local API 仍只创建 CREATED Run；在 Dispatcher 到位前，它不会自动产生模型回复。

### 下一步

- 在用户确认后，设计并实现阶段 6 的最小进程内 Run Dispatcher：从 API 收到 SubmittedRun 后创建受控后台 Task、持有并按 run_id 释放取消令牌、调用 `execute_submitted()`，但暂不实现 SSE；本次不开始该任务。

## 2026-08-11 最小进程内 Run Dispatcher 工作记录

### 完成

- 新增 `InProcessRunDispatcher`：对一个 SubmittedRun 创建以 `run_id` 命名的后台 Task 和协作式 `RunCancellationToken`，`dispatch()` 立即返回可等待的 Handle。
- 同一活跃 Run 被明确拒绝重复调度；`cancel(run_id)` 只标记同一 Token，返回是否找到活跃 Run，不强制终止协程。
- 正常完成、已请求取消和执行函数异常均会清理活跃 Token；异常转换为 `RunDispatchOutcome.error`，因此调用方可观察且不会产生未取回的 Task 异常警告。
- Dispatcher 不读取模型上下文、不选择工具、不执行工具、不写 SQLite、不更新 Run 终态，也没有接入 FastAPI 或 SSE。

### 验证

- 检查：运行 Dispatcher 定向单元测试、Ruff 格式化与检查、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；定向 4 个测试、完整 262 个测试通过，Ruff 格式化与检查、strict mypy、锁文件检查均通过；mypy 检查 133 个源码文件。

### 决策变化

- 无；本次使用既有 RunCancellationToken 与 Runtime 执行边界，未改变 AgentLoop/ToolExecutor 的模型决策与安全执行职责。

### 风险或问题

- Dispatcher 目前只适合单个 Backend 进程；重启即丢失活跃 Task 与内存 Token。CREATED Run 的崩溃恢复、执行 claim、失败终态持久化和主动 shutdown 仍待后续设计。
- `RunDispatchOutcome` 仅向持有 Handle 的进程内调用方报告异常；它不是持久化审计、API 查询或 SSE 事件。

### 下一步

- 在用户确认后，为 PersistentAgentRuntime 建立最小 Dispatcher 执行适配与失败终态持久化边界；在这之前不让 Local API 自动调度，以免后台异常使 Run 长期停留在 CREATED。本次不开始该任务。

## 2026-08-11 架构粒度约定记录

### 完成

- 确认全项目后续设计（Python、Local API、Electron 前端、构建与测试）以简单、清晰、可验证为优先，不为“架构感”或未经证实的未来需求继续细拆包装层。
- 新增对象前必须能说明它独立的调用者、生命周期、失败处理或业务规则；若仅有单一调用者且只转发，默认合并到现有边界。
- 当前 Run 路径固定为 Submission Service、PersistentAgentRuntime、InProcessRunDispatcher 三层；不实现仅包裹 Runtime 的 PersistentRunExecutor。意外执行异常的失败终态归 PersistentAgentRuntime。该约定只指导后续增量，已验证的既有实现不因抽象偏好单独重构。

### 验证

- 检查：复核当前 Submission、Runtime、Dispatcher 的数据流、调用者和异常归属。
- 结果：通过；三层分别覆盖原子提交、模型/工具执行终态、后台任务/协作式取消，均有独立测试价值；拟议包装层没有独立调用者或规则。

### 决策变化

- 新增 DEC-063：以独立生命周期和失败语义控制抽象粒度。

### 风险或问题

- “保持简单”不等于把线程/Task 生命周期、事务或安全策略塞进路由；当实际出现第二个调用者、跨进程恢复、持久化 claim 或 SSE 多播等新失败模式时，应重新评估边界。

### 下一步

- 在用户确认后，增强 `PersistentAgentRuntime.execute_submitted()` 对意外执行异常的 FAILED 终态持久化；随后再将现有 Dispatcher 接到 Runtime。本次不开始该任务。

## 2026-08-11 Persistent Runtime 意外异常失败终态工作记录

### 完成

- `execute_submitted()` 在读取历史或执行 AgentLoop 出现意外 `Exception` 时，先通过既有 RunFinisher 持久化同一 Run 的 `FAILED` 终态且不写 AssistantMessage，再原样抛出异常。
- 正常的 AgentLoop 结果路径保持不变，仍由 Loop 返回的 `COMPLETED`、`FAILED`、`CANCELLED` 或 `LIMIT_REACHED` 状态统一完成。
- 正常路径最后一次 RunFinisher 写入不纳入异常捕获；若 SQLite/Finisher 本身不可写，错误直接传播，不假装已经保存 FAILED。

### 验证

- 检查：运行 Persistent Runtime 集成测试，其中 Provider 以未分类 RuntimeError 模拟 Loop 外泄异常；随后运行 Ruff、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；定向 7 个测试、完整 263 个测试通过，Ruff 格式化与检查、strict mypy、锁文件检查均通过；mypy 检查 133 个源码文件。

### 决策变化

- 无；这是 DEC-063 下 Runtime 已有终态职责的补全，不新增包装器或改变 Dispatcher/AgentLoop 的边界。

### 风险或问题

- 这是一项尽力而为的持久化：如果 Finisher 同样失败，原始/存储异常仍会传播，Run 可能保留 CREATED；后续恢复、事件补齐和用户可见错误仍需单独设计。
- 意外异常路径当前不额外生成 `run.failed` Event；Run 状态的持久化与事件流补齐必须在后续 SSE/恢复任务中一起确定，不能伪造连续事件序列。

### 下一步

- 在用户确认后，将 InProcessRunDispatcher 以一个简单的组合根执行函数接到 PersistentAgentRuntime，并保持异常由 Dispatcher Outcome 观察；不新增 PersistentRunExecutor。本次不开始该任务。

## 2026-08-11 阶段 6 后台 Run 执行 Local API 工作记录

### 完成

- `POST /api/v1/conversations/{conversation_id}/messages` 在 Submission Service 原子创建 USER Message 与 CREATED Run 后，调用注入的 `InProcessRunDispatcher` 安排后台执行；HTTP 不等待模型，因此始终立即返回 201 与创建时的 Run 表面。
- 开发 `serve` 组合根现在使用 SQLite Repository、Starter、Finisher、持久化离线 `development-tools` Runtime 和 Dispatcher 形成端到端闭环；后台 Run 会持久化终态、用户可见 AssistantMessage、RunEvent 与 ToolCall。
- Dispatcher 现在保存活跃 Task；`aclose()` 拒绝后续调度，对活跃 Run 请求协作取消、有限等待并在必要时取消剩余 Task。服务退出按 Dispatcher、Finisher、Starter、Run Repository、Conversation Repository 的顺序关闭，避免任务访问已关闭 SQLite。
- 本任务明确 `serve` 仅使用离线 development runtime；真实 `--profile` 服务端组合、HTTP Run 取消、Run 查询、SSE、崩溃恢复与跨进程执行 claim 均未提前实现。

### 验证

- 检查：运行 Dispatcher、API dispatch/health/server/conversations/OpenAPI 定向测试，随后运行 Ruff、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；定向 34 个测试、完整 266 个测试通过，Ruff 格式化与检查、strict mypy、锁文件检查均通过；mypy 检查 134 个源码文件。

### 决策变化

- 无；本次按 DEC-063 直接在 `serve` 组合根连接既有 Submission Service、Runtime 与 Dispatcher，不新增仅转发的执行包装层。

### 风险或问题

- Dispatcher 是进程内实现；进程崩溃或强制关闭后仍可能留下 CREATED Run，尚无持久化 claim、恢复或补齐终态机制。
- 当前 API 只能提交并异步执行 Run，尚不能按 Run ID 查询状态、请求取消或订阅事件；客户端也无法仅凭 POST 响应获取最终文本。

### 下一步

- 在用户确认后，实现阶段 6 最小 Run 查询 API：按 local-user 与 Conversation 归属返回稳定 Run 身份、状态和时间；本次不开始 HTTP 取消或 SSE。

## 2026-08-11 阶段 6 Run 查询 Local API 工作记录

### 完成

- 新增 `GET /api/v1/runs/{run_id}`：经既有 `RunRepository.get` 读取 Run，再经所属 Conversation 校验固定 `local-user` 归属；缺失或其他用户统一 404 `run not found`，不泄露跨用户存在性。
- `RunResponse.status` 改为完整 `RunStatus`，使查询可反映 `created → completed/failed/...` 等已持久化状态；App Factory 必填注入 `runs: RunRepository`，不新增 RunService、缓存或轮询器。
- `serve` 传入既有 SQLite `runs`；Run 资源集成测试放在独立的 `tests/integration/test_api_runs.py`；OpenAPI 契约路径集合同步包含该 GET。

### 验证

- 检查：运行 Run 查询、OpenAPI、conversations/health/server 与 dispatch 相关测试，随后 Ruff、strict mypy 与完整 `scripts/check.sh`。
- 结果：通过；定向 31 个测试、完整 269 个测试通过，Ruff 格式化与检查、strict mypy、锁文件检查均通过；mypy 检查 135 个源码文件。

### 决策变化

- 无；归属检查复用 Conversation Repository，不在 Run 上引入 `user_id` 或新 Core 类型。

### 风险或问题

- 客户端仍需轮询 GET 才能观察状态变化；尚无 HTTP 取消与 SSE，长时间 Run 的协作中断与事件流续传仍待后续任务。

### 下一步

- 在用户确认后，实现最小 HTTP 取消（对活跃 Run 请求协作取消）；本次不开始 SSE。

## 2026-08-11 阶段 6 HTTP Run 协作取消工作记录

### 完成

- 新增认证后的 `POST /api/v1/runs/{run_id}/cancel`。路由先复用既有 Run/Conversation 的 local-user 归属检查，再调用注入的 `cancel_run` 回调请求现有 Dispatcher 协作取消。
- 活跃 Run 返回 202 及稳定 Run ID 和 `cancellation_requested: true`；不存在或其他用户 Run 统一为 404，已不活跃 Run 返回 409。取消请求不直接写 SQLite 状态，也不强制终止模型或工具调用。
- 开发 `serve` 将既有 `dispatcher.cancel` 注入 App Factory。Runtime 与 AgentLoop 保持最终状态职责：它们在已有安全检查点观察 Token 后持久化 `CANCELLED`。
- OpenAPI 和 Run API 集成测试已覆盖成功、非活跃、未知/跨用户与 Bearer 认证路径；没有新增取消 Service、状态机或缓存。

### 验证

- 检查：运行 Run API、OpenAPI 与既有 API 定向测试，随后运行 Ruff、strict mypy 和完整 `scripts/check.sh`。
- 结果：通过；定向 34 个测试、完整 272 个测试通过，Ruff 格式化与检查、strict mypy、锁文件检查均通过。

### 决策变化

- 无；本次直接桥接已验证的 `InProcessRunDispatcher.cancel()`，未改变协作取消、Runtime 终态持久化或 SSE 的既有边界。

### 风险或问题

- 202 仅表示 Backend 已接受协作取消请求；Provider 或 Tool 若尚未到达安全检查点，Run 不会立即变为 `cancelled`，客户端仍需查询状态。
- 当前仍缺少 SSE 事件帧、断线续传和实时订阅；轮询只是临时可观察方式，不是最终聊天体验。

### 下一步

- 在用户确认后，实现阶段 6 最小认证 SSE：先从持久化 `RunEvent` 按 sequence 回放，再为活跃 Run 连接实时事件；本次不改变 Dispatcher 或引入 Electron。

## 2026-08-11 阶段 6 认证 RunEvent SSE 工作记录

### 完成

- 新增 `GET /api/v1/runs/{run_id}/events`：复用 local-user 归属检查后，以 `text/event-stream` 按 `sequence` 回放持久化 `RunEvent`；`after_sequence`（`>=0`）支持重连不重复。
- 活跃 Run 用进程内短轮询观察 Repository 新增事件，直到 Run 进入终态或客户端断开；终态后自然结束流。不新增 SSE Service、事件总线或多播层。
- SSE 帧使用事件 `sequence` 作为 `id`，`event_type` 作为 `event`，`data` 为稳定排序的 JSON object；帧组装与轮询留在 `create_app()` 同文件私有辅助函数内。
- ASGI 回放测试位于 `test_api_runs.py`；真实 TCP 流式验证放在 `test_api_server.py`，覆盖事件追加后帧到达与终态耗尽。

### 验证

- 检查：运行 Run API、Server、OpenAPI 定向测试，随后 Ruff、strict mypy 与完整 `scripts/check.sh`。
- 结果：通过；定向 17 个测试、完整 277 个测试通过，Ruff 格式化与检查、strict mypy、锁文件检查均通过；mypy 检查 135 个源码文件。

### 决策变化

- 无；观察层只读 `RunRepository.list_events` / `get`，不改变 Runtime、Dispatcher 或事件写入路径。

### 风险或问题

- 当前是 Repository 轮询而非推送；活跃连接有约 100ms 观察延迟，高并发长连接时需再评估。
- 尚未支持 `Last-Event-ID` Header；客户端暂以查询参数 `after_sequence` 续传。Electron fetch-based SSE 与 Origin/CORS 仍待后续。

### 下一步

- 在用户确认后，推进 Electron Main/Renderer 接入本 Local API，或补 `Last-Event-ID` 与真实 Provider `serve` 配置；本次不自动开始。

## 2026-08-11 阶段 7 Electron 开发骨架工作记录

### 完成

- 在仓库 `desktop/` 下通过官方 `@quick-start/electron` 的 `react-ts` 模板创建了 Electron + React + TypeScript + electron-vite 工程，并生成独立的 `package-lock.json`。
- 已在 macOS 开发环境执行 `npm install` 与 `npm run dev`，Electron 示例窗口可正常启动；当前使用 Electron 39、Chromium 142 与 Node 22 运行时。

### 验证

- 检查：在 `desktop/` 执行 `npm run dev`。
- 结果：通过；开发窗口已显示 React/TypeScript 模板页面。

### 决策变化

- 无；采用路线图既有的 Electron + React + TypeScript、Vite/electron-vite 开发方向，尚未接入 Python Sidecar 或 Local API。

### 风险或问题

- 生成模板仍包含示例 UI、通用 Electron API 暴露与 `sandbox: false`，因此它只证明开发工具链可用，不能视为安全桌面客户端。
- 尚未启动 Backend、传递 Token、校验 Health、调用 HTTP API 或订阅 SSE。

### 下一步

- 在用户确认后，收紧 BrowserWindow/Preload 边界并替换示例 Renderer 为最小 asAgent 聊天壳；本次不连接 Backend。

## 2026-08-11 阶段 7 安全桌面壳工作记录

### 完成

- `BrowserWindow` 现在显式启用 `contextIsolation: true`、`nodeIntegration: false` 与 `sandbox: true`；阻止新窗口，并拒绝导航到非当前开发/生产 Renderer 来源。
- 删除模板暴露的通用 `window.electron.ipcRenderer` 与 ping 通道；Preload 只暴露 `window.desktop.getAppInfo()`，Main 在返回只读应用名和版本前校验 IPC 发起 Frame 的来源。
- 删除 Electron 模板素材与示例组件，替换为响应式 asAgent 聊天壳：侧栏、当前 Conversation、消息区、输入框和显式的“Backend 未连接”状态。输入仅在 Renderer 内显示未发送提示，不会伪造模型调用。

### 验证

- 检查：在 `desktop/` 运行 Prettier、TypeScript 类型检查、ESLint、生产构建和 `npm run dev`。
- 结果：通过；Main、Preload 和 Renderer 均成功构建，Electron 开发窗口显示新的 asAgent 聊天壳。

### 决策变化

- 无；本次落实既有 Main/Preload/Renderer 最小权限边界，不新增前端状态库、IPC 泛化层、Backend 生命周期管理或 API 客户端。

### 风险或问题

- 当前 `getAppInfo()` 只是验证窄 IPC 的只读示例；它不提供端口、Token、文件访问、Shell 或通用消息转发。
- 页面仍是本地静态预览；未启动 Python Sidecar，不能加载 Conversation、提交 Message、查询 Run 或订阅 SSE。

### 下一步

- 在用户确认后，实现 Electron Main 启动/停止开发 Python Backend、通过 stdin 传递一次性 Token、解析 ready 记录并轮询认证 Health；本次不让 Renderer 直接取得 Token 或请求业务 API。

## 2026-08-11 阶段 7 开发 Python Sidecar 生命周期工作记录

### 完成

- 新增 Electron Main 的 `BackendLauncher`，在开发模式从仓库根以 `uv run asagent serve --bootstrap-stdin --app-home .local-data --port 0` 启动 Python Backend；Token 在 Main 内生成，只经该子进程 stdin 传递。
- Launcher 读取并校验立即刷新的 `ASAGENT_READY` 记录，再以 Bearer Token 轮询认证 Health；失败时停止自己持有的子进程，成功后才显示 BrowserWindow。退出时先请求 Launcher 停止其子进程。
- Preload 仅新增无敏感的 `getBackendStatus()`；Renderer 显示 `Backend ready`，没有取得 Token、端口、通用 IPC、文件访问或业务 API 能力。
- 新增 Vitest 与 Launcher 单元测试，覆盖私有 Bootstrap、ready/Health 成功路径和非法 ready 记录时终止自有子进程。Python CLI ready 输出改为 `flush=True`，保证管道握手不会被 stdout 缓冲阻塞。

### 验证

- 检查：Python Ruff、strict mypy 和完整 `scripts/check.sh`；桌面 TypeScript、ESLint、Vitest、生产构建与真实 `npm run dev`。
- 结果：通过；Python 完整 277 个测试通过，140 个文件格式正确，135 个 Python 源码文件 Ruff 与 strict mypy 无问题；Vitest 2 个测试通过，Electron 生产构建和真实启动均显示 `Backend ready`。

### 决策变化

- 无；实现既有临时 Token、动态端口、ready 握手与 Health Check 策略，不新增 Renderer Token 传递、通用 IPC 或独立 Backend 服务层。

### 风险或问题

- 当前 Launcher 仅适用于源码开发的 `uv` 命令和仓库 `.local-data/`；发布版必须改用 PyInstaller Sidecar 与 Electron `userData`，不能复用此开发路径假设。
- Launcher 当前只在启动时把 ready 状态提供给 Renderer；Backend 运行后崩溃的实时 UI 状态、受限业务 HTTP 客户端、Conversation/Message 读取和 SSE 仍待后续独立任务。

### 下一步

- 在用户确认后，让 Electron Renderer 通过保持 Token 私有的窄 Preload API 读取真实 Conversation 列表与 Message 历史；本次不提交消息、不创建 Run 或订阅 SSE。

## 2026-08-11 阶段 7 Electron 真实对话历史只读工作记录

### 完成

- `BackendLauncher` 复用自身持有的 loopback endpoint 与仅 Main 可见的 Bearer Token，新增两个固定只读操作：列出 Conversation 与读取指定 Conversation 的用户可见 Message；没有新增通用 HTTP 客户端模块。
- Main 只为这两个操作增加来源校验后的 IPC handler；Preload 仅暴露对应的窄方法。Renderer 不能读取 Token、端口、任意 URL、写入 API 或 SSE。
- Renderer 已显示 SQLite 中真实的 Conversation 列表与 Message 历史；选择 Conversation 会加载其历史。新建 Conversation 与发送 Message 仍明确禁用，因此这次读取不会创建 Message 或 Run。
- Launcher 测试新增私有认证连接的 Conversation 读取覆盖，确认请求仍携带 Bearer Header。

### 验证

- 检查：在 `desktop/` 运行 Prettier、TypeScript 类型检查、ESLint、Vitest 和生产构建，并以真实 `npm run dev` 查看本地历史。
- 结果：通过；TypeScript、ESLint 和生产构建成功，Vitest 3 个测试通过；Electron 开发窗口已人工确认显示真实 Conversation 和 Message 数据。

### 决策变化

- 补充 DEC-062：Token 仅保存在 Electron Main 与 Backend；Renderer 通过固定、来源校验的 Preload/Main 操作取得允许的只读数据，而非获得 Token 或通用本地 HTTP 权限。

### 风险或问题

- Conversation 当前没有标题，因此界面只能显示稳定 ID 的短后缀；标题生成或编辑必须随其对应的持久化/API 任务单独设计。
- 当前只读历史不会随其他运行中的写入自动刷新，也不显示 Run 状态或实时 Event；这些能力应在 Message 提交后，通过既有 Run 查询和 SSE 契约以一个独立任务接入。

### 下一步

- 在用户确认后，实现 Electron 的最小 Conversation 创建与 Message 提交：仍由 Main 持有 Token，Renderer 只调用固定 Preload 操作；随后再单独接入 Run 状态和 SSE。本次不提前开始该任务。

## 2026-08-11 阶段 7 Electron 最小 Conversation 与 Message 提交工作记录

### 完成

- `BackendLauncher` 的私有认证连接新增两个固定 `POST` 操作：创建空 Conversation，以及向指定 Conversation 提交非空 Message；所有请求仍由 Main 持有 Bearer Token。
- Main 对两个 IPC 操作继续验证 Renderer 来源，并验证 Conversation ID 和 Message 内容；Preload 只暴露具名操作，不提供 Token、端口、任意 URL 或通用 IPC 转发。
- Renderer 可创建并自动选择新 Conversation，提交后立即显示 API 返回的 USER Message 与 `Message submitted. Waiting for a response.`。发送期间禁用会改变选择的操作，避免异步响应写入错误 Conversation。
- Launcher Vitest 覆盖创建和提交请求的 POST 方法、JSON 正文与 Bearer Header；本任务未改动 Python Core/API 契约。

### 验证

- 检查：在 `desktop/` 运行 Prettier、TypeScript 类型检查、ESLint、Vitest、生产构建及真实 `npm run dev`。
- 结果：通过；TypeScript、ESLint 和生产构建成功，Vitest 4 个测试通过；Electron 开发窗口已人工确认创建新 Conversation、显示提交的 `hi` 与等待提示。

### 决策变化

- 补充 DEC-062：写入也通过 Main 持有 Token 的固定操作完成；提交与异步 Run 观察仍为两个独立职责。

### 风险或问题

- 后端会立刻在后台执行 Run，但当前 Renderer 没有 Run ID、状态轮询或 SSE，因此不会自动显示 AssistantMessage。
- `npm run dev` 是常驻开发服务，必须先以 `Ctrl+C` 结束，才能在同一终端执行后续命令；粘贴时勿附带终端的 bracketed-paste 控制字符或 `~`。

### 下一步

- 在用户确认后，接入最小 Run 状态观察：提交后保留 Run ID，查询终态并重新读取历史；SSE 实时事件作为紧随其后的独立任务。本次不提前开始。

## 2026-08-11 阶段 7 Electron 实时 Run Activity 与协作取消工作记录

### 完成

- `BackendLauncher` 通过 Main 私有 Bearer Token 打开每个提交 Run 的认证 SSE 流，解析安全 RunEvent；Main 只向对应的受信任 Renderer 推送固定 Run 更新，并在终态、错误、窗口销毁或应用退出时关闭自身持有的流。
- Renderer 在提交后保存 `run_id`，以临时对话内 Activity 卡片保留 `run.started`、模型、工具和终态状态；Run 终态后重读 Message 历史，显示持久化的 AssistantMessage。
- Stop 按钮调用既有协作取消 API；它只表示取消请求已送达，直到 `run.cancelled` 等终态事件到达才恢复输入。
- 聊天布局改为固定 header/composer、仅消息区滚动，较长 Activity 不会将输入框推出窗口可视区域。

### 验证

- 检查：在 `desktop/` 运行 Prettier、TypeScript 类型检查、ESLint、Vitest 和生产构建，并以 `npm run dev` 人工发送 `calculate 123 * 456`。
- 结果：通过；桌面定向 Vitest 5 个测试、类型检查、ESLint 与生产构建成功。人工确认 Activity 保留完整事件序列、Calculator 最终结果为 `56088`，composer 固定在窗口底部。

### 决策变化

- 补充 DEC-062：实时事件由 Main 解析、在 Renderer 作为临时 Activity 展示，仍不突破 Token 与内部事件边界。

### 风险或问题

- 当前 Activity 只属于本次打开的界面会话；刷新或重启后不恢复该卡片，但最终 Message 与可回放 RunEvent 均已持久化。
- 本次仅支持单个活跃 UI Run，且不做断线自动重连；后续应在真实 Provider 体验后评估是否需要基于 `after_sequence` 的受控续传。

### 下一步

- 在用户确认后，为开发 Electron Sidecar 增加可选的真实 DeepSeek Profile：复用现有 providers.toml 与开发 `.env`，保持离线 `development-tools` 默认值，且不把 API Key 暴露给 Renderer。本次不提前开始。

## 2026-08-11 阶段 7 Electron 真实 Provider 开发验收工作记录

### 完成

- `serve` 现可复用 CLI 已有的成对 `--profile`、`--secret-env` 配置；无该参数对时继续组合离线 `development-tools` Runtime，有该参数对时以同一 SQLite/API/Dispatcher 路径组合真实 Provider Runtime。
- Electron 新增显式 `npm run dev:deepseek`。它仅传递 DeepSeek Profile 名、Secret 环境变量名和 `.env` 路径给 Main/Sidecar；API Key 仍只在 Python 环境中解析，未进入 Renderer、Preload、IPC、URL 或日志。
- Sidecar 的真实 HTTP Client 覆盖整个服务生命周期；真实 Provider 配置或调用失败不会回退至离线 Echo 行为。

### 验证

- 检查：在 `desktop/` 执行 Prettier、TypeScript 类型检查、ESLint、Vitest 和生产构建；随后执行 Python `scripts/check.sh`。
- 结果：通过；桌面 Vitest 6 个测试、桌面格式/类型/静态检查/构建均成功，Python 完整门禁 277 个测试通过。
- 人工验收：以 `npm run dev:deepseek` 启动桌面端，输入要求调用 Calculator 计算 `123 * 456` 的英文提示；真实 DeepSeek 返回 `56088`，Activity 依次显示 Run、模型、工具及完成事件。

### 决策变化

- 补充 DEC-062：默认离线与显式真实 Provider 开发入口并存，密钥只由 Python Sidecar 从开发 `.env` 读取。

### 风险或问题

- `.env` 仅适合源码开发；正式桌面版仍需在后续设置/Secret Store 工作中接入系统凭据存储。
- 当前 `dev:deepseek` 名称是首个已验证 Profile 的便利入口；未来应由设置页选择 Provider Profile，而不是为每个 Provider 添加 npm 脚本。

### 下一步

- 在用户确认后，进行一次阶段 7 体验回顾并选择下一条真实用户价值路径（例如 Conversation 标题，或受限文件工具的桌面权限交互）；不提前实现设置页或正式打包。

## 2026-08-11 阶段 7 Provider-aware Privacy Disclosure 工作记录

### 完成

- Electron Main 依据当前 Sidecar 启动配置向 Renderer 提供仅含 `local` / `external` 的处理模式；该数据不包含 Provider 名、端口、Token 或 API Key。
- 顶栏和 Privacy 页面在离线模式显示本地处理承诺，在真实 Provider 模式显示外部模型已启用以及请求内容、必要工具结果可能发送给选定 Provider 的说明。
- Privacy 统计将误导性的固定 “Data sent externally: 0” 改为 “External model access: Off / Enabled”。

### 验证

- 检查：在 `desktop/` 执行 Prettier、TypeScript 类型检查、ESLint、Vitest、生产构建及 `git diff --check`。
- 结果：通过；桌面 Vitest 6 个测试、全部静态检查和构建成功。
- 人工验收：分别以 `npm run dev` 和 `npm run dev:deepseek` 启动，确认顶栏与 Privacy 页面在本地和外部模型模式下显示相应的准确披露。

### 决策变化

- 补充 DEC-062：Privacy 披露由 Main 持有的安全处理模式驱动。

### 下一步

- Conversation 标题闭环已实现；在用户确认后继续阶段 7 体验回顾并选择下一条真实用户价值路径，不提前实现设置页或正式打包。

## 2026-08-11 阶段 7 Conversation 标题最小闭环工作记录

### 完成

- `Conversation` 增加可选 `title`；标题生成留在 `RunSubmissionService`，首条消息规范化截断至 60 字符，已有标题不被覆盖。
- `RunStarter` 接收完整 Conversation，在同一事务中更新 title/`updated_at` 并写入用户消息与 CREATED Run。
- SQLite schema/Alembic `20260811_02`、Repository、Local API `ConversationResponse`/`SubmitMessageResponse`，以及桌面 Main/Preload/Renderer 类型均已携带 `title`；提交成功后侧栏立即用返回的 conversation 刷新显示。

### 验证

- 检查：定向 pytest、`ruff format`/`check`、`mypy`、`scripts/check.sh`，以及 `desktop/` 的 format、typecheck、lint、test、build。
- 结果：通过；Python 280 个测试、桌面 Vitest 6 个测试与桌面构建成功。
- 人工验收：用户已以桌面端新建会话并发送消息，确认侧栏立即显示规范化、截断后的标题。

### 决策变化

- 补充 DEC-062：标题由首条消息确定性生成，且与初始 Message/Run 原子持久化。

### 风险或问题

- 既有本地数据库需通过 Alembic 升级至 `20260811_02`；桌面 Sidecar 启动时会执行既有升级路径。
- Create Conversation 仍禁止请求体携带 `title`；标题只由首条消息提交产生。

### 下一步

- 在用户确认后，继续阶段 7 体验回顾并领取下一项真实用户价值路径；不提前实现手动标题编辑、模型摘要标题或设置页。

## 2026-08-11 阶段 7 最近活跃会话排序工作记录

### 完成

- SQLite `ConversationRepository` 与 Local API 的 Conversation 列表现按 `updated_at` 倒序、再按稳定 Conversation ID 倒序返回。
- 桌面 Renderer 在创建 Conversation 或提交 Message 后使用相同规则更新本地列表，当前会话无需刷新即可移至侧栏顶部。

### 验证

- 检查：Conversation Repository/API 定向测试、Ruff、strict mypy、完整 `scripts/check.sh`、Electron 的格式化、类型检查、ESLint、Vitest 与生产构建。
- 结果：通过；定向 22 个 Python 测试、完整 Python 门禁 281 个测试、桌面 Vitest 6 个测试及桌面构建均成功。

### 下一步

- 在用户确认后，选择下一条阶段 7 真实用户价值路径；优先评估持久化 Activity 总览，而不提前实现权限设置、搜索或 Connector。

## 2026-08-11 阶段 7 Assistant Markdown 显示工作记录

### 完成

- 桌面 Chat 对 AssistantMessage 接入安全 Markdown 渲染，支持标题、列表、引用、行内代码和代码块；UserMessage 保持原样显示。
- 新增 `react-markdown` 前端依赖，未启用原始 HTML 解析；模型输出不会直接注入 DOM。
- 当前 UI 其余功能占位保持冻结，后续统一在产品完善阶段接线，不阻塞阶段 7 收尾和阶段 8 MCP。

### 验证

- 检查：在 `desktop/` 执行 Prettier、TypeScript 类型检查、ESLint、Vitest、生产构建及 `git diff --check`。
- 结果：通过；桌面 Vitest 6 个测试、全部静态检查和构建成功。
- 人工验收：真实 DeepSeek 返回的 Markdown 标题、清单、引用与 Python 代码块均已正确显示。

### 下一步

- 先完成阶段 7 的 PyInstaller Sidecar 打包冒烟测试；通过后进入阶段 8 的测试 stdio MCP Server，不再继续扩展当前 UI 占位页面。

## 2026-08-11 阶段 7 PyInstaller Sidecar 首次手动冒烟工作记录

### 完成

- 增加 `pyinstaller` 开发依赖与 `scripts/build_backend.py`，生成
  `desktop/build/dist/asagent-backend/asagent-backend` 的 onedir Sidecar。
- 将 `alembic.ini`、`alembic/` 迁移资源打进 bundle，并显式收集 `aiosqlite`；
  冻结 CLI 通过 `sys._MEIPASS` 定位 Alembic 配置，源码 CLI 保持原有仓库路径。
- 忽略 `desktop/build/` 产生的本地构建产物。

### 验证

- 在临时工作目录（非源码根）启动打包后的可执行文件，成功取得动态端口的
  `ASAGENT_READY` 记录。
- SQLite 仅写入显式 `--app-home/.../data/asagent.sqlite3`；bundle 安装目录未出现
  `*.sqlite3` 文件。

### 下一步

- 将该 Sidecar 验收自动化：从独立临时目录启动 bundle，完成认证 Health、创建会话、
  离线 `calculate 2 + 2` 工具回合及数据位置断言。自动化通过后才结束阶段 7，并进入
  阶段 8 的最小 stdio MCP Server。

## 2026-08-11 阶段 7 PyInstaller Sidecar 自动化验收与阶段收尾

### 完成

- 新增 `scripts/smoke_backend_bundle.py`，以独立临时工作目录启动已构建的 onedir
  Sidecar，通过 stdin 传递临时 Token，不暴露 Token 到命令行或日志。
- 脚本依次验证认证 Health、创建 Conversation、提交 `calculate 2 + 2`、Run 完成后
  的 `Tool result: 4`，并断言 SQLite 只写入 `--app-home/data/asagent.sqlite3`、bundle
  目录没有 SQLite。
- 阶段 7 完成：Electron 最小安全集成与本地 Sidecar 的首次自动化冒烟均已验收。当前
  UI 的未实现占位继续冻结，正式 electron-builder 资源携带、签名、公证和安装器留给
  阶段 12。

### 验证

- `uv run python scripts/build_backend.py` 成功生成 `desktop/build/dist`。
- `uv run python scripts/smoke_backend_bundle.py` 成功退出（`SMOKE_EXIT=0`）。
- `uv run ruff check scripts/build_backend.py scripts/smoke_backend_bundle.py`、
  `uv run mypy`（135 个 source files）和 `scripts/check.sh`（281 passed）均通过。

### 下一步

- 进入阶段 8：先实现最小测试 stdio MCP Server 的 JSON-RPC `initialize`、
  `notifications/initialized`、`tools/list` 与 `tools/call` 闭环；不先接入生产 MCP
  Server、Streamable HTTP、Electron 设置页或真实外部服务。

## 2026-08-11 阶段 8 MCP 协议基线决策

### 完成

- 阶段 8 的协议基线由旧版握手调整为 MCP `2026-07-28` modern-first：使用可选
  `server/discover` 发现版本/能力，后续请求携带自身协议版本、Client 身份和能力元数据。
- 为兼容已有 stdio 生态，确认保留受限 legacy fallback：现代探测失败或超时时必须关闭
  探测进程，再以全新子进程走旧版 `initialize` / `notifications/initialized`；不得在同一
  已被未知请求影响的 stdio 会话内直接回退。
- 该差异仅位于未来 `McpClient` 传输边界；AgentLoop、ToolExecutor、Tool Snapshot 与
  Provider 工具调用契约不因协议版本改变。

### 下一步

- 先实现仅支持 MCP `2026-07-28` 的最小测试 stdio Server，覆盖 `server/discover`、
  `tools/list`、`tools/call`、JSON-RPC 错误和 stderr 日志；不在本任务接入 Client、
  fallback、真实第三方 Server 或 Tool Registry。

## 2026-08-12 阶段 8 现代 stdio MCP 测试 Server 工作记录

### 完成

- 新增测试专用、无外部依赖的 stdio JSON-RPC Server：
  `tests/fixtures/mcp_test_server.py`。
- Server 只接受带完整现代 `_meta` 的 MCP `2026-07-28` 请求；实现
  `server/discover`、`tools/list` 和 `tools/call`，并提供确定性 `add` 工具与 JSON
  Schema。
- stdout 只输出换行分隔的 JSON-RPC Response；启动诊断写入 stderr。集成测试覆盖现代
  发现、工具列举、正常调用、无效 JSON、工具执行参数错误和未知工具的协议错误边界。
- 不实现产品 MCP Server、McpClient、旧版 fallback、外部进程配置或 Tool Registry 接入。

### 验证

- `tests/integration/test_mcp_test_server.py` 通过；完整 `scripts/check.sh` 为 283 passed。
- Ruff、strict mypy（137 个 source files）与锁文件检查均通过。

### 下一步

- 将远程 MCP Tool 描述与调用结果包装为现有 `ToolDefinition` / `Tool` 契约，并以明确的
  MCP 命名空间接入 `ToolRegistry`；仍不实现 Server Manager、外部配置、legacy fallback、
  分页或真实第三方 Server。

## 2026-08-12 阶段 8 最小现代 stdio MCP Client 工作记录

### 完成

- 新增 `src/asagent/tools/mcp.py` 的最小 `McpClient`，以命令元组启动受控 stdio 子进程，
  使用现代 `_meta` 请求 `server/discover`、`tools/list` 与 `tools/call`。
- 每条请求使用递增 JSON-RPC id，并以单一在途请求和有界等待保证 Response 配对；超时、
  EOF、无效 JSON 或 id 不匹配会关闭子进程并报告协议/传输错误。
- Client 将 JSON-RPC error 映射为 `McpRemoteError`，但保留 `tools/call` 的
  `result.isError` 为结构化工具结果，区分协议失败与模型可依据结果修正的工具失败。
- 集成测试使用现有测试 Server 覆盖发现、工具列举、正常 `add` 调用和远端未知工具错误；
  当前未接入 `ToolRegistry`、Agent Loop、legacy fallback、分页、通知或外部 Server 配置。

### 验证

- `tests/integration/test_mcp_client.py` 通过；完整 `scripts/check.sh` 为 285 passed。
- Ruff、strict mypy（139 个 source files）与锁文件检查均通过。

### 下一步

- 将发现到的 MCP Tool 包装为现有 `ToolDefinition` / `Tool`，并以明确命名空间接入
  `ToolRegistry`；保持本次 Client 的现代协议和错误边界不变。

## 2026-08-12 阶段 8 MCP Tool 接入 Registry 工作记录

### 完成

- 在 `src/asagent/tools/mcp.py` 增加 `McpTool` 与异步 `register_mcp_tools`：从已启动的
  `McpClient.list_tools()` 创建工具并注册到现有 `ToolRegistry`。
- 工具 ID 为 `mcp:{server_name}:{tool_name}:{schema_hash}`；`display_name` 优先 MCP
  `title`；schema/description 沿用远端描述；声明为 `medium` 风险、需要 `mcp.execute`
  权限且需要审批。
- `execute` 调用 `client.call_tool`：`result.isError` 以 `Error: ...` 普通文本返回模型；
  JSON-RPC / 传输层错误仍抛异常，由既有 Agent Loop 配对错误结果。

### 验证

- `tests/integration/test_mcp_tool_registry.py` 通过：启动测试 MCP Server、注册后找到
  `mcp:test-server:add:` 前缀工具，经 `ToolExecutor`（`mcp.execute` + 同意审批）调用
  `{"left": 2, "right": 3}` 得到 `"5"`，并断言 risk / 权限 / 审批元数据。
- 完整 `scripts/check.sh` 为 286 passed；Ruff、strict mypy（140 个 source files）与锁文件检查
  均通过。

### 下一步

- 在不扩大 Server Manager / 外部配置范围的前提下，设计最小 MCP Server 生命周期所有者：
  明确谁启动、持有、关闭 Client，并使当前测试导入路径成为可复用的受控组合；仍不实现
  legacy fallback、分页或真实第三方 Server。

## 2026-08-12 阶段 8 MCP 到 Agent Loop 冒烟工作记录

### 完成

- 新增 `tests/integration/test_mcp_agent_loop.py`，覆盖测试 MCP Server 的 `add` 工具经
  `McpClient`、`McpTool`、`ToolRegistry`、`ToolSnapshot`、`AgentLoop` 与 `ToolExecutor`
  回到下一轮模型上下文的完整链路。
- 脚本化 Fake Model Provider 在第一个请求中看见 Provider 可见工具定义并选择调用；执行路径
  仍要求 `mcp.execute` 权限与明确同意的审批 Policy，随后把配对 TOOL 结果 `"5"` 交给第二轮
  模型请求。Fake Model 只固定模型决策，不替代实际的 stdio MCP Client/Server 通信。
- 当前应用组合根不会自动发现、启动或授权 MCP Server；本测试只确认现有统一工具边界能够承载
  已受控导入的 MCP 工具。

### 验证

- `tests/integration/test_mcp_agent_loop.py` 通过；完整 `scripts/check.sh` 为 287 passed。
- Ruff、strict mypy（141 个 source files）与锁文件检查均通过。

### 下一步

- 设计最小 MCP Server 生命周期所有者，明确 Client 的启动、持有、关闭与受控导入位置；不在
  该任务接入外部配置、legacy fallback、分页、真实第三方 Server 或桌面设置页。

## 2026-08-12 阶段 8 最小 MCP Server Session 工作记录

### 完成

- 在 `src/asagent/tools/mcp.py` 的 `McpClient` 之后增加 `McpServerSession`：持有一个 Client、
  目标 Registry 和宿主 `server_name`，`start()` 完成 discover 与一次性 `register_mcp_tools`。
- Session 禁止重复启动；启动失败会关闭 Client 并将自身标为已关闭；`aclose()` 幂等关闭子进程。
- 当前仍不是 Server Manager：不读外部配置、不管理多个 Server、不自动接入应用组合根。

### 验证

- `tests/integration/test_mcp_server_session.py` 通过：正常路径导入 `mcp:test-server:add:`
  后关闭 Client；启动失败（对端立即退出）同样关闭 Client 并拒绝再次 `start()`。
- 完整 `scripts/check.sh` 为 289 passed；Ruff、strict mypy（142 个 source files）与锁文件检查
  均通过。

### 下一步

- 从已校验的可选 `mcp.json` 创建并持有多个 `McpServerSession`，使组合根可按配置受控启动、
  导入与关闭 Server；仍不实现 legacy fallback、分页或真实第三方 Server。

## 2026-08-12 阶段 8 MCP 非敏感配置工作记录

### 完成

- 新增 `tools.mcp_config`，作为 `config_dir/mcp.json` 的唯一当前加载边界；文件缺失返回空的
  `McpServerConfigs`，且不创建配置目录或启动子进程。
- 每个配置项只包含小写稳定名称、非空 command 参数元组与绝对 working directory；严格拒绝
  未知字段、相对目录、空参数与不合法名称。
- 配置不接受 Token、API Key、密码或环境变量值；加载器也不检查目录存在性、不读取环境变量或
  Secret。未来由组合根和 Secret Store 在独立边界决定实际启动和注入。

### 验证

- `tests/unit/test_mcp_config.py` 覆盖正常加载、缺失文件为空、无效名称/命令/目录/敏感字段拒绝及
  无效 JSON 错误。
- 完整 `scripts/check.sh` 为 296 passed；Ruff、strict mypy（144 个 source files）与锁文件检查
  均通过。

### 下一步

- 实现最小多 Server 生命周期所有者：从已校验 `McpServerConfigs` 创建、启动和关闭多个
  `McpServerSession`；不在该任务接入 CLI、Local API、Electron、legacy fallback、分页或真实
  第三方 Server。

## 2026-08-12 阶段 8 McpClient 工作目录工作记录

### 完成

- `McpClient` 增加可选绝对 `working_directory`，启动 stdio 子进程时作为 `cwd`；相对路径在
  构造时拒绝。未提供时行为与此前相同（沿用宿主当前目录）。

### 验证

- `tests/integration/test_mcp_client.py` 与 `test_mcp_server_session.py` 在默认不传 cwd 时仍通过。
- 定向 Ruff 与 `mypy src/asagent/tools/mcp.py` 通过。

### 下一步

- 从已校验的配置在应用组合根构造 Manager，使用户显式配置的 MCP Server 可进入实际 Runtime；
  仍不实现 Secret 注入、legacy fallback、分页、热刷新或真实第三方 Server 验收。

## 2026-08-12 阶段 8 最小 MCP Server Manager 工作记录

### 完成

- 新增 `tools.mcp_manager.McpServerManager`，从注入的 `McpServerConfigs` 创建多个
  `McpServerSession`，并把每项绝对工作目录传入 `McpClient` 作为 stdio 子进程 cwd。
- Manager 先使用临时 `ToolRegistry` 导入全部远程工具；仅所有 Session 启动成功且无正式工具 ID
  冲突后才合并到正式 Registry。任一 Server 失败时关闭已启动 Session，正式 Registry 不留下
  已关闭 Client 的工具。
- `aclose()` 以反向创建顺序关闭全部 Session 并拒绝再次启动。当前 Manager 不读配置文件、不处理
  Secret、热刷新、重连、分页或 legacy fallback，也尚未被 CLI/API/Electron 自动构造。

### 验证

- `tests/integration/test_mcp_server_manager.py` 覆盖单 Server 成功导入与“首个 Server 成功、
  后续 Server 退出”时的清理及正式 Registry 无残留。
- 完整 `scripts/check.sh` 为 298 passed；Ruff、strict mypy（146 个 source files）与锁文件检查
  均通过。

### 下一步

- 将可选 `mcp.json` 和 `McpServerManager` 接入一个明确的应用组合根，使配置的 Server 可供实际
  Runtime 使用；不在该任务接入 Secret、legacy fallback、分页、热刷新、桌面设置页或真实第三方
  Server。

## 2026-08-12 阶段 8 桌面逐次工具审批工作记录

### 完成

- 新增不可变 `ToolApprovalRequest` 与内存 `PendingToolApprovalPolicy`。工具调用会在 schema、权限
  检查通过后登记请求，随后才发布不含参数正文的 `tool.approval_requested` 事件并等待一次决定。
- Local API 新增认证的待处理审批读取与决定端点；取消 Run 和关闭 Sidecar 会拒绝未完成审批，避免
  后台 Run 永久等待。
- Electron Main 继续独占本地 Token：它从 SSE 得到审批事件后读取详情，经 Preload 的具名 IPC 交给
  Renderer；Renderer 在对话流中显示英文审批卡，展示工具、说明和参数，并提供 `Allow once` / `Deny`。
- 此任务不自动加载 `mcp.json`、不启动 MCP Server，也不授予 `mcp.execute`；因此它建立确认通道，
  而不扩大任何实际工具能力。

### 验证

- `tests/unit/test_tool_approval.py` 覆盖请求先登记后通知、Run 取消与关闭拒绝等待；
  `tests/integration/test_api_tool_approvals.py` 覆盖本地 API 读取和一次性决定。
- `scripts/check.sh` 为 301 passed；Ruff、strict mypy（148 个 source files）与锁文件检查均通过。
- Desktop 执行 `npm run format`、`npm run typecheck`、`npm run lint`、`npm test`（7 tests）和
  `npm run build` 均通过。

### 下一步

- 将可选 `mcp.json` 与 `McpServerManager` 接入桌面 Sidecar 的明确组合根：成功启动后才把其 Tool
  导入 Runtime，并仅向该 Runtime 授予 `mcp.execute`；使用上述审批卡进行首次真实 MCP 人工验收。

## 2026-08-12 阶段 8 MCP Sidecar Runtime 接入工作记录

### 完成

- `asagent serve` 现在读取可选 `config_dir/mcp.json`，在创建 Runtime 前启动 `McpServerManager`，并将同一份“内置工具 + 成功导入的 MCP 工具”Registry 交给 Tool Snapshot 与 Executor。
- 缺失配置保持原来的仅内置工具行为；非空配置只有在全部 Server 成功启动后才向该 Runtime 授予 `mcp.execute`。任一配置、发现或导入失败会阻止 Sidecar 宣布 ready，Manager 的已有原子导入和清理语义保持生效。
- MCP 子进程不再隐式继承宿主环境：`McpClient` 默认使用空环境，Sidecar 只传递 `PATH`，因此模型 API Key、Local API Token 与开发 `.env` 值不会进入 MCP Server。
- 新增集成测试覆盖：缺少 `mcp.json` 时仅保留内置工具；配置测试 Server 后，远程 `add` Tool 经真实 Manager、持久化 Runtime、ToolExecutor 权限与批准 Gate 完成一次模型工具回合；测试还验证父进程 Secret 不会传入 MCP 子进程。

### 验证

- 定向 MCP 集成测试通过：7 passed。
- `scripts/check.sh` 通过：304 passed；Ruff、strict mypy（149 个 source files）与锁文件检查均通过。

### 决策变化

- 新增 DEC-067：Sidecar 以最小环境原子导入配置的 MCP Server。

### 风险或问题

- 当前仅支持现代 stdio MCP；不包含 Server 凭据注入、热刷新、重连、分页、legacy fallback 或桌面设置页。

### 下一步

- 使用桌面真实 Provider 模式和一个显式 `mcp.json` 完成首次人工 MCP 验收：模型请求 MCP Tool，桌面审批卡 Allow/Deny 后验证结果与 RunEvent；不在该任务扩展配置 UI 或 Secret Store。

## 2026-08-12 会话内按 tool_id 授权工作记录

### 完成

- 审批决定由布尔值改为 `deny` / `allow_once` / `allow_conversation`。`PendingToolApprovalPolicy`
  以内存 `(conversation_id, definition.tool_id)` grants 记住本会话对某一内部工具的授权；
  `allow_once` 不记 grant，`deny` 不产生授权，Sidecar `aclose()` 清空 grants 且不写 SQLite。
- Local API 的决定请求/响应使用字符串 `decision`；Electron Main / Preload / Renderer 传递同一
  三种值。桌面横幅提供 `Deny`、次级 `Allow for this conversation` 和主按钮 `Allow once`。

### 验证

- `tests/unit/test_tool_approval.py` 覆盖一次性仍弹窗、会话授权跳过同工具、新会话/不同工具仍弹窗、
  Deny 不授权、关闭后 grants 消失；`tests/integration/test_api_tool_approvals.py` 覆盖三种
  字符串 decision 的本地 API 边界。
- Desktop 测试覆盖 Main 向 API 发送三种字符串 decision，以及 Renderer 三个按钮到 API 决定的映射。
- Python `scripts/check.sh` 通过：310 passed；Ruff、strict mypy（149 个 source files）与锁文件检查均通过。
- Desktop 执行 `npm run format`、`npm run typecheck`、`npm run lint`、`npm test`（12 tests）和
  `npm run build` 均通过。
- 手动 MCP 验收通过：同一会话对同一工具的会话授权不再弹窗；Allow once、Deny、换会话、换工具和
  重启 Sidecar 都保持各自预期边界。

### 决策变化

- 新增 DEC-068：工具审批按会话与内部 tool_id 授权，而不是全局布尔值。

### 下一步

- 设计 Gmail 的最小只读 MCP 接入：先定义 Desktop OAuth、系统 Secret Store、账户/Scope 资源范围和
  Email 专用工作区的授权边界；不把 Token 写入 `mcp.json`，不先实现发送或删除邮件。

## 2026-08-12 通用外部连接与 macOS Keychain 基础工作记录

### 完成

- 新增 Core `Connection` / `ConnectionStatus`、`ConnectionRepository` 与 `CredentialStore`：SQLite
  只保存连接 ID、用户、服务标识、账户显示名、scope、状态和时间；credential 是仅由
  `connection_id` 引用的不透明字符串，不进入数据库或普通配置。
- 新增 `connections` Schema 与 Alembic `20260812_03` 迁移；`SqliteConnectionRepository` 支持
  查询、按用户列出、upsert 和删除非敏感连接元数据。
- 新增 `MacOSKeychainCredentialStore`，通过 `keyring` 访问当前 macOS 用户的 Keychain。它按
  Connection ID 隔离 credential，空 credential 与非 macOS 平台明确拒绝；尚未实现 Windows 和
  Linux 的系统存储适配器。
- 本次不实现 OAuth、token 刷新、MCP credential 注入、Connection API、设置页或 Gmail 专用 UI。

### 验证

- 定向单元与 SQLite 集成测试覆盖 Keychain 适配器的 save/get/delete、跨连接隔离、空值/非 macOS
  拒绝、迁移、跨实例持久化、更新排序、UTC 标准化和删除语义。
- `scripts/check.sh` 通过：316 passed；Ruff、strict mypy（154 个 source files）与锁文件检查均通过。

### 决策变化

- 新增 DEC-070：外部连接元数据与系统凭据存储分离。

### 下一步

- 设计并实现最小 MCP connection reference：非敏感配置只引用 `connection_id`，组合根只向目标
  Server 提供所需 credential；不接入 Gmail OAuth、不向所有 MCP 子进程广播 Secret，也不开始
  Windows/Linux 适配器。

## 2026-08-12 阶段 8 MCP Connection 定向凭据注入工作记录

### 完成

- `config_dir/mcp.json` 的单个 Server 现在可成对声明非敏感的 `connection_id` 与
  `credential_environment_variable`。前者引用系统 CredentialStore，后者只表示该 Server 子进程
  接收 credential 的变量名；严格配置继续拒绝 token、API Key、密码和环境变量值，也拒绝只提供其中
  一个字段或不合法变量名。
- Sidecar 仅在配置实际引用 Connection 时构造 macOS Keychain Store。`McpServerManager` 为每个
  Server 从最小基础环境复制独立 Mapping，只读取其引用的 credential，并只注入该 Server 声明的变量；
  未引用 Connection 的 Server 仍只得到显式允许的 `PATH`。
- 缺少 Store、缺少 Keychain credential 或后续 Session 启动失败时，Manager 保持既有原子启动语义：
  清理已启动子进程，正式 ToolRegistry 不导入任何远程工具，且异常文本不包含 Secret。

### 验证

- 配置单元测试覆盖成对引用、字段缺失和不合法变量名；Manager 集成测试覆盖目标 Server 收到假
  credential、并行的未引用 Server 明确收不到它，以及缺少 credential 时拒绝启动。
- Sidecar Runtime 集成测试覆盖配置引用经过组合根、Manager、真实测试 stdio Server、ToolRegistry 与
  Persistent Runtime 的完整工具回合，同时保留父进程 Secret 不继承断言。
- `scripts/check.sh` 通过：321 passed；Ruff、strict mypy（154 个 source files）与锁文件检查均通过。

### 决策变化

- 新增 DEC-071：MCP Connection credential 按配置 Server 定向注入，而非作为 Sidecar 或 Manager 的
  全局环境。

### 风险或问题

- 当前交付机制仅为 stdio 子进程环境变量，并且只有 macOS Keychain 可用；Windows/Linux、OAuth、
  refresh、Connection API/设置页和 Gmail 专用 UI 尚未实现。
- 当前尚不读取 Connection Repository 以校验归属、服务类型或 `reauthentication_required` 状态；这些
  与 OAuth 连接生命周期一起作为后续独立任务设计，不能在本次用配置推断账户授权。

### 下一步

- 在用户确认后，选择一个真实但受限的 MCP 连接体验路径：优先设计 Gmail 的 OAuth 登录、Connection
  元数据创建/状态和最小只读账户范围；不开始发信、删除、刷新自动化或通用设置页。

## 2026-08-12 Gmail 本地 OAuth 设计决策

### 完成

- 确认第一个真实外部账户体验为 Gmail 的本地开发 OAuth 连接，而不是先为 Gmail 编写 MCP Tool。
- 确认授权链路为：Electron Main 请求 Sidecar 开始授权并用系统浏览器打开 URL；Sidecar 在内存生成
  PKCE verifier、state 与随机 loopback 端口，接收一次 callback、验证 state、交换授权码，然后保存
  Connection 元数据与 Keychain credential。Renderer 不获得授权 URL 以外的 OAuth 参数、Token 或回调正文。
- 首版仅使用 Google OAuth Desktop client、External Testing 的显式 Test user 和
  `gmail.readonly`；它是 restricted scope，Testing 授权会过期，因此当前只作为个人本地开发验收。

### 决策变化

- 新增 DEC-072：Gmail 使用系统浏览器、Authorization Code + PKCE 和一次性 `127.0.0.1` loopback
  callback；不采用嵌入式浏览器、复制授权码或文件化 token。

### 风险或问题

- 真实授权前仍需用户在 Google Cloud 创建独立测试项目、启用 Gmail API、配置 consent screen、创建
  Desktop OAuth client，并把自己的账号加入 Test users；这些均未在仓库或代码中保存。
- `gmail.readonly` 为 restricted scope；Testing 的短期授权适合本地体验，但公开发布、长期运行与
  Google 验证/合规要求必须在后续产品发布阶段单独处理。

### 下一步

- 实现离线可测的 Gmail OAuth Foundation：严格验证非敏感 Desktop client 配置，生成 PKCE/state/
  authorization URL，并定义一次性 loopback callback 与脱敏失败结果；不在该任务执行真实浏览器授权、
  token 交换、Connection 写入、Keychain 写入或 Gmail MCP Tool。

## 2026-08-12 Gmail 首版入口范围决策

### 完成

- 确认 Gmail 首版继续沿用阶段 8 的 MCP 主线：OAuth 连接完成后，credential 仅定向提供给受控 Gmail
  MCP Server，其工具进入既有 ToolRegistry、权限、会话审批和审计链路。
- 原生 Email workspace、直接 Gmail API Gateway、邮件专用 Local API 与 Playwright 网页自动化均不在
  当前范围。现有 Connection、CredentialStore 和定向环境注入已足以为未来原生界面预留账户与凭据边界，
  无需提前增加空接口。

### 决策变化

- 新增 DEC-073：先验证 Gmail MCP 的真实使用价值；未来原生邮箱页若实现，复用同一 OAuth/Connection/
  Keychain 生命周期，不建立第二套 token 或账户主数据。

### 下一步

- 实现离线可测的 Gmail OAuth Foundation：严格验证非敏感 Desktop client 配置，生成 PKCE/state/
  authorization URL，并定义一次性 loopback callback 与脱敏失败结果；不在该任务执行真实浏览器授权、
  token 交换、Connection 写入、Keychain 写入或 Gmail MCP Tool。

## 2026-08-12 Gmail OAuth Foundation 与功能后置记录

### 完成

- 新增离线 `bootstrap.gmail_oauth`：仅接受非敏感 Google Desktop client ID，生成 PKCE S256
  verifier/challenge、随机 state、固定的 `gmail.readonly` scope 和受限 `127.0.0.1` callback URL。
- 一次性授权 Session 只在内存保留 verifier/state；它只接受单值、匹配 state 的 callback code，明确区分
  用户拒绝、无效 query、状态不匹配和重复消费，且错误不回显授权码、state 或 Google 错误详情。
- 本任务没有网络、浏览器、loopback listener、token exchange、Connection/SQLite 写入、Keychain 写入或
  Gmail MCP Tool；因此可离线稳定测试而不要求 Google Cloud 项目或真实账户。

### 验证

- 单元测试覆盖 PKCE URL 参数、一次性成功回调、state 不匹配、用户拒绝、无效 client/redirect 配置和无效端口。
- `scripts/check.sh` 通过：331 passed；Ruff、strict mypy（156 个 source files）与锁文件检查均通过。

### 决策变化

- DEC-072 更新为“Foundation 已完成，真实授权后置”；DEC-073 更新为 Gmail MCP 也暂不继续，等待产品完善阶段的
  真实需求恢复。

### 后置范围

- 暂停 Gmail 的真实 Google Cloud 配置、系统浏览器授权、loopback listener、token exchange、Connection/
  Keychain 持久化、refresh、Gmail MCP Server 和原生 Email workspace。
- Foundation、通用 Connection、Keychain 与 MCP 定向 credential 注入均保留；恢复时从真实 OAuth callback +
  token exchange 的独立任务继续，不必重做已验证的安全边界。

### 下一步

- 回到阶段 8 通用 MCP 主线，选择不依赖外部账户、收益更高的剩余协议能力；优先评估 modern-first 的
  legacy stdio fallback、`tools/list` 分页/`listChanged`，或按实际需要明确结束阶段 8 后进入 Skills。

## 2026-08-12 阶段 8 MCP legacy stdio fallback 工作记录

### 完成

- `McpClient.start()` 现在先在受限 stdio 子进程中尝试现代 `server/discover`；探测收到 MCP
  Client 错误时，关闭该进程后重新启动全新子进程，以 `2025-11-25` 的 `initialize` 和
  `notifications/initialized` 完成 legacy 生命周期。
- 旧版会话的后续 `tools/list` 与 `tools/call` 不携带现代 `_meta`；现代和旧版响应继续映射为同一
  `McpServerInfo`、`McpToolDescription` 与 `McpToolCallResult`，因此 ToolRegistry、Executor、
  审批和 Agent Loop 均不需要协议分支。
- 新增专用 legacy stdio 测试 Server：它在收到现代 `server/discover` 后返回方法不存在并立即退出；
  重启后的进程要求完成 `initialize` 和 initialized 通知，才允许列举或调用 `add`。这证明 fallback
  没有复用已被现代探测影响的连接。

### 验证

- `tests/integration/test_mcp_client.py` 通过：3 passed，覆盖现代发现/列举/调用、远端工具错误，以及
  legacy fallback 后的 `20 + 22 = 42`。
- `scripts/check.sh` 通过：332 passed；Ruff、strict mypy（157 个 source files）与锁文件检查均通过。

### 下一步

- 先定义一个不依赖第三方账户的最小 `web_search` MCP 体验范围：明确搜索提供方、网络/域名限制、
  结果正文上限、缓存与审批策略；确定后才实现 Server 配置、工具和桌面人工验收。该任务不自动扩展到
  `tools/list` 分页、`listChanged`、Streamable HTTP 或 Gmail。

## 2026-08-12 外部 Web Search 接入策略

### 决策

- 确认外部搜索优先采用用户配置的 MCP Server，而非当前阶段直接调用某个模型厂商的 managed search 或
  在 asAgent Core 内置多搜索 API 路由。
- 用户决定搜索 Server、凭据和网络能力；模型只经既有 MCP 工具、权限、审批、超时和审计链路请求搜索。
  没有配置 Server 时，模型没有联网搜索能力。

### 下一步

- 以 Tavily 官方本地 stdio MCP Server 完成首次真实 Web Search 人工验收：用户在 Tavily 创建 API key，
  Keychain 以 Connection 保存凭据，并仅向该 Server 的 `TAVILY_API_KEY` 定向注入。首轮只启用基础
  `tavily_search`，确认每次审批、结果大小与免费额度体验；不启用 advanced search、extract、map、crawl、
  research 或远程 HTTP Transport。

## 2026-08-12 阶段 8 MCP 工具白名单工作记录

### 完成

- `mcp.json` 的单个 Server 现可选 `allowed_tools`；省略时保持既有的全量导入行为，空列表、重复项或
  空名称在严格配置校验时拒绝。
- `McpServerSession` 将白名单传给工具导入；只将明确列出的远程工具注册到临时 Registry。若 Server 未
  暴露任一所列名称，启动失败、已有 Session 关闭且正式 Registry 保持无残留。
- 测试 stdio Server 以可选 `multiply` 工具验证筛选路径，默认仍只暴露 `add`，不改变既有 MCP 验收语义。

### 验证

- `tests/unit/test_mcp_config.py` 与 `tests/integration/test_mcp_server_manager.py` 共 22 passed，覆盖省略
  白名单的全量导入、合法筛选、非法配置与未知远程工具的原子失败。
- `scripts/check.sh` 通过：339 passed；Ruff、strict mypy（157 个 source files）与锁文件检查均通过。

### 下一步

- 实现 Tavily 的最小安全配置后端：在 macOS Keychain 保存 API key、在 SQLite 保存非敏感 Connection
  元数据、在 `mcp.json` 写入不含 Key 的 Tavily Server 引用和 `allowed_tools`；不在本项制作 Settings UI
  或热重启 Sidecar。

## 2026-08-12 阶段 8 Tavily 安全配置后端工作记录

### 完成

- 新增 `save_mcp_server_configs()`：显式保存时原子替换 `config_dir/mcp.json`，并保留同一配置中的其他
  Server；文件只序列化严格校验过的非敏感 `McpServerConfigs`。
- 新增 `bootstrap.tavily_settings.TavilySettings`，统一协调 `connection-tavily` 的 macOS Keychain API key、
  SQLite `Connection` 元数据和 Tavily MCP 配置。启用时只写入 `tavily_search` 白名单；禁用保留 key 与
  Connection；删除才清理三处状态。
- Local API 在注入该对象时提供经 Bearer 认证的 Tavily 状态、保存/启用、禁用和删除端点。任何响应只含
  `enabled`、`api_key_saved` 或标准错误，不返回 API key。
- `asagent serve` 创建 SQLite Connection Repository、macOS Keychain Store 与 Tavily Settings，并在关闭时
  关闭 Connection Repository。配置变更不热重启或修改当前 Runtime，重启 Sidecar 后才被 MCP 组合根读取。

### 验证

- `tests/integration/test_api_tavily_settings.py` 为 9 passed，覆盖初始状态、保存后的三层持久化、无 key
  重启用的 409、禁用保留、完全删除、其他 Server 保留、严格请求体和 API key 不泄露。
- `scripts/check.sh` 通过：348 passed；Ruff、strict mypy（159 个 source files）与锁文件检查均通过。

### 下一步

- 在 Electron Settings 页面加入 Tavily 开关、临时密码输入、保存/禁用/删除状态和“Restart asAgent to apply
  this change”提示；Renderer 只能通过窄 Preload/Main IPC 调用上述 API，不能获取、缓存或打印 API key。

## 2026-08-12 阶段 8 Tavily Electron Settings 工作记录

### 完成

- Electron Preferences 的 Tavily Web Search 卡片已接入现有 BackendLauncher、受来源校验的 Main IPC 与窄
  Preload API；Renderer 不获得 Local API Token、端口、HTTP 能力或已保存 key。
- 开关关闭调用 disable 并保留 key；存在 key 时可直接重新启用，首次配置或 Replace 时才显示临时 password
  input；保存成功或失败后均清空该输入 state。Remove 有英文确认，并执行完整删除。
- 状态加载或写入失败只显示固定英文消息；写入成功后明确提示 `Restart asAgent to apply this change.`，不在
  当前 Sidecar 内热重启或热加载 MCP。

### 验证

- Desktop 执行 `npm run format`、`npm run typecheck`、`npm run lint`、`npm test`（16 passed）及
  `npm run build` 均通过。
- Python `scripts/check.sh` 通过：348 passed；Ruff、strict mypy（159 个 source files）与锁文件检查均通过。
- 手动体验已验证：Preferences 可保存 Tavily key，重启后 Sidecar 能读取 Tavily 配置并完成启动。

## 2026-08-12 阶段 8 Tavily 真实搜索兼容性与人工验收

### 完成

- `McpClient` 现在将 `tools/call` 成功结果中省略的可选 `isError` 解释为 `False`；显式非布尔值继续按
  `McpProtocolError` 拒绝，避免静默接受损坏协议数据。
- 受控 MCP 测试 Server 新增“省略 `isError`”和“无效 `isError`”模式；集成测试分别验证成功兼容与严格拒绝。
- 真实桌面验收已完成：用户在 Preferences 保存 Tavily API key、重启 Sidecar、批准 `tavily_search` 后，Agent
  成功获取并回答 Perth 的实时天气。该路径验证了 Settings、Keychain、定向子进程环境、白名单、审批、
  MCP Tool、Agent Loop 与模型回答的完整闭环。

### 验证

- `scripts/check.sh` 通过：350 passed；Ruff、strict mypy（159 个 source files）与锁文件检查均通过。

### 下一步

- Tavily 最小 Web Search 已完成。后续 MCP 工作按真实需求选择，例如 `tools/list` 分页/`listChanged`、
  Streamable HTTP，或其他用户显式配置的 Server；不因已有 Tavily 闭环自动扩展更多搜索工具。

## 2026-08-12 桌面外部链接、紧凑活动视图与模型设置

### 完成

- Assistant Markdown 中的安全 `http`/`https` 外部链接可经来源校验的 Main IPC 在系统默认浏览器打开；Renderer
  不获得 shell、任意 URL 导航或 Token。
- 当前 Run 的活动信息改为紧凑的进行中状态和可展开完成摘要，隐藏原始内部事件名称；它仍是本次 Renderer 会话的
  临时视图。RunEvent 已按 sequence 持久化，重启后的历史摘要将在后续独立任务中从事件回放重建，而不重复存储摘要。
- Preferences 现以分隔线组织 Model provider 与 Tavily Web Search。用户可保存一个 OpenAI-compatible model、
  base URL 和 API key；配置与 key 分别进入 `providers.toml` 和系统 CredentialStore，重启后自动使用该模型。
  Anthropic/Gemini 仅保留英文占位，尚未实现。
- 保存模型或 Tavily 设置后，Preferences 显示统一的 `Restart now` / `Later` 提示；前者由 Electron Main
  在发布版自动 relaunch 并安全停止自己持有的 Sidecar；开发版仅重启 Sidecar 后刷新 Renderer，避免空白窗口。
  用户不必手动退出并重新打开。

### 验证

- Python 定向设置测试通过：13 passed。
- `scripts/check.sh` 通过：355 passed；Ruff、strict mypy（163 个 source files）与锁文件检查均通过。
- Desktop `npm run format`、`npm run typecheck`、`npm run lint`、`npm test`（24 passed）和 `npm run build` 均通过。

### 下一步

- 在单独的桌面体验任务中，从已持久化的 RunEvent 回放重建历史 Run 的折叠活动摘要；不新增摘要表，也不保存模型或工具正文。

## 2026-08-12 本地文件/文件夹范围授权工作记录

### 完成

- 新增会话级 `ConversationWorkspaceSettings` 与 SQLite `conversation_file_scopes`，分别保存每个 Conversation 在默认 Workspace 之外的额外允许根和单文件允许项。
  保存时文件夹或文件必须存在，路径会解析符号链接并去重；文件夹递归覆盖其内容，单文件不会自动扩大为父目录权限。不同 Conversation 互相隔离，旧的全局范围不会被静默扩大到所有 Conversation。
- Sidecar 现在确保默认 Workspace 目录存在，并提供 Bearer 认证、归属校验的 `GET` / `PUT /api/v1/conversations/{conversation_id}/file-access`。
  API 只返回当前 Conversation 的默认根、额外根和单文件允许项；它不读取、扫描或上传用户文件。
- Electron Preferences 和 Chat Composer 的 `+` 共用当前 Conversation 的 Local file access 操作。Renderer 请求 Main 打开原生文件/目录选择器，
  再通过窄 Preload/Main IPC 保存或移除当前 Conversation 的完整路径列表；它不能取得 Node、任意文件读取、Token 或通用 HTTP 能力。
- 当前设置仅建立持久、可撤销的未来访问范围；文件工具仍未注册到实际 Runtime，且没有写入、删除、Shell 或模型文件访问能力。

### 验证

- `tests/unit/test_workspace_settings.py`、`tests/unit/test_workspace_resolver.py`、SQLite Schema 与扩展后的设置 API 集成测试覆盖规范化、Conversation 隔离、单文件精确范围、缺失/错误类型路径、API 保存/移除、归属校验和无效路径/未知字段拒绝。
- `scripts/check.sh` 通过：361 passed；Ruff、strict mypy（167 个 source files）与锁文件检查均通过。
- Desktop `npm run format`、`npm run typecheck`、`npm run lint`、`npm test`（25 passed）和 `npm run build` 均通过。

### 决策变化

- 更新 DEC-075：已选择文件或文件夹作为会话级、可撤销的未来文件范围。

### 下一步

- 在独立任务中设计并实现 DEC-060 的 `FileChange`、私有快照、哈希冲突检测和撤回基础；在此之前不实现覆盖、
  追加、删除或编辑既有文件。

## 2026-08-12 会话级只读文件工具 Runtime 接入

### 完成

- 持久化 Runtime 现在会在每个 Run 从其 `conversation_id` 读取 SQLite `conversation_file_scopes`，构造专属
  `WorkspaceResolver`，并为该 Run 复制基础 ToolRegistry、注册 `filesystem.list` 与 `filesystem.read_file`。
  这样共享的内置/MCP Tool 不会携带某一 Conversation 的文件范围，Run Tool Snapshot 也保持稳定。
- 两个 Tool 获得 `filesystem.read` 能力，但只能在当前 Conversation 的默认 Workspace、明确授权文件夹或精确授权
  单文件内执行。越界请求不会访问磁盘，而是返回配对的工具错误；文件选择本身仍不上传、扫描或读取内容。
- 持久化开发 CLI、真实 Provider Runtime 与 Electron Sidecar 均使用该按 Run 构造的只读工具路径。非持久化 CLI
  仍不提供外部文件范围。

### 验证

- 新增集成测试验证：Conversation A 能读取其明确授权的 Workspace 外文件；Conversation B 即使请求同一路径也会
  获得工具错误，且两个 Run 的模型 Snapshot 均包含只读 File Tool。
- 定向测试通过：14 passed；完整 `scripts/check.sh` 通过：363 passed；Ruff、strict mypy（168 个 source files）与锁文件检查均通过。

### 下一步

- 让模型在当前 Run 的系统上下文中获知当前 Conversation 已选择的文件/目录路径，避免用户必须复述绝对路径；之后再实现 DEC-060 的 `FileChange`、私有快照、哈希冲突检测和撤回基础。

## 2026-08-12 会话级文件范围的模型可发现性

### 完成

- 每个持久化 Run 现在把当前 Conversation 明确选择的文件夹和单文件路径附加到短暂系统上下文。模型因此可将“附加的文件夹”或“共享的文件”等自然语言指代映射为正确的受控工具路径，而不要求用户输入绝对路径。
- 该上下文只包含用户已经在 Composer/Preferences 中显式选择的路径，不读取、扫描或上传文件正文；不写入用户可见 Message、SQLite、RunEvent 或 ToolCall。文件正文仍必须通过 `filesystem.list` 或 `filesystem.read_file` 的 Resolver、权限、超时和审计链路取得。

### 验证

- 新增集成断言：当前 Conversation 的模型请求包含其已选文件夹与文件路径；另一 Conversation 的请求不包含这些路径，且越界读取继续只返回配对工具错误。

### 下一步

- 在独立任务中设计 `search_files`：仅搜索当前 Conversation 已授权文件夹，限制匹配数、单文件大小、总输出和超时；它不替代已完成的文件范围可发现性。

## 2026-08-12 会话级文件搜索工具

### 完成

- 新增只读 `filesystem.search_files`，使模型能够在当前 Conversation 已授权目录中递归查找未知位置的文件，而不必猜测精确文件名。
- 搜索按大小写不敏感的字面查询匹配文件名与 UTF-8 文本；可指定单个已授权目录，省略路径时仅搜索当前 Conversation 可访问的 Workspace 根。
- 工具不使用正则、不建立索引、不后台扫描，也不返回完整文件正文。它最多扫描 1,000 个文件、每个文件最多读取 64 KiB、最多返回 20 项含相对路径和短片段的匹配；二进制、不可读、超限文件与符号链接都会跳过，截断会明确告知模型。
- 持久化 Runtime 的 Conversation 专属 Registry 现注册 `filesystem.list`、`filesystem.read_file` 与 `filesystem.search_files`。因此 Tool Snapshot、权限、超时、审计和文件范围仍严格绑定当前 Run 的 Conversation，不会扩大到其他会话或整台电脑。

### 验证

- 定向测试覆盖文件名/内容递归匹配、稳定结果上限、二进制/超限/符号链接跳过、无效参数和目录范围拒绝，并扩展 Runtime 集成测试确认新工具进入当前 Conversation 的模型 Snapshot。
- 完整 `scripts/check.sh` 通过：375 passed；Ruff、strict mypy（170 个 source files）与锁文件检查均通过。Electron 人工验收也已确认模型可调用 Search files 并读取命中结果。

### 决策变化

- 无；本次落实既有 DEC-039 和 DEC-075 的会话级只读文件范围，没有引入新的权限、写入能力或持久化索引。

### 下一步

- 根据真实需求决定是否进入 DEC-060 的 FileChange/撤回基础；本次不开始写入或编辑能力。

## 2026-08-12 Desktop Composer visual refinement

### Complete

- Chat Composer now uses a larger rounded input surface with a separate lower control row, a `+` control for selecting
  a local file or folder for the active Conversation, and a circular upward-arrow send action. The existing submit and
  cooperative Stop behavior are unchanged.
- The `+` control persists only an authorization scope. It does not upload, read, scan, or expose file content to the
  model; actual file-tool consumption remains a later task.

### Verification

- Desktop `npm run format`, `npm run typecheck`, `npm run lint`, `npm test` (25 passed), and `npm run build` all pass.

## 2026-08-15 DEC-060 FileChange Core contract

### 完成

- 新增 `FileChangeId`、`FileChangeOperation`（CREATE、REPLACE、DELETE）和 `FileChangeStatus`（PREPARED、APPLIED、REVERTED、CONFLICTED）。
- 新增不可变 Core `FileChange`，记录来源 Run、规范化根路径和相对路径、前后哈希、可选快照引用及创建/更新时间；按操作种类拒绝不完整或矛盾的哈希和快照元数据。
- 新增异步 `FileChangeRepository` Protocol，提供按稳定身份读取、按 Run 列出和保存，为后续 SQLite 持久化及撤回流程保留 Core 边界。
- 未新增 SQLite 表或迁移、快照正文、真实文件写入、审批 UI 或撤回执行。

### 验证

- 定向 `pytest`、Ruff、格式检查和 strict mypy 通过：13 passed。
- `scripts/check.sh` 通过：388 passed；Ruff、格式检查、strict mypy（172 个 source files）与锁文件检查均通过。

### 决策变化

- 无；本次实施既有 DEC-060 的第一层 Core 合同，不改变其快照、冲突检测或撤回安全决策。

### 下一步

- 在独立任务中为 `FileChangeRepository` 添加 SQLite 表与迁移，并实现私有快照存储的容量、保留期和隐私边界；在其完成前，继续禁止覆盖、追加、删除和回滚执行。

## 2026-08-15 DEC-060 FileChange SQLite persistence

### 完成

- 新增 `file_changes` SQLite 表和 Alembic 迁移，约束来源 Run、操作种类和生命周期状态。
- 新增 `SqliteFileChangeRepository`，支持覆盖保存、按稳定身份读取和按 Run 的稳定排序查询。
- 未实现快照正文、文件写入、哈希计算、冲突检测或回滚执行。

### 验证

- FileChange Repository 与 schema 定向集成测试：3 passed。
- `scripts/check.sh`：389 passed；Ruff、格式检查、strict mypy（174 个 source files）与锁文件检查均通过。

### 决策变化

- 无；本次落实既有 DEC-060 的元数据持久化边界。

### 下一步

- 在独立任务中实现私有快照存储及其单项 5 MiB、总量 100 MiB、保留期和隐私边界；继续不执行文件覆盖、追加、删除或撤回。

## 2026-08-15 DEC-060 单文件可撤回存储闭环

### 完成

- 新增私有 `FileChangeSnapshotStore`，快照正文只写入 `AppPaths.data_dir/file-changes`，执行相对引用校验、独占保存、单项 5 MiB 与总量 100 MiB 限制。
- 新增单一 `ReversibleFileService`，在已授权范围内支持最大 64 KiB 的 UTF-8 普通文件 CREATE、REPLACE 与 DELETE，并为每次成功操作持久化独立 `APPLIED` FileChange。
- 实现按 `change_id` 的安全撤回：CREATE 仅删除 after hash 未变化的文件，REPLACE 仅在当前内容未变化时原子恢复快照，DELETE 仅在目标仍不存在时独占恢复；不匹配会标记 `CONFLICTED` 且不覆盖用户数据。
- 文件应用或撤回后的普通 Repository 保存失败会补偿恢复磁盘状态；已删除只有单一调用者的 `FileChangePreparationService`，没有为流程保留额外转发层。
- 当前没有把修改或 Undo 注册为 Agent Tool，也没有接入 Local API、Electron UI、批量 `FileChangeSet`、文档提取或 OCR。

### 验证

- `tests/unit/test_reversible_files.py`：13 passed，覆盖三种操作及撤回、三种冲突、应用持久化失败补偿、撤回状态保存失败补偿、范围限制与非 UTF-8 拒绝。
- `scripts/check.sh`：405 passed；Ruff、格式检查、strict mypy（178 个 source files）与锁文件检查均通过。
- `git diff --check` 通过。

### 决策变化

- 补充 DEC-060：单文件闭环从 REPLACE 扩展为 CREATE、REPLACE 与 DELETE；批量修改未来通过 `FileChangeSet` 组合独立变更，文档提取/OCR 和范围扩大保持独立。
- 快照首版不自动按 30 天删除；只有未来明确的用户清理操作才能移除仍可撤回的快照。

### 下一步

- 在独立任务中完成用户可见接入：首次修改复用现有 Approval 横幅并保留 `Allow for this conversation`；成功变更显示带手动 `Undo` 的对话卡片，经窄化的 Backend API 与 Main/Preload IPC 执行，不把 Undo 暴露给模型。

## 2026-08-15 DEC-060 Agent Tool、Local API 与桌面 Undo 闭环

### 完成

- 新增真实 `filesystem.create_file`、`filesystem.replace_file`、`filesystem.delete_file` Agent Tool；每个 Run 获得独立工具实例并把成功变更关联到该 Run。
- 三种写操作要求 `filesystem.write`、高风险审批和 ToolCall 审计；`Allow for this conversation` 继续按各自内部 `tool_id` 隔离。
- 审批 API 隐藏待写入 `content`，只向桌面返回文件路径与英文影响摘要。
- 新增按 Conversation 查询 FileChange 的认证 API，以及携带 `change_id` 和精确路径的手动 Undo API；服务端验证本地用户归属、来源 Run 与记录路径，冲突返回 409 且不覆盖后续文件内容。
- Electron Main/Preload 新增固定查询和 Undo IPC，Renderer 不获得 Token、文件系统或通用 HTTP 能力。
- 对话界面会从持久化 API 加载 CREATE、REPLACE、DELETE 修改卡片；`APPLIED` 卡片显示 `Undo`，成功后显示 `Undone`，冲突显示 `Changed later`，刷新软件后卡片仍存在。
- Undo 只由用户点击触发，没有注册为模型 Tool。

### 验证

- Python 定向工具、Runtime、审批与 API 测试：6 passed。
- `scripts/check.sh`：409 passed；Ruff、格式检查、strict mypy（181 个 source files）与锁文件检查均通过。
- Desktop：`npm run format`、`npm run typecheck`、`npm run lint`、`npm run test`（26 passed）和 `npm run build` 全部通过。
- `git diff --check` 通过。

### 决策变化

- 补充 DEC-060：真实 Runtime 注册三种单文件修改 Tool；审批响应不向 Renderer 发送正文；Undo 只经本地用户归属校验和精确路径复核的固定 API/IPC 由用户触发。

### 下一步

- 由用户在真实桌面软件中人工验证 CREATE、REPLACE、DELETE 的首次审批、Conversation 级授权、刷新后的卡片、正常 Undo 与外部修改后的冲突提示。
- 多文件原子体验继续作为独立 `FileChangeSet` 任务，不在本次单文件闭环中隐式扩展。

## 2026-08-15 Desktop FileChange timeline refinement

### 完成

- FileChange 卡片不再统一堆在消息列表底部；Renderer 按持久化变更时间将其插入到对应 Conversation 的消息时间线中，通常位于触发操作的用户消息之后、最终 AssistantMessage 之前。
- Undo 失败不再写入对话顶部的通用错误区。卡片会在其 Undo 操作附近显示安全的局部失败提示；后端已标记冲突时，卡片显示 `Changed later`。

### 验证

- Desktop `npm run format`、`npm run typecheck`、`npm run lint`、`npm run test`（26 passed）和 `npm run build` 全部通过。

## 2026-08-15 FileChange conflict explanation refinement

### 完成

- `CONFLICTED` FileChange 不再只显示 `Changed later`；对应卡片显示 `Undo unavailable` 和“当前文件版本与 asAgent 修改时的版本不同”的明确原因，提示保留在该操作附近。

### 验证

- Desktop `npm run format`、`npm run typecheck`、`npm run lint`、`npm run test`（26 passed）和 `npm run build` 全部通过。

## 2026-08-15 FileChange approval and banner refinement

### 完成

- `Always allow file changes` 现以当前 Conversation 的 `filesystem.write` 家族授权复用 CREATE、REPLACE、DELETE 三种单文件操作；不会影响批量变更、范围扩大或其他 Tool。
- 审批横幅改为自适应两行：操作摘要和路径独占上行，操作按钮在下行换行，避免窄窗口中按钮覆盖文字。

### 验证

- Approval 单元测试覆盖从 CREATE 授权后直接执行 REPLACE 和 DELETE；定向 Python 测试 12 passed。
- Desktop `npm run format`、`npm run typecheck`、`npm run lint`、`npm run test`（26 passed）和 `npm run build` 全部通过。

## 2026-08-15 FileChange post-response placement refinement

### 完成

- FileChange 卡片优先跟随变更后第一条 AssistantMessage，显示在 Agent 的最终回复之后；没有可匹配回复的历史记录才回退到最近前序消息。
- 卡片改为紧凑的最大 720px 轻量记录，缩小间距、字体和 Undo 按钮；过长路径在视觉上省略但保留完整悬停提示。

### 验证

- Desktop `npm run format`、`npm run typecheck`、`npm run lint`、`npm run test`（26 passed）和 `npm run build` 全部通过。

## 2026-08-15 FileChange conflict card visual refinement

### 完成

- 冲突信息改为文件路径下方的紧凑状态行：红色 `Undo unavailable` 标签和简短版本差异原因，不再占据卡片右侧的大块空间。

### 验证

- Desktop `npm run format`、`npm run typecheck`、`npm run lint`、`npm run test`（26 passed）和 `npm run build` 全部通过。

## 2026-08-15 FileChange post-response separator refinement

### 完成

- FileChange 改为 Agent 回复后的附注区域，以浅色上边线分隔；可用的 `Undo` 与操作标题顶部对齐，路径和冲突原因位于其下，避免右侧说明造成视觉割裂。

### 验证

- Desktop `npm run format`、`npm run typecheck`、`npm run lint`、`npm run test`（26 passed）和 `npm run build` 全部通过。

## 2026-08-15 Desktop message actions

### 完成

- 用户和 AssistantMessage 都显示创建时间；用户消息另有 Edit 操作。两者使用重叠圆角方框的复制图标，复制成功时短暂显示勾选确认。
- 复制文本通过受来源校验的 Main/Preload 固定 IPC 写入系统剪贴板，成功时图标短暂显示确认。
- Edit 只将原正文带回 Composer，并提示发送会创建新的 Message 和 Run；既有消息、回复、工具调用和 FileChange 审计不会被改写。

### 验证

- Desktop `npm run format`、`npm run typecheck`、`npm run lint`、`npm run test`（26 passed）和 `npm run build` 全部通过。

### 决策变化

- 新增 DEC-077。

## 2026-08-15 Conversation rename ordering

### 完成

- 重命名 Conversation 只保存标题，不再更新其活跃时间；Renderer 也原位更新该列表项，因此重命名后不会移到列表首位。

## 2026-08-15 Assistant Markdown table rendering

### 完成

- AssistantMessage 的安全 Markdown 渲染启用 GFM 表格语法；表格使用紧凑边框样式，超出消息宽度时在消息内横向滚动。

### 验证

- Desktop `npm run format`、`npm run typecheck`、`npm run lint`、`npm run test`（26 passed）和 `npm run build` 全部通过。

## 2026-08-16 可见嵌入式浏览器基础：范围确认

### 已确认

- 新建独立功能分支 `visible-browser-foundation`，用于可见嵌入式浏览器基础；已有未提交的会话列表 CSS 调整不属于本功能，保持原样且不会纳入本功能提交。
- 浏览器体验优先保证用户可见、可理解并可在未来人工接管：Electron Main 将成为 asAgent 专属持久浏览器 Session 的唯一所有者，使用 `WebContentsView`，不采用已弃用的 `BrowserView`。
- 第一个小任务只新增独立 Browser 菜单、可见网页 View 和安全生命周期。它不连接 Python Agent、ToolRegistry、MCP、Gmail、Scheduler 或浏览器自动化操作。
- 当前不会复制或导出 Cookie，也不允许 Playwright 或其他 Chromium 进程并发访问同一 Profile。网页的 Cookie、密码、Storage 与会话凭据不进入 Renderer、Python、日志、RunEvent、ToolCall 或模型上下文。

### 下一步

- 在本分支的一个独立小任务中设计并实现最小 `WebContentsView` 菜单与关闭生命周期，配套 Main 进程测试和安全导航验收；完成前不开始 AI BrowserAction。

## 2026-08-16 可见嵌入式浏览器 Browser v0

### 完成

- Electron Main 现在创建并拥有使用 `browser-profile` 持久 Session 的 `WebContentsView`；Renderer 通过来源校验后的窄 IPC 显示、隐藏、导航、关闭和控制受管标签，不能读取网页 DOM、Cookie、Storage 或密码。
- Browser 菜单提供可见标签、地址栏、后退、前进、刷新和主页。HTTP/HTTPS 地址可省略 scheme；`file:`、`javascript:`、`data:`、`ftp:` 等非网页协议被拒绝。
- `window.open`/`target=_blank` 的 HTTP/HTTPS 目标不创建原生 Electron 子窗口，而是转换为当前可见 Session 中最多 16 个标签；不安全目标仍拒绝。
- 原始带 userinfo 的 URL 只传给 Main 的 `loadURL()`，以保留 Basic Authentication 兼容性。所有发给 Renderer 的导航状态、地址栏回执和新标签状态均删除 username/password；页面加载失败返回安全错误，HTTP 404 继续作为正常页面加载。
- 本功能仍不接入 Python Agent、ToolRegistry、MCP、Gmail 或 Scheduler。

### 验证

- Desktop `npm run format`、`npm run typecheck`、`npm run lint`、`npm run test`（79 passed）、`npm run build` 和 `git diff --check` 全部通过。
- 手动桌面验收通过：普通 HTTP/HTTPS 导航、网页第三方链接的受管新标签、带 userinfo 地址在加载后的脱敏显示、`file:`/`javascript:`/`data:` 拒绝、Chat/Browser 切换后的页面保持，以及重启后的专属 Session/Profile 均符合预期。测试没有使用真实账号或密码。

### 下一步

- 在用户确认后，直接设计 Agent 读取当前可见网页内容的最小 Browser Tool 闭环；页面加载状态只作为该 Tool 的必要结果，不单独开发观测产品功能。本次仍不开始通用点击/输入、站点范围、审批或 Scheduler。
