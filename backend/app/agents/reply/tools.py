"""ReplyAgent 的工具函数。

每个工具通过 RunnableConfig 获取运行时 user_id，
Agent 初始化时不绑定用户。
"""

from __future__ import annotations

from collections.abc import Callable

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.infrastructure.db.models.user import User
from app.infrastructure.db.repositories import (
    EmailRepository,
    JobApplicationRepository,
)


def create_reply_tools(
    session_factory: Callable[[], Session],
) -> list:
    """创建 ReplyAgent 的工具集。"""

    @tool
    def get_user_profile(config: RunnableConfig) -> dict:
        """获取当前用户的个人档案，包括显示名、时区和回复偏好。

        用于在生成回复前了解用户的语言偏好和签名风格。
        """
        user_id = config["configurable"]["user_id"]
        with session_factory() as session:
            user = session.get(User, user_id)
            if user is None:
                return {"error": f"User {user_id} not found"}
            return {
                "display_name": user.display_name,
                "timezone": user.timezone,
                "reply_preferences": user.reply_preferences or {},
            }

    @tool
    def get_application_context(
        application_id: int,
        config: RunnableConfig,
    ) -> dict:
        """获取求职申请的完整上下文，用于写回复时了解申请进度。

        Args:
            application_id: 申请 ID。
        """
        user_id = config["configurable"]["user_id"]
        with session_factory() as session:
            repo = JobApplicationRepository(session, user_id)
            app = repo.get(application_id)
            events, _ = repo.list_events(application_id, offset=0, limit=20)
            return {
                "id": app.id,
                "company_name": app.company_name,
                "position_name": app.position_name,
                "current_stage": app.current_stage.value if app.current_stage else None,
                "status": app.status.value if app.status else None,
                "contact_name": app.contact_name,
                "contact_email": app.contact_email,
                "source": app.source.value if app.source else None,
                "timeline": [
                    {
                        "event_type": e.event_type,
                        "proposed_stage": e.proposed_stage.value if e.proposed_stage else None,
                        "confirmed_stage": e.confirmed_stage.value if e.confirmed_stage else None,
                        "event_at": e.event_at.isoformat() if e.event_at else None,
                    }
                    for e in events[:10]
                ],
            }

    @tool
    def search_previous_conversation(
        application_id: int,
        config: RunnableConfig,
    ) -> list[dict]:
        """查找该申请的历史往来邮件，用于生成回复时避免重复或矛盾。

        返回最近 5 封关联邮件的摘要，包括发件人、主题、日期和分类。

        Args:
            application_id: 申请 ID。
        """
        user_id = config["configurable"]["user_id"]
        with session_factory() as session:
            emails, _ = EmailRepository(session, user_id).query(
                application_id=application_id,
                offset=0,
                limit=5,
            )
            return [
                {
                    "id": e.id,
                    "subject": e.subject,
                    "from_address": e.from_address,
                    "from_name": e.from_name,
                    "received_at": e.received_at.isoformat() if e.received_at else None,
                    "category": (
                        e.current_analysis.category.value
                        if e.current_analysis and e.current_analysis.category
                        else None
                    ),
                    "summary": (
                        e.current_analysis.summary
                        if e.current_analysis
                        else None
                    ),
                }
                for e in emails
            ]

    return [get_user_profile, get_application_context, search_previous_conversation]
