from __future__ import annotations

from threading import Event


class TaskCancelled(Exception):
    """Raised at safe checkpoints when the user requests a stop."""


class CancellationToken:
    def __init__(self):
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        if self.cancelled:
            raise TaskCancelled
