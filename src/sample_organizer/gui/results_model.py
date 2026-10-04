from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from ..models import SampleRecord
from ..organizer import destination_for


class ResultsModel(QAbstractTableModel):
    HEADERS = ["Archivo", "Tipo", "Categoría", "Librería", "Confianza", "Destino"]

    def __init__(self, records: list[SampleRecord] | None = None, destination: str = ""):
        super().__init__()
        self.records = records or []
        self.destination = destination

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.records)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        record = self.records[index.row()]
        relative = destination_for(record)
        try:
            target = str(Path(self.destination) / relative) if relative else "—"
        except ValueError:
            target = "Destino manual no válido"
        values = [record.filename, record.family,
                  record.category or ("Metadatos macOS pendientes de eliminación"
                                      if record.is_macos_metadata else
                                      f"{record.extension} pendiente de eliminación"
                                      if record.is_pending_deletion else ""), record.library,
                  record.confidence, target]
        return values[index.column()]

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None


class ResultsFilter:
    """Predicate kept separate to make the UI filter states explicit."""
    @staticmethod
    def accepts(record: SampleRecord, selection: str) -> bool:
        if selection == "Unclassified":
            return record.family == "Unclassified"
        if selection == "Confianza baja":
            return record.confidence == "low"
        if selection == ".part":
            return record.is_part
        if selection == ".lrc":
            return record.is_lrc
        if selection == "Archivos macOS":
            return record.is_macos_metadata
        if selection == "Pendientes de eliminación":
            return record.is_pending_deletion
        if selection == "Duplicados":
            return bool(record.duplicate_of)
        return True
