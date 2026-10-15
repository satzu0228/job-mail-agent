from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from sqlalchemy.orm import Session

from app.application.email_access import EmailAccessService
from app.application.schemas import MailboxProcessingResult


class WorkflowStarter(Protocol):
    def __call__(self, email_id: int) -> object: ...


class SyncAndProcessMailbox:
    """统一完成邮箱同步及新邮件工作流启动。"""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        email_access_factory: Callable[[Session], EmailAccessService],
        workflow_starter: WorkflowStarter,
    ) -> None:
        self._session_factory = session_factory
        self._email_access_factory = email_access_factory
        self._workflow_starter = workflow_starter

    def execute(
        self,
        account_id: int,
        *,
        limit: int | None = None,
    ) -> MailboxProcessingResult:
        with self._session_factory() as session:
            sync_result = self._email_access_factory(session).sync(
                account_id,
                limit=limit,
            )

        workflow_run_ids: list[str] = []
        failed_workflows: dict[int, str] = {}
        for email_id in sync_result.created_email_ids:
            try:
                run = self._workflow_starter(email_id)
                run_id = getattr(run, "id", None)
                if isinstance(run_id, str):
                    workflow_run_ids.append(run_id)
            except Exception as exc:
                # 单封模型失败不阻塞同批邮件；工作流内部仍负责记录自身错误。
                failed_workflows[email_id] = str(exc)[:500]

        return MailboxProcessingResult(
            **sync_result.model_dump(),
            workflow_run_ids=workflow_run_ids,
            failed_workflows=failed_workflows,
        )
