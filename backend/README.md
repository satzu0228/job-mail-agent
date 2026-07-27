# Backend

正式系统的 FastAPI 后端。当前已建立应用入口、版本化路由、配置、SQLAlchemy
Session、Alembic 环境和基础测试；12 张业务表将在下一步按数据库设计分批实现。

数据库字段和迁移顺序以
[`../docs/database/database-er-design.md`](../docs/database/database-er-design.md) 为准。

## 本地运行

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

打开：

- API 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/api/v1/health>

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
pytest
ruff check .
```
