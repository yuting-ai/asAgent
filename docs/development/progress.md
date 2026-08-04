# Ragent 当前进度

## 1. 当前状态

- 项目阶段：阶段 0 已启动，Python/uv 工程骨架与质量工具闭环已完成
- 代码状态：已创建最小 `src/ragent` 包、Core ID 类型、不可变的 Conversation、用户可见 Message、Run、RunEvent、ToolCall 和 ToolDefinition 数据对象、Provider-neutral 模型交换数据类型、`ModelProvider` 与 Repository Protocol、`RunStatus` 状态枚举及 `AppPaths` 路径契约，并配置 pytest、pytest-asyncio、Ruff、strict mypy 与 `pydantic.mypy`
- 项目路径：`/Users/yuting/Desktop/BityDev/Ragent`
- 当前日期：2026-08-04
- 当前目标：`ToolDefinition` 已完成；下一独立任务是定义 `Tool` 和 `EventPublisher` Protocol

## 2. 已完成

- [x] 确认项目名称由 AsAgent 变更为 Ragent。
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

## 3. 尚未开始

- [ ] 定义 `Tool` 和 `EventPublisher` Protocol。
- [ ] 实现 Fake Model。

## 4. 下一阶段：阶段 0

### 目标

建立一个不依赖真实模型、Web、Electron 和数据库的可测试核心骨架。

### 建议执行顺序

1. 初始化 Git 和 Python 工程。
2. 建立最小目录，不提前创建所有未来空模块。
3. 定义领域对象和接口。
4. 实现 Fake Model。
5. 编写单元测试。
6. 记录第一篇学习笔记。
7. 更新本文件。

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
- [ ] 定义 `Tool` 和 `EventPublisher` Protocol。
- [ ] 实现 `FakeModelProvider`。
- [ ] 为核心对象和 Fake Model 编写测试。
- [ ] 创建 `docs/learning-notes/01-conversation-and-run.md`。
- [ ] 添加最小测试 Dockerfile。

### 阶段 0 验收

- [ ] `pytest` 全部通过。
- [ ] Ruff 检查通过。
- [ ] 类型检查通过。
- [ ] 测试无需网络和 API Key。
- [ ] Core 不依赖 FastAPI、Electron、SQLite 或模型 SDK。
- [ ] Fake Model 能预设文本响应和 ToolCall 响应。
- [ ] AppPaths 的开发、测试和发布构造方式有测试，业务代码不读取或拼接用户主目录。

## 5. 新 Codex 任务启动提示词

在 Ragent 项目下创建新任务后，使用：

```text
请先完整阅读项目根目录 AGENTS.md，以及其中列出的 docs/development 全部文档。

暂时不要写代码。请先总结：
1. Ragent 的产品定位和当前范围；
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
- 第一家真实模型服务尚未选择，但不会阻塞 Fake Model 阶段。

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

### 验证

- 检查：运行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv lock --check` 和 `git diff --check`。
- 结果：通过；29 个测试通过，Ruff 与 strict mypy 无问题，锁文件和 diff 检查通过。
- 检查：运行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv lock --check` 和 `git diff --check`。
- 结果：通过；31 个测试通过，两个类型完整的异步示例 Repository 满足 Protocol，Ruff 与 strict mypy 无问题，锁文件和 diff 检查通过。
- 检查：运行 `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv lock --check` 和 `git diff --check`。
- 结果：通过；34 个测试通过，ToolDefinition 的元数据、顶层 Schema 快照、正数超时与不可变性均已验证，Ruff 与 strict mypy 无问题，锁文件和 diff 检查通过。

### 决策变化

- 无；Conversation、Repository 与 ToolDefinition 均为既有架构中的边界，本次仅补齐最小 Core 数据对象和接口契约。

### 风险或问题

- 无。

### 下一步

- 定义 `Tool` 和 `EventPublisher` Protocol。
