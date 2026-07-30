"""在此导入 ORM 模型，确保 Alembic 能发现完整元数据。"""

from app.infrastructure.db.models.action_execution import ActionExecution
from app.infrastructure.db.models.application_event import ApplicationEvent
from app.infrastructure.db.models.automation_rule import AutomationRule
from app.infrastructure.db.models.email import Email
from app.infrastructure.db.models.email_account import EmailAccount
from app.infrastructure.db.models.email_analysis import EmailAnalysis
from app.infrastructure.db.models.job_application import JobApplication
from app.infrastructure.db.models.reminder import Reminder
from app.infrastructure.db.models.reply_draft import ReplyDraft
from app.infrastructure.db.models.review_task import ReviewTask
from app.infrastructure.db.models.task import Task
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.workflow_run import WorkflowRun

__all__ = [
    "ActionExecution",
    "ApplicationEvent",
    "AutomationRule",
    "Email",
    "EmailAccount",
    "EmailAnalysis",
    "JobApplication",
    "ReplyDraft",
    "Reminder",
    "ReviewTask",
    "Task",
    "User",
    "WorkflowRun",
]
