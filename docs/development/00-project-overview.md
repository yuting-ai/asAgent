# asAgent 项目概览

## 1. 项目定位

asAgent 是一个本地运行、默认单用户、私有化的个人 AI 助手。

它同时是一个学习型开发项目：开发者通过亲手实现模型调用、Agent Loop、工具系统、会话持久化、上下文管理、MCP、Skills、Memory 和 Electron 桌面客户端，系统理解一个现代 Agent 产品从输入到执行、持久化和交付的完整链路。

项目不以复制 CowAgent 为目标。CowAgent 可以作为成熟实现的参考，asAgent 会在需要时吸收其中有效的工程经验，并重新建立更清晰的身份、状态、Workspace、工具和桌面边界。

CowAgent 源码位于 `/Users/yuting/Desktop/BityDev/CowAgent`。它不是默认读取的上下文，也不是 asAgent 的运行时或构建依赖。开发过程中只有两种情况可以参考：

1. 用户明确要求查看或比较 CowAgent。
2. Codex 先说明具体参考目的、准备查看的模块和预期收益，用户确认后再查看。

除此之外，开发应只依据 asAgent 自己的文档、代码和测试推进。参考 CowAgent 时也应优先理解设计取舍，而不是直接复制代码和历史兼容逻辑。

## 2. 产品愿景

用户安装 asAgent 后，不需要安装 Python 或 Docker，就可以在自己的电脑上与私人助手对话，并逐步让助手安全地读取本地文件、执行工具、调用 MCP 服务、使用 Skills、形成个人记忆和知识。

核心承诺：

- 数据默认保存在用户本机。
- 默认只有一个本地用户，不引入登录和多租户复杂度。
- Agent 的每一步重要行为可观察、可取消、可审计。
- 桌面客户端只是入口，Agent Core 可以独立测试和运行。
- 能力按阶段逐步增加，每个阶段都有可运行成果。

## 3. 当前范围

### 3.1 首个可用版本（MVP）必须支持

- 本地单用户。
- 多个相互隔离的对话。
- CLI 对话入口。
- 一个 OpenAI-compatible 模型接口。
- 流式和非流式模型响应的基础抽象。
- 最小 Agent Loop。
- 少量安全的内置工具。
- SQLite 会话和运行记录。
- 本地 HTTP API 与 SSE。
- Electron 最小桌面外壳。
- 可取消的 Run。
- 清晰的日志和运行事件。

这里的 MVP 是产品范围，不等同于路线图中的“阶段 1”。它由路线图阶段 0–7 逐步完成，并在阶段 7 结束时增加一次本地 Sidecar 打包冒烟测试。

### 3.2 MVP 后续阶段支持

- 分层 Workspace。
- 文件和 Shell 工具的权限控制。
- MCP stdio，再扩展 Streamable HTTP。
- Skills。
- Conversation Summary、User Memory 和 Knowledge。
- Scheduler。
- 正式 Electron 安装包和自动更新。
- 可选 Docker Server 部署。

### 3.3 当前明确不做

- Telegram、微信、飞书、Slack 等外部渠道。
- 多人协作、团队空间和组织管理。
- 用户注册、登录、RBAC 和多租户。
- 云端账号同步。
- 微服务、Kubernetes、消息队列集群。
- 第一版即引入向量数据库。
- 把 Docker 作为桌面用户的运行前提。
- 把 CowAgent 源码作为 asAgent 的代码依赖、默认上下文或自动同步来源。

这些能力可以预留接口，但不得增加当前实现复杂度。

## 4. 默认用户模型

第一版只有一个用户：

```text
user_id = "local-user"
```

仍然保留以下接口：

```python
class UserProvider(Protocol):
    def current_user_id(self) -> str: ...
```

本地实现始终返回 `local-user`。数据库中的 Conversation、Memory 和 Workspace 保留 `user_id` 字段，但不实现用户管理界面。

