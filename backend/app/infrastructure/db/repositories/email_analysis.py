from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models.email import Email
from app.infrastructure.db.models.email_analysis import EmailAnalysis


class EmailNotFoundError(LookupError):
    pass


class EmailAnalysisRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_version(self, analysis: EmailAnalysis) -> EmailAnalysis:
        """锁定邮件并切换当前版本，调用方负责事务提交或回滚。"""
        email_exists = self._session.scalar(
            select(Email.id).where(Email.id == analysis.email_id).with_for_update()
        )
        if email_exists is None:
            raise EmailNotFoundError(f"Email {analysis.email_id} does not exist")

        existing = list(
            self._session.scalars(
                select(EmailAnalysis)
                .where(EmailAnalysis.email_id == analysis.email_id)
                .order_by(EmailAnalysis.version.desc())
            )
        )
        for item in existing:
            item.is_current = False

        analysis.version = existing[0].version + 1 if existing else 1
        analysis.is_current = True
        self._session.add(analysis)
        self._session.flush()
        return analysis
