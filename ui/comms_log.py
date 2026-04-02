import csv
from datetime import datetime
from typing import List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

_TX_BG = QColor("#0a1a3d")
_RX_BG = QColor("#0d2b14")
_MAX_ROWS = 20_000


class CommsLog(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: List[Tuple[str, str, str]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        controls = QHBoxLayout()
        self._chk_autoscroll = QCheckBox("Auto-scroll")
        self._chk_autoscroll.setChecked(True)
        self._btn_clear = QPushButton("Clear")
        self._btn_export = QPushButton("Export Log")
        self._btn_clear.clicked.connect(self.clear_log)
        self._btn_export.clicked.connect(self._on_export)
        controls.addWidget(self._chk_autoscroll)
        controls.addStretch()
        controls.addWidget(self._btn_clear)
        controls.addWidget(self._btn_export)
        layout.addLayout(controls)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Timestamp", "Dir", "Data"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._table)

    def append_entry(self, direction: str, text: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S.") + f"{datetime.now().microsecond // 1000:03d}"
        row = self._table.rowCount()
        if row >= _MAX_ROWS:
            self._table.removeRow(0)
            self._entries.pop(0)
            row = self._table.rowCount()

        self._table.insertRow(row)
        bg = _TX_BG if direction == "Tx" else _RX_BG
        for col, value in enumerate([ts, direction, text]):
            item = QTableWidgetItem(value)
            item.setBackground(bg)
            item.setForeground(Qt.GlobalColor.white)
            self._table.setItem(row, col, item)

        self._entries.append((ts, direction, text))

        if self._chk_autoscroll.isChecked():
            self._table.scrollToBottom()

    def clear_log(self) -> None:
        self._table.setRowCount(0)
        self._entries.clear()

    def _on_export(self) -> None:
        path, selected_filter = QFileDialog.getSaveFileName(
            self, "Export Log", "", "CSV (*.csv);;Text (*.txt)"
        )
        if not path:
            return
        if "csv" in selected_filter.lower():
            self._export_csv(path)
        else:
            self._export_txt(path)

    def _export_csv(self, path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Direction", "Data"])
            writer.writerows(self._entries)

    def _export_txt(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for ts, direction, text in self._entries:
                f.write(f"[{ts}] [{direction}] {text}\n")
