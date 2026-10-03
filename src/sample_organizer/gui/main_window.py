from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar,
                               QPushButton, QPlainTextEdit, QTableView, QVBoxLayout, QWidget)

from ..models import ScanResult
from ..cancellation import CancellationToken
from ..organizer import destination_for
from .results_model import ResultsFilter, ResultsModel
from .workers import OrganizationWorker, ScanWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sample Organizer")
        self.resize(1100, 720)
        self.source = Path.home() / "Music" / "Samples"
        self.destination = Path.home() / "Music" / "SamplesOrdenados"
        self.result: ScanResult | None = None
        self.thread: QThread | None = None
        self.worker = None
        self.cancellation: CancellationToken | None = None
        self._last_log_at = 0.0
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        paths = QGroupBox("Carpetas")
        grid = QGridLayout(paths)
        self.source_label = QLabel(str(self.source))
        self.destination_label = QLabel(str(self.destination))
        self.source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.destination_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        source_button = QPushButton("Seleccionar…")
        dest_button = QPushButton("Seleccionar…")
        source_button.clicked.connect(lambda: self._select_folder(True))
        dest_button.clicked.connect(lambda: self._select_folder(False))
        grid.addWidget(QLabel("Carpeta a ordenar"), 0, 0)
        grid.addWidget(self.source_label, 0, 1)
        grid.addWidget(source_button, 0, 2)
        grid.addWidget(QLabel("Carpeta de destino"), 1, 0)
        grid.addWidget(self.destination_label, 1, 1)
        grid.addWidget(dest_button, 1, 2)
        layout.addWidget(paths)

        actions = QHBoxLayout()
        self.analyze_button = QPushButton("Analizar")
        self.organize_button = QPushButton("Organizar")
        self.stop_button = QPushButton("Detener tarea")
        self.organize_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.delete_pending = QCheckBox("Eliminar .part, .lrc y archivos auxiliares macOS (confirmación)")
        self.analyze_button.clicked.connect(self._analyze)
        self.organize_button.clicked.connect(self._organize)
        self.stop_button.clicked.connect(self._stop_task)
        actions.addWidget(self.analyze_button)
        actions.addWidget(self.organize_button)
        actions.addWidget(self.stop_button)
        actions.addWidget(self.delete_pending)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.summary = QLabel("Selecciona las carpetas y pulsa Analizar. El análisis no modifica archivos.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.activity = QLabel("Listo para analizar. No se han leído ni modificado archivos.")
        self.activity.setWordWrap(True)
        layout.addWidget(self.activity)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Mostrar:"))
        self.filter_box = QComboBox()
        self.filter_box.addItems(["Todos", "Unclassified", "Confianza baja", "Pendientes de eliminación",
                                  ".part", ".lrc", "Archivos macOS", "Duplicados"])
        self.filter_box.currentTextChanged.connect(self._refresh_table)
        filter_row.addWidget(self.filter_box)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)
        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.model = ResultsModel()
        self.table.setModel(self.model)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 220)
        layout.addWidget(self.table, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(300)
        self.log.setMaximumHeight(100)
        layout.addWidget(self.log)
        self.setCentralWidget(central)

    def _select_folder(self, source: bool):
        current = self.source if source else self.destination
        selected = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta", str(current))
        if selected:
            if source:
                self.source = Path(selected)
                self.source_label.setText(selected)
            else:
                self.destination = Path(selected)
                self.destination_label.setText(selected)
            self.result = None
            self.organize_button.setEnabled(False)

    def _analyze(self):
        self.result = None
        self.cancellation = CancellationToken()
        self._set_busy(True)
        self.activity.setText("Preparando el análisis de solo lectura…")
        self.log.appendPlainText("Iniciando análisis de solo lectura…")
        self.thread = QThread(self)
        worker = ScanWorker(self.source, self.destination, self.cancellation)
        self.worker = worker
        worker.moveToThread(self.thread)
        self.thread.started.connect(worker.run)
        worker.progress.connect(self._progress)
        worker.finished.connect(self._scan_finished)
        worker.failed.connect(self._failed)
        worker.cancelled.connect(self._scan_cancelled)
        worker.finished.connect(self.thread.quit)
        worker.failed.connect(self.thread.quit)
        worker.cancelled.connect(self.thread.quit)
        self.thread.finished.connect(worker.deleteLater)
        self.thread.finished.connect(self._worker_finished)
        self.thread.start()

    def _scan_finished(self, result: ScanResult):
        self.result = result
        self._refresh_table()
        summary = result.summary()
        self.summary.setText(
            f"Archivos: {summary['files_found']}  ·  One Shots: {summary['one_shots']}  ·  "
            f"Loops: {summary['loops']}  ·  MIDI: {summary['midi']}  ·  "
            f"Sin clasificar: {summary['unclassified']}  ·  .part: {summary['part']}  ·  "
            f".lrc: {summary['lrc']}  ·  Pendientes: {summary['pending_deletion']}  ·  "
            f"Metadatos macOS: {summary['macos_metadata']}  ·  "
            f"Duplicados exactos: {summary['duplicates']}  ·  Otros: {summary['other']}  ·  "
            f"Comprimidos: {summary['archives']}"
        )
        self.organize_button.setEnabled(True)
        self.activity.setText(f"Análisis terminado: {summary['files_found']} archivos revisados. Ya puedes revisar los resultados.")
        self.log.appendPlainText(f"Análisis terminado. Errores de lectura: {len(result.errors)}")
        self._set_busy(False)

    def _scan_cancelled(self):
        self.result = None
        self.model = ResultsModel()
        self.table.setModel(self.model)
        self.summary.setText("Análisis detenido. No se modificó ningún archivo.")
        self.activity.setText("Tarea detenida por el usuario.")
        self.log.appendPlainText("Análisis cancelado; el origen no se modificó.")
        self._set_busy(False)

    def _refresh_table(self):
        if self.result is None:
            return
        selection = self.filter_box.currentText()
        records = [r for r in self.result.records if ResultsFilter.accepts(r, selection)]
        self.model = ResultsModel(records, str(self.destination))
        self.table.setModel(self.model)
        self.table.setColumnWidth(0, 220)
        self.table.horizontalHeader().setStretchLastSection(True)

    def _organize(self):
        if not self.result:
            return
        count = sum(r.kind in {"audio", "midi"} for r in self.result.records)
        part_count = sum(r.is_part for r in self.result.records)
        lrc_count = sum(r.is_lrc for r in self.result.records)
        macos_count = sum(r.is_macos_metadata for r in self.result.records)
        answer = QMessageBox.question(
            self, "Confirmar organización",
            f"Se copiarán hasta {count} archivos musicales a:\n{self.destination}\n\n"
            f"Se encontraron {part_count} archivos .part, {lrc_count} .lrc y {macos_count} "
            f"archivos auxiliares macOS. ¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        delete_pending = False
        if self.delete_pending.isChecked() and (part_count or lrc_count or macos_count):
            answer = QMessageBox.warning(
                self, "Confirmar eliminación de archivos pendientes",
                f"Se eliminarán permanentemente {part_count} archivos .part, {lrc_count} .lrc y "
                f"{macos_count} archivos auxiliares macOS "
                "del origen. Esta acción no se puede deshacer. ¿Confirmas?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            delete_pending = answer == QMessageBox.StandardButton.Yes
        pending_count = part_count + lrc_count + macos_count
        self.cancellation = CancellationToken()
        self._set_busy(True, total=count + pending_count)
        self.activity.setText("Copiando archivos y preparando los informes…")
        self.log.appendPlainText("Iniciando copia…")
        self.thread = QThread(self)
        worker = OrganizationWorker(self.result, self.destination, delete_pending, self.cancellation)
        self.worker = worker
        worker.moveToThread(self.thread)
        self.thread.started.connect(worker.run)
        worker.progress.connect(self._progress)
        worker.finished.connect(self._organization_finished)
        worker.failed.connect(self._failed)
        worker.finished.connect(self.thread.quit)
        worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(worker.deleteLater)
        self.thread.finished.connect(self._worker_finished)
        self.thread.start()

    def _worker_finished(self):
        self.worker = None

    def _organization_finished(self, outcome):
        if outcome.cancelled:
            self.activity.setText("Organización detenida. Las copias completadas se conservaron.")
        else:
            self.activity.setText("Organización terminada. Revisa el registro y los informes en la carpeta de destino.")
        self.log.appendPlainText(f"Copia completada: {outcome.copied}; eliminados .part: {outcome.deleted_parts}; "
                                 f".lrc: {outcome.deleted_lrc}; metadatos macOS: {outcome.deleted_macos_metadata}")
        if outcome.report_csv and outcome.report_json:
            self.log.appendPlainText(f"Informes: {outcome.report_csv.name} y {outcome.report_json.name}")
        if outcome.errors:
            self.log.appendPlainText(f"Operaciones con error: {len(outcome.errors)}")
        self._set_busy(False)
        title = "Organización detenida" if outcome.cancelled else "Organización terminada"
        state = "La tarea se detuvo; las copias terminadas se conservaron.\n" if outcome.cancelled else ""
        QMessageBox.information(self, title,
                                f"{state}Copiados: {outcome.copied}\n.part eliminados: {outcome.deleted_parts}\n"
                                f".lrc eliminados: {outcome.deleted_lrc}\n"
                                f"Archivos auxiliares macOS eliminados: {outcome.deleted_macos_metadata}\n"
                                f"Errores: {len(outcome.errors)}")

    def _progress(self, count: int, message: str):
        self.activity.setText(message)
        if self.progress.maximum() > 0:
            self.progress.setValue(min(count, self.progress.maximum()))
        else:
            self.progress.setFormat("Trabajando…")
        now = time.monotonic()
        important = message.startswith(("Escaneo completo", "Comparando duplicados", "Análisis finalizado"))
        if important or (count % 25 == 0 and now - self._last_log_at >= 1.0):
            self.log.appendPlainText(message)
            self._last_log_at = now

    def _stop_task(self):
        if self.cancellation is None:
            return
        self.cancellation.cancel()
        self.stop_button.setEnabled(False)
        self.activity.setText("Solicitando detener la tarea de forma segura…")

    def _failed(self, message: str):
        self._set_busy(False)
        self.activity.setText("El análisis no pudo completarse. Consulta el mensaje de error.")
        self.log.appendPlainText("Error: " + message)
        QMessageBox.critical(self, "No se pudo completar", message)

    def _set_busy(self, busy: bool, total: int = 0):
        self.progress.setVisible(busy)
        self.progress.setRange(0, total if total else 0)
        self.progress.setValue(0)
        self.progress.setFormat("%v / %m" if total else "Procesando…")
        self.analyze_button.setEnabled(not busy)
        self.organize_button.setEnabled(not busy and self.result is not None)
        self.stop_button.setEnabled(busy and self.cancellation is not None
                                    and not self.cancellation.cancelled)
