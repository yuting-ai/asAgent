# asAgent 开发与学习路线

## 1. 路线原则

asAgent 采用“每个阶段完成一个可运行闭环”的方式开发。不得先写大量框架再等待最后集成。

每个阶段按相同节奏进行：

1. 理解本阶段概念和要解决的问题。
2. 画出最小数据流和失败路径。
3. 定义最少接口、领域对象和验收样例。
4. 使用 Fake 实现完成稳定测试。
5. 接入一个真实实现验证。
6. 主动制造异常、超时和取消。
7. 记录学习笔记和架构结论。
8. 更新 `progress.md`。

时间仅作为参考。建议按每周 8–12 小时估算，总体约 12–18 周。质量和理解优先于赶进度。

## 2. 阶段总览

| 阶段 | 主题 | 可运行成果 |
| --- | --- | --- |
| 0 | 项目骨架与领域建模 | Fake Model 驱动的核心测试 |
| 1 | 最小聊天 | CLI 可以连续对话 |
| 2 | Agent Loop 与 Tools | 模型可以调用三个安全工具 |
| 3 | SQLite 与 Run Events | 重启后恢复对话并回放运行 |
| 4 | Context Builder | 有预算、裁剪和摘要边界的模型上下文 |
| 5 | Workspace 与安全 | 受控文件工具、取消和审批边界 |
| 6 | Local API 与 SSE | 浏览器/API 客户端可流式对话 |
| 7 | Electron 最小集成 | Electron 启停 Python、完成聊天并通过首次 Sidecar 打包冒烟测试 |
| 8 | MCP | stdio MCP 工具进入统一 Tool Registry |
| 9 | Skills | Agent 可选择并读取技能说明 |
| 10 | Memory 与 Knowledge | 对话摘要和个人长期记忆 |
| 11 | Scheduler 与扩展口 | 本地定时 Run 和 Channel 接口验证 |
| 12 | 桌面打包与发布 | 无 Python/Docker 依赖的安装包 |

## 3. 阶段 0：项目骨架与领域建模

### 学习目标

- Python 类型系统、dataclass/Pydantic 和 Protocol。
- 模块化单体与依赖倒置。
- Conversation、Run、Message、Event 和 ToolCall 的区别。
- Fake/Mock 为什么是 Agent 测试的基础。

### 开发任务

- 初始化 Git、`pyproject.toml` 和 `src/asagent` 布局。
- 配置 Python 3.13、uv、pytest、pytest-asyncio、Ruff 和 strict mypy；启用 `pydantic.mypy`。
- 使用 `.python-version` 固定 Python 3.13，提交跨平台 `uv.lock`；本地、Docker 和 CI 均通过 uv 使用同一依赖锁。
- Pydantic 2 主要用于系统边界；Core 领域对象优先使用 dataclass、Enum、NewType 和 Protocol。
- 创建 `core` 基础对象和 ID 类型。
- 定义顶层 `AppPaths` 路径契约；测试使用临时目录，不读取真实用户目录。
- 先定义 Provider-neutral 的 `ModelMessage`、`ModelToolDefinition`、`ModelToolCall`、`ModelRequest`、`ModelResponse` 和 `ModelEvent` 数据类型，再定义 `ModelProvider`、Repository、Tool 和 EventPublisher Protocol。
- 实现 `FakeModelProvider`。
- 定义结构化错误和 Run 状态。
- 建立单元测试目录和测试约定。
- 创建 `docs/learning-notes/`。

### 产出

- 核心领域对象。
- 不依赖网络的测试。
- 第一份学习笔记：`Conversation 与 Run`。

### 验收

- `pytest`、lint 和类型检查通过。
- `uv lock --check` 通过，锁文件与项目元数据一致。
- `core` 不导入 FastAPI、SQLite 或模型 SDK。
- Fake Model 能按预设脚本返回文本或工具调用。
- `AppPaths` 可以分别由开发、测试和发布入口显式构造，业务代码不拼接用户主目录。

## 4. 阶段 1：最小聊天

### 学习目标