这是一种“保留边界、不实现业务”的设计：未来可以扩展用户来源，但今天不为不存在的多人场景付出成本。

## 5. 核心使用场景

### 场景 A：普通对话

```text
用户输入
→ 创建 Run
→ 加载对话上下文
→ 调用模型
→ 流式显示回答
→ 保存消息和运行记录
```

### 场景 B：工具辅助回答

```text
用户提出任务
→ 模型请求工具
→ 参数和权限校验
→ 执行工具
→ 将结果返回模型
→ 模型给出最终回答
```

### 场景 C：中止运行

```text
长任务运行中
→ 用户点击停止
→ 通过 run_id 发送取消请求
→ Runtime 在安全检查点停止
→ 保存 cancelled 状态
```

### 场景 D：重启后继续

```text
应用退出
→ SQLite 和 Workspace 保留
→ 再次启动
→ 加载对话列表和历史
→ 继续原有 Conversation
```

### 场景 E：未来接入其他渠道

```text
Telegram / WeChat 外部消息
→ Channel Adapter
→ 标准 ChatRequest
→ 与 Electron 对话走同一 Agent Core
```

当前只定义 Channel 边界，不实现具体适配器。

## 6. 产品原则

### Local first

用户数据、数据库、日志、Workspace 和个人记忆默认在本机。网络访问必须来自用户配置的模型或工具。

### Single user, future-ready

默认单用户，保留轻量 `user_id` 边界，不构建多用户系统。

### Observable

模型请求、工具调用、错误和运行结束都形成结构化事件。用户可以理解 Agent 正在做什么。

### Safe tools

模型选择工具不等于获得执行权限。工具必须经过参数校验、策略判断、超时和审计。

### Replaceable edges

模型、存储、Electron、Channel、MCP Transport 都是边界实现；Agent Core 不直接依赖具体厂商和 UI。

### Learn by building

每个里程碑只引入少量新概念，并要求开发者说明它解决的问题、失败方式和测试策略。

## 7. 成功标准

项目成功不只意味着“能聊天”，还包括：

- 可以解释一条消息从 UI 到模型再回到 UI 的完整路径。
- 可以解释 Conversation、Run、ToolCall 和 Memory 的区别。
- 可以在不修改 Agent Core 的情况下替换模型 Provider。
- 可以在不修改 Agent Core 的情况下增加新的 Channel Adapter。
- 可以从 SQLite 回放一次 Run 的关键事件。
- 工具异常、超时和取消不会破坏下一轮会话。
- Electron 安装包不要求用户安装 Python 或 Docker。
- Docker 环境可以验证后端在干净系统中的可安装性和测试结果。

## 8. 核心术语

| 名称 | 含义 |
| --- | --- |
| User | 本地用户，第一版固定为 `local-user` |
| Conversation | 一段可长期继续的对话 |
| Run | Agent 对一条用户请求的一次执行 |
| Message | 用户或助手可见的对话消息 |
| RunEvent | Agent 内部发生的结构化事件 |
| ToolCall | 一次工具调用及其结果 |
| Agent Loop | 模型与工具反复交互直到产生最终回答的循环 |
| Workspace | 助手可使用的本地长期文件空间 |
| Run Directory | 某次 Run 使用的临时目录 |
| Skill | 告诉 Agent 如何完成某类任务的说明书 |
| Tool | Agent 可以实际执行的能力 |
| MCP | 让外部 Server 按统一协议提供工具的机制 |
| Channel | 将外部消息转换成内部 ChatRequest 的入口适配器 |

## 9. 产品名称

- 项目名称：`asAgent`
- Python 包名：`asagent`
- 后端可执行文件：`asagent-backend`
- 桌面应用显示名：`asAgent`

名称应保持简单。模块名称优先使用 `chat`、`agent`、`models`、`tools`、`memory`、`workspace`、`storage`、`api` 和 `desktop`。
