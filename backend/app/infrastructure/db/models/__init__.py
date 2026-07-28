"""在此导入 ORM 模型，确保 Alembic 能发现完整元数据。"""

from app.infrastructure.db.models.email import Email
from app.infrastructure.db.models.email_account import EmailAccount
from app.infrastructure.db.models.job_application import JobApplication
from app.infrastructure.db.models.user import User

__all__ = ["Email", "EmailAccount", "JobApplication", "User"]