- LLM Message 格式。
- 异步 Provider，以及流式与非流式响应的统一边界。
- Conversation 生命周期。
- 配置和 Secret 的区别。

### 开发任务

- 实现内存版 Conversation Repository。
- 实现 `ChatService`。
- 实现 CLI：新建对话、发送消息、退出。
- 锁定并定义 Provider Profile 与 Secret 引用边界：Pydantic `ProviderConfig`/`ProviderProfiles` 保存并校验非敏感连接参数，`SecretProvider` 仅以 `secret_id` 解析 API Key。
- 实现一个 OpenAI-compatible Provider；首个真实 Profile 使用 DeepSeek，未来 OpenAI 与其他兼容服务复用该 Adapter。当前已完成非流式响应和文本/推理 SSE 增量的离线 HTTP 映射；流式工具调用待阶段 2 Agent Loop。
- 将 Claude 等原生 Messages API Provider 作为独立 Adapter 后续实现，不将其协议细节混入 OpenAI-compatible Adapter。
- 保存使用量和模型元数据。
- 添加 Provider 错误转换和重试边界。
- 阶段 1 收尾后，单独建立质量门禁 Pipeline：先提供一个统一的本地检查入口，再评估 Git pre-commit hook；代码托管到 Git 平台后，用 CI Runner 在干净环境复用同一套 uv 锁文件执行测试、Ruff、mypy 和锁文件检查。当前学习阶段不启用“保存文件即运行完整测试”的文件监听。

### 验收

- CLI 可以连续多轮对话。
- 不配置真实 API 时，Fake Model 路径仍完整可用。
- 模型异常不会丢失用户输入或导致进程崩溃。

## 5. 阶段 2：Agent Loop 与内置工具

### 学习目标

- Function/Tool Calling。
- JSON Schema 参数验证。
- Agent 状态机。
- 循环保护、超时和错误回传。

### 开发任务

- 按以下依赖顺序完成最小闭环，不能在模型上下文无法表达工具往返时提前实现 Loop：
  1. 实现 `ToolDefinition`、`ToolRegistry`、`ToolExecutor` 与确定性的内置工具：`builtin.calculator`、`builtin.current_time`、`builtin.echo`。
  2. 定义 assistant tool calls 与配对 TOOL results 的 Provider-neutral 消息契约，并覆盖不合法组合。
  3. 验证目标 Provider 能将该完整历史映射为合法请求；测试必须检查出站负载，而不仅是解析最终响应。
  4. 区分内部 `tool_id` 与 Provider 可接受的工具名称，并将映射写入 Tool Snapshot。
  5. 在上述条件成立后实现最小非流式 Agent Loop。
- 添加最大步骤、重复调用检测和结果截断。
- 实现基础 Run 取消令牌、模型超时和工具超时；取消定位到 `run_id`。
- 记录最小 RunEvent；随后插入内存态开发 CLI 的 Agent 垂直切片，手动体验“输入 → Loop → Provider → 工具 → 最终回答/事件”。
- 再记录 ToolCall；SQLite 持久化、SSE 和 Electron 仍留在后续阶段。

### 验收

- 模型可调用工具并基于结果给出最终答案。
- 覆盖工具不存在、参数错误、异常、超时和重复调用。
- 达到最大步骤时进入明确的 `LIMIT_REACHED` 终态，不继续调用工具，也不记录为成功完成。
- 在模型调用或工具执行期间取消 Run 后，状态进入 `CANCELLED`，下一次 Run 不受影响。
- tool_use/tool_result 始终合法配对。
- 每次“模型请求工具 → 工具结果 → 再次模型调用”的历史可由 Provider-neutral 契约表示，并可映射为目标 Provider 的合法请求。
- 当前 Run 的工具调用链只能作为完整单元进入或离开上下文；未知工具、参数错误与工具异常仍会产生配对的错误结果。
- 取消在模型调用前、相邻工具之间及结果追加前可被观察；重复调用检测以内部工具身份和规范化参数为基础。

## 6. 阶段 3：SQLite 与可恢复状态

### 学习目标

- Repository 与数据库实现分离。
- 事务、迁移和并发写入。
- 用户消息与内部事件分表的价值。

