# 求职邮迹 — Job Mail Agent

**基于大语言模型与多智能体协作的求职邮件智能管理系统。**

连接你的邮箱，自动识别求职邮件、提取面试信息、关联求职申请、生成回复草稿——所有关键操作经过你的人工审核后才执行。

## 功能概览

| 功能 | 说明 |
|------|------|
| 📬 **邮件同步** | 通过 IMAP 连接邮箱，自动同步邮件并解析正文 |
| 🤖 **智能分类与抽取** | LLM 自动识别邮件类型（面试/Offer/拒信等），抽取公司、岗位、时间、地点、会议链接等结构化信息 |
| 🔗 **求职申请匹配** | 将邮件自动关联到对应的求职申请，或建议新建申请 |
| 📅 **面试日程** | 自动提取面试时间并创建日程，页面内展示即将到期的提醒 |
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
- **邮箱账号**：支持 IMAP 收件 + SMTP 发件（QQ 邮箱、163、Gmail 等均可）

### 1. 克隆项目

```bash
git clone https://github.com/satzu0228/job-mail-agent.git
cd job-mail-agent
```

### 2. 创建 MySQL 数据库

登录 MySQL 并执行：

```sql
CREATE DATABASE job_mail_agent CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'job_mail'@'127.0.0.1' IDENTIFIED BY '你的密码';
GRANT ALL PRIVILEGES ON job_mail_agent.* TO 'job_mail'@'127.0.0.1';
FLUSH PRIVILEGES;
```

### 3. 配置后端

```bash
cd backend
python -m pip install -e ".[dev]"

# 复制环境变量模板
cp .env.example .env
```

编辑 `.env`，修改以下配置项：

```bash
# ① 数据库连接（必填）—— 替换为第 2 步设置的密码
JOB_MAIL_DATABASE_URL=mysql+pymysql://job_mail:你的密码@127.0.0.1:3306/job_mail_agent?charset=utf8mb4

# ② 加密密钥（必填）—— 用以下命令生成两对密钥：
#    python -c "import secrets; print(secrets.token_hex(16))"
JOB_MAIL_CHECKPOINT_ENCRYPTION_KEY=   # 填入生成的 32 位十六进制字符串
JOB_MAIL_EMAIL_CREDENTIAL_ENCRYPTION_KEY=  # 填入另一对生成的密钥
```

生成加密密钥的命令（在终端执行）：

```bash
python -c "import secrets; print(secrets.token_hex(16))"
```

> 执行两次，分别填入 `JOB_MAIL_CHECKPOINT_ENCRYPTION_KEY` 和 `JOB_MAIL_EMAIL_CREDENTIAL_ENCRYPTION_KEY`。**请勿使用示例中的 "replace-with-…" 值，务必生成自己的密钥。**

初始化数据库表：

```bash
alembic upgrade head
```

### 4. 启动后端

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 6. 添加邮箱

1. 打开 `http://localhost:5173`
2. 进入「设置>邮箱账户」页面，添加邮箱账户
3. 填写 IMAP/SMTP 服务器信息和**邮箱授权码**

> **关于邮箱授权码**：主流邮箱（QQ、163、Gmail）出于安全考虑，不允许直接用登录密码连接第三方客户端。你需要在邮箱设置中单独生成一个"授权码"（或称应用专用密码）：

### 7. 配置 AI 模型

1. 进入「设置 > AI 模型」页面
2. 点击「添加配置」，粘贴从 [platform.deepseek.com](https://platform.deepseek.com) 获取的 **DeepSeek API Key**
3. 系统会自动测试连接，通过后启用该配置

> **关于用户系统**：当前为个人使用设计，采用单用户模式（默认 `demo_user_id=1`）。无需注册或登录——启动后即可以该用户身份使用全部功能。

添加邮箱并配置 API Key 后，系统将自动开始同步邮件。

## 配置说明

以下为常用配置项，完整列表见 `.env.example`。

### 必填

| 环境变量 | 说明 |
|---------|------|
| `JOB_MAIL_DATABASE_URL` | MySQL 连接串，格式 `mysql+pymysql://用户:密码@主机:端口/库名` |
| `JOB_MAIL_CHECKPOINT_ENCRYPTION_KEY` | LangGraph 状态加密密钥（16 字节，32 位十六进制） |
| `JOB_MAIL_EMAIL_CREDENTIAL_ENCRYPTION_KEY` | 邮箱授权码存储加密密钥（16 字节，32 位十六进制） |

### 可选

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `JOB_MAIL_REMINDER_LEAD_MINUTES` | 日程提前多久生成提醒（分钟） | `60` |
| `JOB_MAIL_DEMO_USER_ID` | 单用户模式的用户 ID | `1` |

> **LLM 参数、邮箱自动同步等均在页面配置**，无需通过环境变量设置。

## 使用流程

1. **添加邮箱 & 配置 API Key**：在「邮箱设置」页面连接邮箱，在「AI 模型」页面填入 DeepSeek API Key（仅需一次）
2. **自动同步 & 智能处理**：系统定时拉取新邮件，自动调用 LLM 分类、抽取信息、匹配求职申请——处理完成后暂停等待审核
3. **审核决策**：在「审核中心」查看 AI 建议，批准/拒绝/一键批准
4. **追踪进度**：在「求职进度」和「日程」页面查看面试安排和申请状态

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
