from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from ..cancellation import CancellationToken, TaskCancelled
from ..models import ScanResult
from ..organizer import organize
from ..scanner import scan


class ScanWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, source: Path, destination: Path, cancellation: CancellationToken):
        super().__init__()
        self.source, self.destination = source, destination
        self.cancellation = cancellation

    @Slot()
    def run(self):
        try:
            self.finished.emit(scan(self.source, self.destination, self.progress.emit,
                                    cancellation=self.cancellation))
        except TaskCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class OrganizationWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, result: ScanResult, destination: Path, delete_pending: bool,
                 cancellation: CancellationToken):
        super().__init__()
        self.result, self.destination, self.delete_pending = result, destination, delete_pending
        self.cancellation = cancellation

    @Slot()
    def run(self):
        try:
            self.finished.emit(organize(self.result, self.destination, delete_pending=self.delete_pending,
                                        progress=self.progress.emit, cancellation=self.cancellation))
        except Exception as exc:
            self.failed.emit(str(exc))