### 开发任务

- 引入 SQLAlchemy 2.0 Core、aiosqlite 和 Alembic，不使用 SQLAlchemy ORM。
- 使用 SQLAlchemy Core 建立初始 Schema，并通过 Alembic 管理迁移。
- 使用 `AppPaths.data_dir` 定位 SQLite，不在 Repository 中推导系统路径。
- 实现 SQLite Repository。
- 持久化 Conversation、Message、Run、RunEvent、ToolCall。
- 为 RunEvent 增加每个 Run 单调递增的 `sequence`，并建立 `(run_id, sequence)` 唯一约束。
- 用明确事务边界原子创建用户消息和 Run，并为 API 重试预留幂等键。
- 通过集成测试确定并固定 foreign keys、journal mode、busy timeout、synchronous 和 SQLite/aiosqlite 事务控制。
- 重启后加载对话列表和历史。
- 实现 Run 回放查询。

### 验收

- 重启进程后可以继续对话。
- 失败和取消的 Run 有完整记录。
- UI/CLI 历史不显示内部 tool_result 消息。
- Alembic 可以在空数据库完成升级，并能从已建 Schema 重复验证当前版本。
- 外键、并发写入、锁等待和事务回滚行为有集成测试。

## 7. 阶段 4：Context Builder

### 学习目标

- Context Window 与 Token 预算。
- System Prompt、历史、工具 Schema 和输出预算的关系。
- 摘要与原始历史的边界。

### 开发任务

- 实现分层 System Prompt Builder。
- 实现消息标准化和合法性检查。
- 分离 Provider/模型的 context window 硬上限与用户可配置的输入预算、输出预留和轮次保护；未来设置窗口只能在模型上限内调整策略。
- 实现 Token 估算和上下文预算，覆盖 system prompt、工具 Schema、模型消息与输出预留。
- 生成不可变、默认脱敏的 ContextSnapshot，说明模型本次实际可见的组成、来源、预算和裁剪原因。
- 实现旧工具结果截断、按完整工具调用链裁剪历史，以及可替换的 Conversation Summary 接口；摘要失败时回退为确定性裁剪，不修改原始 Conversation。
- 添加 Context 调试快照，默认脱敏且关闭。

### 验收

- 大历史不会无界增长。
- 裁剪不破坏当前 Run 的工具调用链。
- 每个上下文组成部分的 Token 占用可观察。
- 后台摘要或并发任务不能修改已创建的 ContextSnapshot。

## 8. 阶段 5：Workspace 与安全工具

### 学习目标

- 路径穿越、符号链接和权限边界。
- 副作用等级、用户批准和审计。
- 阻塞任务的异步封装。

### 开发任务

- 复用阶段 0 的 `AppPaths`，实现 `WorkspaceResolver`、允许根目录和 Run Directory。
- 实现文件范围设置窗口与配置模型：仅 Workspace（默认）、用户选择的文件夹、整台电脑；全盘模式需要高风险二次确认和平台文件访问授权，可随时撤销。
- 文件操作在当前用户选择的范围内进行；外部文件或根目录可由用户精确选择或导入。全盘范围只扩大可寻址路径，不能自动扩大写入、删除、执行命令或敏感位置读取的权限。
- 实现只读工具 `filesystem.read_file`、`filesystem.list`。
- 在基础纯文本读取稳定后，独立设计文档正文提取：`document.extract_text` 可逐步支持 DOCX 和带文本层的 PDF；扫描型 PDF 与图片 OCR 保持为单独工具。两类能力都必须声明文件格式、大小/页数和输出限制、超时、权限与审计边界，不得隐式扫描或上传用户文档。
- 先实现 create-only 的受控写入工具；覆盖、追加、删除和自动创建目录作为独立能力推进。
- 在引入覆盖、追加或删除前，先设计可撤回文件变更：持久化 `FileChange`、变更前快照、前后哈希、来源 Run、容量/保留期与隐私边界；撤回仅适用于 asAgent 自己记录的变更，且当前哈希未被后续修改时才允许原子恢复。create-only 可在该机制就绪后纳入记录，以支持安全删除 Agent 新建且未被后续修改的文件。
- 建立 Tool Policy 和 Approval 接口；批准请求展示操作、规范化路径/根、权限、递归范围、影响摘要和有效期限。写入、删除、执行命令、敏感位置读取和 Agent 提议的范围扩大始终单独批准。
- Policy 与 Approval 数据模型区分工具能力、文件范围和单次操作批准，为后续浏览器、OAuth 与 MCP 复用，但不让文件范围跨资源继承。
- 将阶段 2 的取消/超时机制接入文件操作、审批等待和受控阻塞任务。
- Shell 工具只设计接口，是否实现由后续决策确认。

