# Job Mail Agent

毕业设计：**基于大语言模型与多智能体协作的求职邮件智能管理系统设计与实现**。

当前前十阶段已经完成：MVP 与架构边界、13 张
业务表、邮件同步与安全解析、四个核心 Agent、三段可恢复人工审核、回复草稿与
SMTP 幂等发送均已实现。Vue 3 前端现已提供邮件、求职进度、日程、审核和邮箱
设置五个核心页面，并接通现有 FastAPI 接口。第十阶段已增加可配置的 5～60 分钟
自动同步、新邮件工作流触发和到期前系统内部提醒。
项目背景和长期协作约定见
[AGENTS.md](AGENTS.md)。

第十一阶段系统测试正在执行，当前自动化基线和未通过边界见
[系统测试进展](docs/phase-11/system-test-progress.md)。

全部文档按职责分类，统一从 [项目文档导航](docs/README.md) 进入。

## 当前目录

```text
job-mail-agent/
├── AGENTS.md                       # 项目长期背景与协作规则
├── README.md                       # 项目入口
├── references/                     # 第三方参考项目，不纳入本项目版本历史
├── experiments/email-ai-agent/     # 针对参考项目的独立实验与测试数据
├── docs/                           # 按需求、架构、数据库、计划和阶段记录分类
├── backend/                        # 正式 FastAPI/SQLAlchemy/Alembic 后端
├── frontend/                       # 正式 Vue 3 + TypeScript 前端
└── tests/fixtures/emails/          # 脱敏邮件测试样例
```

## 后端开始方式

```powershell
conda activate job-mail-agent
cd backend
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

详细命令见 [后端说明](backend/README.md)。

## 前端开始方式

```powershell
cd frontend
npm install
npm run dev
```

详细说明见 [前端说明](frontend/README.md)。

## 自动化回归

```powershell
cd backend
python -m ruff check app tests
python -m pytest --cov=app --cov-report=term-missing

cd ..\frontend
npm test
npm run type-check
npm run build
npx playwright install chromium
npm run test:e2e
```

Playwright 失败证据和 HTML 报告输出到根目录 `.artifacts/`，不进入版本控制。

## 第一阶段参考项目

在项目根目录执行：

```powershell
git clone https://github.com/parthshr370/Email-AI-Agent.git references/Email-AI-Agent
```

第一阶段已经完成。需要复现时，先查看 [参考项目登记表](references/README.md) 和
[第一阶段清单](docs/phase-1/README.md)。

不要把 API Key、邮箱密码、授权码或包含个人信息的真实邮件提交到仓库。
