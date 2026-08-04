"""ApplicationAgent 的工具函数。

每个工具通过 RunnableConfig 获取运行时 user_id，
Agent 初始化时不绑定用户，同一个 Agent 实例可安全复用于多用户请求。
"""

from __future__ import annotations

from collections.abc import Callable

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.infrastructure.db.repositories import (
    EmailRepository,
    JobApplicationRepository,
)


def create_application_tools(
    session_factory: Callable[[], Session],
) -> list:
    """创建 ApplicationAgent 的工具集。

    Args:
        session_factory: 每次工具调用时创建新的 DB 会话，
                         工具内自行管理会话生命周期。
    """

    @tool
    def search_application(
        keyword: str,
        config: RunnableConfig,
    ) -> list[dict]:
        """搜索用户申请列表中匹配关键词的求职申请。

        按更新时间降序返回前 10 条匹配结果，每条包含 id、公司、岗位、阶段和状态。

        Args:
            keyword: 搜索关键词，匹配公司名称、别名和岗位名称。
        """
        user_id = config["configurable"]["user_id"]
        with session_factory() as session:
            repo = JobApplicationRepository(session, user_id)
            apps, _ = repo.query(keyword=keyword, offset=0, limit=10)
            return [
                {
                    "id": a.id,
                    "company_name": a.company_name,
                    "position_name": a.position_name,
                    "current_stage": a.current_stage.value if a.current_stage else None,
                    "status": a.status.value if a.status else None,
                    "contact_email": a.contact_email,
                }
                for a in apps
            ]

    @tool
    def get_application_detail(
        application_id: int,
        config: RunnableConfig,
    ) -> dict:
        """获取单个求职申请的完整信息，包括事件时间线。

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
                "created_at": app.created_at.isoformat() if app.created_at else None,
                "updated_at": app.updated_at.isoformat() if app.updated_at else None,
                "recent_events": [
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
    def get_email_history(
        application_id: int,
        config: RunnableConfig,
    ) -> list[dict]:
        """获取该求职申请关联的历史邮件摘要（标题、日期、分类）。

        按接收时间降序返回最近 10 封。

        Args:
            application_id: 申请 ID。
        """
        user_id = config["configurable"]["user_id"]
        with session_factory() as session:
            emails, _ = EmailRepository(session, user_id).query(
                application_id=application_id,
                offset=0,
                limit=10,
            )
            return [
                {
                    "id": e.id,
                    "subject": e.subject,
                    "from_address": e.from_address,
                    "from_name": e.from_name,
                    "received_at": e.received_at.isoformat() if e.received_at else None,
                    "has_analysis": e.current_analysis is not None,
                    "category": (
                        e.current_analysis.category.value
                        if e.current_analysis and e.current_analysis.category
                        else None
                    ),
                }
                for e in emails
            ]

    return [search_application, get_application_detail, get_email_history]