### 验收

- 不能逃逸允许的 Workspace Root。
- 默认不具备 Workspace 外访问；用户可在设置中显式选择文件夹或整台电脑范围，且全盘范围可撤销并不绕过高副作用操作批准。
- 取消长任务后，下一次对话正常。
- 写操作以及授权、拒绝和范围扩大产生不包含文件正文或 Secret 的审计事件。

## 9. 阶段 6：Local API 与 SSE

### 学习目标

- FastAPI 依赖注入。
- HTTP API 版本管理。
- SSE 生命周期、断线和事件重连。
- 本地接口认证。

### 开发任务

- 实现 `/api/v1/health`。
- 实现 Conversation CRUD。
- 实现创建 Run、查询状态和取消 Run。
- 实现基于 `fetch` 的认证 SSE RunEvent 流，不使用无法设置 Bearer Header 的原生 EventSource。
- 使用 `sequence` 和 `Last-Event-ID`/`after_sequence` 实现断线续传和去重。
- 支持 host、port、app-home、workspace-dir 等启动参数，并支持独立于命令行的 Token Bootstrap 通道。
- 校验 Origin Allowlist；为明确允许的开发/发布来源配置 CORS 和 Authorization Header 预检，不使用通配来源。
- 生成 OpenAPI/JSON 契约测试。

### 验收

- curl 或测试客户端可完成完整流式对话。
- SSE 断开不会让后端泄漏 Queue 或 Run。
- 断线重连不会丢失或重复展示已经持久化的事件。
- 非法 Token 无法访问业务接口。

## 10. 阶段 7：Electron 最小集成

### 学习目标

- Electron Main、Preload、Renderer 的安全边界。
- Python Sidecar 生命周期。
- 开发资源和用户数据目录分离。

### 开发任务

- 创建 Electron + React + TypeScript 工程。
- Main 启动本地 Python 源码。
- Backend 绑定 `127.0.0.1:0`，再通过仅由 Main 读取的结构化启动握手报告实际端口。
- 使用临时 Token；优先通过子进程管道传递，必要时使用环境变量，不放入命令行、URL 或日志。
- Health Check 后才显示聊天页面。
- Renderer 使用带 Bearer Header 的 HTTP + fetch-based SSE 对话，Token 只保存在内存。
- 生产环境优先使用安全的自定义协议，不加载远程代码；设置严格 CSP、Origin Allowlist、导航和新窗口限制。
- Main 校验所有 IPC sender，Preload 只暴露逐项参数校验后的窄接口。
- 支持停止和重启 Backend。
- Electron 退出时优雅关闭 Python。
- 完成第一次 PyInstaller onedir Sidecar 冒烟构建，验证只读安装目录和 AppPaths。

### 验收

- 一条命令启动 Electron 开发环境。
- 不出现僵尸 Python 进程。
- Renderer 不具备 Node 和任意文件访问能力。
- 端口由 Backend 实际绑定后报告，不存在“探测空闲后再绑定”的竞争窗口。
- Token 不出现在进程参数、URL、localStorage 和日志中。
- Sidecar 在不依赖源码目录的情况下通过 Health Check 并完成一次 Fake Model 对话。

## 11. 阶段 8：MCP

### 学习目标

- MCP 协议版本协商、能力协商、initialize、notifications/initialized、tools/list、tools/call。
- stdio 子进程协议和 JSON-RPC。
- Server 生命周期、tools/list 分页与 listChanged、工具错误和协议错误的区别。
- 工具 Schema 和 Provider 名称映射的稳定性。

