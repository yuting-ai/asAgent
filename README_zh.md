<div align="center">

# asAgent

**私有化、轻量级、本地优先的个人 AI 智能体桌面客户端**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.12+](https://img.shields.io/badge/Python-3.12%2B-teal.svg)](https://www.python.org/)
[![Electron: 39+](https://img.shields.io/badge/Electron-39%2B-47848F.svg)](https://www.electronjs.org/)
[![React: 19](https://img.shields.io/badge/React-19-52C9D1.svg)](https://react.dev/)
[![TypeScript: 5.9](https://img.shields.io/badge/TypeScript-5.9-3178C6.svg)](https://www.typescriptlang.org/)
[![Tests: 660+ Passed](https://img.shields.io/badge/Tests-660%2B%20Passed-brightgreen.svg)](#-测试与质量保证)

[English](README.md) • **简体中文**

[核心特性](#-核心特性) • [架构与安全](#-架构与安全性) • [快速开始](#-快速开始--quickstart) • [模型配置](#-模型服务商配置) • [项目状态与路线图](#-项目状态与开发路线图)

</div>

---

## 🌟 核心理念与概述

**asAgent** 是一款开源、本地优先（Local-First）的个人 AI 助手与自主桌面智能体（Autonomous Desktop Agent）。它将大语言模型（LLM）的推理能力与操作系统的本地能力深度结合，且 **100% 的用户数据、数据库记录与凭据资产均严格保存在用户本机**。

* 🔒 **100% 隐私与本地优先**：基于 SQLite 本地数据库，密码凭据交由系统底层钥匙串（macOS Keychain / 系统凭据存储）加密托管。零外部遥测数据，零云端账号绑定。
* 🧩 **模型厂商中立 (Provider-Neutral)**：无缝接入 Ollama、LM Studio、DeepSeek、OpenAI、OpenRouter、硅基流动（SiliconFlow）等任意兼容 OpenAI 协议的本地与云端模型。
* 🛡️ **安全受控 (Human-in-the-Loop)**：敏感文件写操作与重要工具调用均受权限策略保护（支持“允许一次”、“会话允许”、“始终允许”与“拒绝”），并支持差异快照自动一键撤销（Undo）。
* ⚡ **Neo-Mint 极客视觉**：现代桌面端 UI，具备 WCAG AAA 顶级可读性对比度、原生 macOS 窗口拖拽、自由调整分栏宽度与中英双语无缝切换。

---

## 🚀 核心特性

### 1. 💬 私有多轮对话与上下文管理
* **实时认证 SSE 流式传输**：基于回环地址带 Bearer Token 鉴权的 Server-Sent Events 实现平滑流式输出；
* **可观测运行轨迹 (Run Activity)**：实时卡片展示 Agent 的推理链、工具调用详情、耗时统计与执行结果；
* **智能上下文预算**：内置 Context Builder 滑动窗口算法，在保留长对话深度的同时严格控制 Token 溢出与成本；
* **双语动态切换**：全界面原生支持 **English** 与 **中文 (简体)** 动态即时切换，无需重启应用。

### 2. 📁 工作区与可逆文件工具
* **严格隔离的文件操作**：受控工具支持 `list_dir`、`read_file`、`write_file`、`edit_file`（行级精准搜索替换）与 `search_files`，严防软链接逃逸；
* **可逆文件差异快照 (一键 Undo)**：Agent 修改或删除文件前自动在 SQLite 中记录差异快照，对话流中直接提供撤销卡片，一键回滚磁盘文件；
* **工作区文件树联动**：侧边栏实时浏览工作区目录树，支持文件内容即时预览与一键“引用至对话/输入框”。

### 3. 🌐 嵌入式自主浏览器
* **双浏览器隔离架构**：用户可视化主浏览视图与 Agent 自动化驱动会话相互隔离；
* **深度网页自动化工具集**：原生支持 `browser.navigate`、`browser.read_current_page`（结构化 Markdown DOM 提取并自动标引链接/按钮）、`browser.inspect_interactive`、`browser.click`、`browser.fill`、`browser.select` 与 `browser.wait`；
* **页面助手侧栏**：在浏览任意网页时，一键呼出助手面板对当前网页进行答疑、长文摘要与自动化操作。

### 4. ⏰ 定时任务与自愈自动化引擎
* **自然语言对话式规划**：通过大画布交互式起草并调整定时任务指令、周期与目标；
* **自由拖拽分栏工作台**：列表栏与详情画布支持 260px ~ 640px 自由拖拽调节宽度并自动持久化；
* **执行历史与详情时间线**：完整记录每次定时触发的运行状态、耗时指标与 Markdown 报告输出；
* **执行自适应自愈与计划自动回写 (`automation.update_plan`)**：Agent 在执行定时任务时若遭遇失效链接（如 400/404）或网站改版，会自动寻找备用路径并在成功后**自动更新任务计划与 URL**，保证后续周期性执行始终稳定。

### 5. 🔌 扩展协议与外部工具
* **Model Context Protocol (MCP)**：原生支持 MCP `stdio` 客户端会话，管理外部服务 Sidecar 进程并动态注册工具能力；
* **实时网络搜索**：内置 Tavily Search API 集成，随时获取最新网络公开资讯。

---

## 🏗️ 架构与安全性

```
┌─────────────────────────────────────────────────────────────┐
│                    Electron Desktop Shell                   │
│         (React 19 + TypeScript + Vite + CSS Tokens)         │
└──────────────────────────────┬──────────────────────────────┘
                               │ Loopback HTTP & Authenticated SSE
                               │ Bearer Token / 127.0.0.1:0
┌──────────────────────────────▼──────────────────────────────┐
│                    FastAPI Local API Gateway                │
├─────────────────────────────────────────────────────────────┤
│                       asAgent Core Engine                   │
│  ┌──────────────────────┬────────────────────────────────┐  │
│  │ Context Builder      │ Model Provider Neutral Adapter │  │
│  ├──────────────────────┼────────────────────────────────┤  │
│  │ Tool Pipeline & Sec  │ Scheduler & Cron Engine        │  │
│  ├──────────────────────┼────────────────────────────────┤  │
│  │ Browser Automation   │ Reversible File Snapshot Store │  │
│  └──────────────────────┴────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│             SQLite Repository & OS Keychain Store           │
└─────────────────────────────────────────────────────────────┘
```

* **本地进程隔离**：Python 后端动态绑定随机本地回环端口（`127.0.0.1:0`），并将实际端口告知 Electron 主进程；
* **单次启动 Bearer 鉴权**：应用每次启动时生成一次性随机 Bearer Token，所有 API 与 SSE 请求强制校验，杜绝未经授权的跨进程访问；
* **系统凭据安全库**：API Key 保存至系统原生钥匙串（macOS Keychain），不在日志、配置文件或前端界面中暴露明文。

---

## 💻 快速开始 / Quickstart

### 环境要求 (Prerequisites)
* **Node.js** >= 20.0.0
* **Python** >= 3.12 (推荐使用 `venv` 或 `uv` 进行环境管理)
* **npm** 或 **pnpm**

---

### 1. 克隆仓库与安装依赖

```bash
# 克隆项目
git clone https://github.com/your-username/asAgent.git
cd asAgent

# 创建并激活 Python 虚拟环境
python -m venv .venv
source .venv/bin/activate

# 以可编辑模式安装 Python 依赖
pip install -e ".[dev]"

# 安装桌面客户端前端依赖
npm --prefix desktop install
```

---

### 2. 本地开发模式运行 (Development)

运行以下命令将同时启动 Python Agent 后端服务与 Electron 桌面客户端：

```bash
cd desktop
npm run dev
```

如需使用环境变量中的 DeepSeek API Key 启动：
```bash
ASAGENT_MODEL_API_KEY="your-deepseek-api-key" npm --prefix desktop run dev:deepseek
```

---

### 3. 测试与质量保证

asAgent 包含覆盖单元测试、集成测试与契约测试的完整测试矩阵：

```bash
# 运行 Python 后端测试套件 (530+ 个测试)
pytest

# 运行桌面前端 TypeScript 类型检查、代码风格检查与测试 (133+ 个测试)
npm --prefix desktop run typecheck
npm --prefix desktop run lint
npm --prefix desktop test
```

---

### 4. 桌面安装包构建 (Build & Package)

```bash
# 构建 macOS 应用程序 (.dmg / .app)
npm --prefix desktop run build:mac

# 构建 Windows 安装包 (.exe)
npm --prefix desktop run build:win

# 构建 Linux 安装包 (AppImage / deb)
npm --prefix desktop run build:linux
```

---

## ⚙️ 模型服务商配置

在应用内的 **设置 (Settings)** 页面，可选择或配置您的模型接口：

| 服务提供商 | 部署类型 | 默认 Base URL | 当前测试状态 |
| :--- | :--- | :--- | :--- |
| **DeepSeek** | 云端 API | `https://api.deepseek.com/v1` | **已完成充分实测验证** |
| **Ollama** | 本地模型 | `http://localhost:11434/v1` | 兼容 (符合 OpenAI 协议标准) |
| **LM Studio** | 本地模型 | `http://localhost:1234/v1` | 兼容 (符合 OpenAI 协议标准) |
| **OpenAI** | 云端 API | `https://api.openai.com/v1` | 兼容 (符合 OpenAI 协议标准) |
| **OpenRouter** | 聚合 API | `https://openrouter.ai/api/v1` | 兼容 (符合 OpenAI 协议标准) |
| **SiliconFlow** | 云端 API | `https://api.siliconflow.cn/v1` | 兼容 (符合 OpenAI 协议标准) |
| **自定义 (Custom)** | 本地 / 云端 | 用户自定义 | 兼容 (符合 OpenAI 协议标准) |

> [!IMPORTANT]
> **当前测试状态说明**：虽然 asAgent 的模型接入层遵循严格的 OpenAI API 标准协议设计，但 **DeepSeek（如 `deepseek-chat` / `deepseek-reasoner`）是目前经过最完整端到端实测验证的模型**。针对其他本地与云端模型的深入微调与兼容性测试正在持续进行中。

*API Key 均加密保存在系统钥匙串中，界面不显示明文，确保资产安全。*

---

## 📋 项目状态与开发路线图

### ✅ 已实现功能 (Completed & Implemented)
* [x] **自主 Agent 执行循环**：多轮自主工具调用、Schema 校验、权限控制与超时策略；
* [x] **厂商中立模型层**：兼容 OpenAI 协议适配器、SSE 流式解析与失败分类；
* [x] **SQLite 全量持久化**：会话、消息、运行事件、定时任务及文件差异快照 Repository；
* [x] **可逆文件系统**：原子级差异备份与对话内一键撤销（Undo）；
* [x] **嵌入式自主浏览器**：双视图安全隔离、页面结构化 Markdown 提取与自动化交互；
* [x] **定时任务自愈调度**：Cron 定时执行、并发防风暴锁、执行历史时间线与 400/404 自适应自愈（`automation.update_plan`）；
* [x] **MCP 扩展协议**：stdio 客户端会话与外部工具动态加载；
* [x] **桌面现代化界面**：Electron 39 外壳、可拖拽分栏、原生 macOS 窗口拖拽、中英双语即时切换与 Neo-Mint 设计规范。

### 🚧 待完成/规划中任务清单 (Pending Roadmap Tasks)
* [ ] **长期用户记忆与全局知识库**：基于 Embedding 向量或画像知识库的跨会话长期用户偏好记忆与检索召回（当前由滑动窗口上下文管理）；
* [ ] **动态 Skills 目录加载机制**：支持从本地 `skills/` 目录动态解析 `SKILL.md` 清单并由 Agent 按需即时加载领域专属能力；
* [ ] **多 Agent 协同与子任务派发**：支持主 Agent 分裂派生后台子 Agent（Subagents）进行多线程分工研究与并发汇总；
* [ ] **桌面安装包签名与自动更新管线**：Apple Notarization 公证、Windows 证书签名及 GitHub Releases 在线静默自动更新；
* [ ] **独立无头守护进程 / Docker Compose 部署模式**：为无需界面的服务器环境提供独立的 Docker Compose 与无头守护运行容器。

---

## 📄 开源协议 (License)

本项目采用 [MIT License](LICENSE) 开源协议。
