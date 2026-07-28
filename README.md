# Job Mail Agent

毕业设计：**基于大语言模型与多智能体协作的求职邮件智能管理系统设计与实现**。

第一阶段的参考项目运行与分析已经完成，MVP、架构和数据库逻辑 ER 已收敛。
FastAPI 后端骨架以及 `users`、`email_accounts`、`job_applications`、`emails`
四个 ORM 模型和首批 Alembic 迁移已经实现，并已在本地 MySQL 8 成功执行首次
`upgrade head`、`current` 和 `check`。Classification 和 Extraction 的正式 Agent、
DeepSeek 模型适配、版本化 Prompt 以及首批脱敏邮件 Fixture 已实现，三封 Fixture
的真实模型基线均已通过。下一步是接入分析结果持久化。项目背景和长期协作约定见
[AGENTS.md](AGENTS.md)。

当前已完成第二阶段“冻结 MVP 边界并搭建项目骨架”，正在进行第三阶段“设计数据库
并建立基础接口”。

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
├── frontend/                       # 正式 Vue 3 前端（后续创建）
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

## 第一阶段参考项目

在项目根目录执行：

```powershell
git clone https://github.com/parthshr370/Email-AI-Agent.git references/Email-AI-Agent
```

第一阶段已经完成。需要复现时，先查看 [参考项目登记表](references/README.md) 和
[第一阶段清单](docs/phase-1/README.md)。

不要把 API Key、邮箱密码、授权码或包含个人信息的真实邮件提交到仓库。