### 开发任务

- 实现测试 MCP Server。
- 实现 stdio McpClient。
- 实现 Server Manager 和名称空间。
- 为每个 MCP Server 配置独立的资源范围、工作目录、最小环境变量和 Secret 引用；不得继承 asAgent 的文件范围、浏览器 Profile 或其他账户 Token。
- 实现版本/能力协商、tools/list 分页和超时取消。
- 将 MCP 工具映射到统一 Tool Registry。
- 实现 Tool Snapshot 和错误隔离。
- 增加配置刷新；热更新只影响后续 Run。

### 验收

- 测试 Server 的工具可以被模型调用。
- Server 崩溃、超时和无效 JSON 不影响其他工具。
- 同名工具不会覆盖。

## 12. 阶段 9：Skills

### 学习目标

- Skill 与 Tool 的区别。
- Progressive Disclosure。
- Prompt 指令层级和上下文成本。

### 开发任务

- 扫描和校验 `SKILL.md` 元数据。
- 构建可用 Skill 摘要。
- 按需求选择并读取一个 Skill。
- 记录 Skill 版本和本次 Run 使用情况。

### 验收

- Skill 不作为可执行 Tool 注册。
- 未命中的 Skill 正文不进入上下文。
- 无效 Skill 给出可理解错误。

## 13. 阶段 10：Memory 与 Knowledge

### 学习目标

- Working、Conversation、User Memory 的区别。
- 摘要、关键词检索和向量检索的适用范围。
- 记忆污染、冲突和隐私。

### 开发任务

- Conversation Summary 的持久化、覆盖区间与跨重启复用。
- User Memory 的候选、用户确认、显式读写与来源追溯接口。
- 可选跨 Conversation 历史检索：先实现 SQLite 文本/关键词检索，按用户范围、相关度、数量和 Token 预算把来源明确的参考资料加入 ContextSnapshot；实际证明需要后再评估 Embedding。
- 关键词搜索和去重。
- Knowledge Markdown 以 Workspace 文件为主数据，SQLite 只保存索引、Checksum 和解析状态。
- 结构化 User Memory 以 SQLite 为主；`workspace/memory/` 只提供可重建导出。
- 评估后再决定是否增加 Embedding。

### 验收

- 新 Conversation 可以读取已确认的个人偏好。
- 不把临时任务结果错误写入长期记忆。
- 用户可以查看和删除记忆。

## 14. 阶段 11：Scheduler 与扩展口

### 开发任务

- Scheduler 通过 `RunService` 创建隔离 Run。
- 防止 Scheduler 工具自递归。
- 定义 Channel Adapter Protocol 和一个 Fake Channel 测试。
- 不实现真实 Telegram/WeChat。

### 验收

- 定时任务与当前对话上下文不互相污染。
- Fake Channel 不修改 Agent Core 即可接入。

## 15. 阶段 12：桌面打包与发布

阶段 7 已完成本地 Sidecar 冒烟构建；本阶段处理正式发行，而不是第一次发现打包问题。

### 开发任务

- PyInstaller onedir Sidecar。
- electron-builder 打包。
- macOS ARM/x64 构建验证。
- 用户数据迁移。
- 崩溃日志和更新流程。
- 后续再增加 Windows NSIS。

### 验收

- 干净机器无需 Python 和 Docker即可运行。
- 应用升级后数据库、Workspace 和配置保留。
- 安装目录只读时后端仍能正常启动。

## 16. Docker 工作流

从阶段 0 开始维护最小测试 Dockerfile，用于：

- 干净环境安装。
- 单元/集成测试。
- CI。
- MCP 测试 Server。

阶段 12 前不投入复杂 Docker Server 产品化。Docker 不是 Electron 的运行依赖。

## 17. 每阶段完成定义

一个阶段只有同时满足以下条件才算完成：

- 功能闭环可运行。
- 正常路径、错误路径和取消/超时路径有测试。
- 文档和代码一致。
- `progress.md` 已更新。
- 新增架构决策已登记。
- 没有把下一阶段的大功能偷偷带入当前实现。
