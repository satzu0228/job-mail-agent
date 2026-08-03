# 求职邮迹 — Job Mail Agent

**基于大语言模型与多智能体协作的求职邮件智能管理系统。**

连接你的邮箱，自动识别求职邮件、提取面试信息、关联求职申请、生成回复草稿——所有关键操作经过你的人工审核后才执行。

## 功能概览

| 功能 | 说明 |
|------|------|
| 📬 **邮件同步** | 通过 IMAP 连接邮箱，自动同步邮件并解析正文 |
| 🤖 **智能分类与抽取** | LLM 自动识别邮件类型（面试/Offer/拒信等），抽取公司、岗位、时间、地点、会议链接等结构化信息 |
| 🔗 **求职申请匹配** | 将邮件自动关联到对应的求职申请，或建议新建申请 |
| 📅 **面试日程** | 自动提取面试时间并创建日程，支持到期前提醒 |
| ✍️ **回复草稿** | LLM 根据邮件内容生成回复草稿，人工确认后通过 SMTP 发送 |
| 👀 **人工审核** | 所有高风险操作（关联申请、阶段变更、日程创建、回复发送）均需人工批准后才执行 |
| ⚡ **一键批准** | 批准首项审核后自动执行后续低风险操作，只在发送回复时暂停确认 |
| 🔄 **自动流转** | 面试结果邮件自动更新对应轮次状态（通过/未通过），追踪多轮面试进度 |

## 系统架构

```
┌─────────────────────────────────────────────────┐
│                   Frontend                      │
│           Vue 3 + Element Plus + TS             │
│   Mail │ Applications │ Calendar │ Reviews │    │
│              Mailbox Settings                   │
└────────────────────┬────────────────────────────┘
                     │ REST API (/api/v1)
┌────────────────────┴────────────────────────────┐
│                  Backend                        │
│              FastAPI + LangGraph                 │
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Classify │→ │ Extract  │→ │ Match & Link │  │
│  │  Email   │  │  Info    │  │ Application  │  │
│  └──────────┘  └──────────┘  └──────────────┘  │
│        ↓              ↓               ↓         │
│  ┌──────────────────────────────────────────┐  │
│  │         Human Review (interrupt)         │  │
│  │   Approve / Reject / Auto-approve chain  │  │
│  └──────────────────────────────────────────┘  │
│        ↓              ↓               ↓         │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  Create  │  │  Reply   │  │   Finalize   │  │
│  │  Tasks   │  │  Draft   │  │              │  │
│  └──────────┘  └──────────┘  └──────────────┘  │
│                                                 │
│  Agents: Classification · Extraction ·          │
│          Application · Reply (LangChain)        │
│  LLM: DeepSeek (extensible)                     │
│  DB: MySQL 8 + SQLite (checkpoints)             │
└─────────────────────────────────────────────────┘
```

## 快速开始

### 环境要求

- **Python** 3.11+
- **Node.js** 18+
- **MySQL** 8.0+
- **DeepSeek API Key**（[platform.deepseek.com](https://platform.deepseek.com) 获取）

### 1. 克隆项目

```bash
git clone https://github.com/satzu0228/job-mail-agent.git
cd job-mail-agent
```

### 2. 配置后端

```bash
cd backend
python -m pip install -e ".[dev]"

# 复制并编辑环境变量
cp .env.example .env
# 编辑 .env，至少修改以下一项：
#   JOB_MAIL_DATABASE_URL  → 你的 MySQL 连接串
#   JOB_MAIL_LLM_API_KEY   → 可选；DeepSeek API Key 也可启动后在「设置 > AI 模型」页面填写

# 初始化数据库（自动建表）
alembic upgrade head
```

### 3. 启动后端

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173`，在「邮箱设置」页面添加邮箱账户，系统将自动开始同步。

## 配置说明

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `JOB_MAIL_DATABASE_URL` | MySQL 连接串 | `mysql+pymysql://job_mail:...@127.0.0.1:3306/job_mail_agent` |
| `JOB_MAIL_LLM_PROVIDER` | LLM 供应商（当前支持 `deepseek`） | `deepseek` |
| `JOB_MAIL_LLM_MODEL` | 模型名称 | `deepseek-chat` |
| `JOB_MAIL_LLM_API_KEY` | LLM API Key（可改用界面配置：设置 > AI 模型） | —（可选） |
| `JOB_MAIL_CHECKPOINT_ENCRYPTION_KEY` | Checkpoint 加密密钥（AES-256 十六进制） | —（必填） |
| `JOB_MAIL_EMAIL_CREDENTIAL_ENCRYPTION_KEY` | 邮箱授权码加密密钥 | —（必填） |
| `JOB_MAIL_AUTOMATION_ENABLED` | 启用自动同步轮询 | `true` |
| `JOB_MAIL_AUTOMATION_POLL_SECONDS` | 轮询间隔（秒） | `30` |

完整配置项见 `.env.example`。

## 使用流程

1. **添加邮箱**：在「邮箱设置」页面填写 IMAP/SMTP 信息和邮箱授权码
2. **同步邮件**：系统自动通过 IMAP 拉取并解析邮件
3. **智能处理**：在邮件详情页点击「启动智能处理」，LLM 自动分类、抽取信息、匹配申请
4. **审核决策**：在「审核中心」查看 AI 建议，批准/拒绝/一键批准
5. **追踪进度**：在「求职进度」和「日程」页面查看面试安排和申请状态

## 技术栈

| 层面 | 技术 |
|------|------|
| **后端框架** | FastAPI |
| **工作流引擎** | LangGraph（带加密 checkpoint 持久化） |
| **LLM** | DeepSeek（LangChain 集成，架构支持扩展其他供应商） |
| **数据库** | MySQL 8 + SQLAlchemy + Alembic |
| **前端** | Vue 3 + TypeScript + Vite + Element Plus |
| **邮件协议** | IMAP（收件）+ SMTP（发件） |
| **测试** | pytest + Playwright |

## 项目结构

```text
job-mail-agent/
├── backend/                         # FastAPI 后端
│   ├── app/
│   │   ├── agents/                  # LLM Agent（分类/抽取/匹配/回复）
│   │   ├── application/             # 应用服务层
│   │   ├── workflows/               # LangGraph 工作流
│   │   ├── infrastructure/          # DB 模型、LLM 工厂、邮件格式化
│   │   └── api/v1/endpoints/        # REST API 路由
│   ├── migrations/                  # Alembic 数据库迁移
│   └── tests/                       # 后端测试
├── frontend/                        # Vue 3 前端
│   └── src/
│       ├── views/                   # 页面组件
│       ├── api/                     # API 调用层
│       └── types/                   # TypeScript 类型定义
└── docs/                            # 项目文档
```

## License

MIT
