# Backend

正式系统的 FastAPI 后端。当前已建立应用入口、版本化路由、配置、SQLAlchemy
Session、Alembic 环境和基础测试，并完成 12 张核心业务表与三批迁移。邮件查询、
求职记录、任务和回复草稿基础 API 已建立；关键申请阶段、草稿批准和外部动作仍
必须通过后续审核流程，普通 PATCH 不提供绕过入口。Classification 与 Extraction
的版本化 Pydantic Schema、Prompt、正式 Agent 和 DeepSeek 模型适配已经建立。
面试邀请、拒信和非求职促销三个脱敏 Fixture 的真实模型调用均已通过。
邮箱账户配置、IMAP/SMTP 连接测试、INBOX 有界增量同步、MIME/HTML 安全解析及
幂等入库已经实现。单封邮件分类、抽取、统一分析 API 和分析结果版本化持久化
也已完成。第六阶段已增加确定性申请候选评分、Application Agent、申请状态机和
人工审核执行链路；模型建议不会直接关联申请或修改关键阶段。第七阶段已增加
LangGraph 强类型工作流、Validation Node、SQLite checkpoint、申请处理的两段人工
中断恢复、运行轨迹以及工作流启动和查询 API。第八阶段已增加 Reply Agent、确定性邮件
Formatter、草稿高风险审核、第三段可恢复中断和 SMTP 幂等 Executor；Agent 与
LangGraph 均不能直接发送邮件。

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
- 单封分类：`POST /api/v1/emails/{id}/classify`
- 单封抽取：`POST /api/v1/emails/{id}/extract`
- 统一分析：`POST /api/v1/emails/{id}/analyze`
- 申请匹配：`POST /api/v1/emails/{id}/match-application`
- 启动工作流：`POST /api/v1/emails/{id}/workflow-runs`
- 查询工作流：`GET /api/v1/workflow-runs/{run_id}`
- 求职记录：<http://127.0.0.1:8000/api/v1/job-applications>
- 审核任务：<http://127.0.0.1:8000/api/v1/review-tasks>
- 任务日程：<http://127.0.0.1:8000/api/v1/tasks>
- 回复草稿：<http://127.0.0.1:8000/api/v1/reply-drafts>
- 生成回复：`POST /api/v1/emails/{id}/generate-reply`
- 发送已审核草稿：`POST /api/v1/reply-drafts/{id}/send`

配置 `JOB_MAIL_LLM_API_KEY` 后，可使用脱敏邮件执行一次真实分类与抽取：

```powershell
python -m app.cli.analyze_fixture ..\tests\fixtures\emails\interview_invitation.json
```

启动第七阶段工作流前还必须配置 checkpoint AES 密钥。密钥为 16、24 或 32 字节，
在环境变量中使用十六进制表示；例如生成 32 字节随机密钥：

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

将输出写入本地 `.env` 的 `JOB_MAIL_CHECKPOINT_ENCRYPTION_KEY`，不得提交真实值。

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
