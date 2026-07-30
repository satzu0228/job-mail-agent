from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Event, Thread

logger = logging.getLogger(__name__)


class PollingScheduler:
    def __init__(
        self,
        callback: Callable[[], object],
        *,
        interval_seconds: float,
    ) -> None:
        self._callback = callback
        self._interval_seconds = interval_seconds
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(
            target=self._run,
            name="job-mail-automation",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=min(self._interval_seconds + 1, 10))
        self._thread = None

    def _run(self) -> None:
        # 延迟首轮，避免应用启动探针和迁移尚未完成时访问业务表。
        while not self._stop_event.wait(self._interval_seconds):
            try:
                self._callback()
            except Exception:
                logger.exception("自动同步轮询失败")
