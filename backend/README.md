# Backend

正式系统的 FastAPI 后端。当前已建立应用入口、版本化路由、配置、SQLAlchemy
Session、Alembic 环境和基础测试，并完成 12 张核心业务表与三批迁移。邮件查询、
求职记录、任务和回复草稿基础 API 已建立；关键申请阶段、草稿批准和外部动作仍
必须通过后续审核流程，普通 PATCH 不提供绕过入口。Classification 与 Extraction
的版本化 Pydantic Schema、Prompt、正式 Agent 和 DeepSeek 模型适配已经建立。
面试邀请、拒信和非求职促销三个脱敏 Fixture 的真实模型调用均已通过。
邮箱账户配置、IMAP/SMTP 连接测试、INBOX 有界增量同步、MIME/HTML 安全解析及
幂等入库已经实现。

数据库字段和迁移顺序以
[`../docs/database/database-er-design.md`](../docs/database/database-er-design.md) 为准。

## 本地运行

```powershell
conda activate job-mail-agent
cd backend
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

打开：

- API 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/api/v1/health>
- 邮箱账户：<http://127.0.0.1:8000/api/v1/email-accounts>
- 邮件查询：<http://127.0.0.1:8000/api/v1/emails>
- 求职记录：<http://127.0.0.1:8000/api/v1/job-applications>
- 任务日程：<http://127.0.0.1:8000/api/v1/tasks>
- 回复草稿：<http://127.0.0.1:8000/api/v1/reply-drafts>

配置 `JOB_MAIL_LLM_API_KEY` 后，可使用脱敏邮件执行一次真实分类与抽取：

```powershell
python -m app.cli.analyze_fixture ..\tests\fixtures\emails\interview_invitation.json
```

邮箱账户的 `credential_ref` 只保存环境变量名，例如
`JOB_MAIL_EMAIL_CREDENTIAL_TEST_163`。授权码通过进程环境变量或本地 `.env`
提供，不得放入 API 请求或数据库字段。创建账户后可通过 Swagger 依次调用
`test-connection` 和 `sync`；同步只读 `INBOX`，默认最多处理最近 50 封新邮件。

## Alembic

```powershell
alembic current
alembic revision --autogenerate -m "create core tables"
alembic upgrade head
```

不要使用 `Base.metadata.create_all()` 代替迁移。运行数据库相关命令前，需要先创建
MySQL 数据库并在 `.env` 中设置 `JOB_MAIL_DATABASE_URL`。

## 测试与检查

```powershell
python -m pytest
python -m ruff check .
```
