from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QSplitter,
    QToolBar,
    QWidget,
)

from ui.command_panel import CommandPanel
from ui.comms_log import CommsLog
from workers.ssh_bridge import SSHBridge

_STYLE = """
QMainWindow, QWidget { background: #0d1117; color: #c9d1d9; }
QLineEdit, QSpinBox, QDoubleSpinBox {
    background: #161b22; color: #c9d1d9;
    border: 1px solid #30363d; padding: 2px;
}
QPushButton {
    background: #3277ff; color: #fff;
    border: none; padding: 4px 10px; border-radius: 3px;
}
QPushButton:disabled { background: #1c2333; color: #555; }
QPushButton:checked  { background: #1f6feb; }
QGroupBox {
    border: 1px solid #30363d; margin-top: 8px;
    color: #8b949e; font-size: 11px;
}
QGroupBox::title { subcontrol-origin: margin; left: 8px; }
QCheckBox { color: #c9d1d9; }
QScrollArea { border: none; }
QTableWidget {
    background: #0d1117; color: #c9d1d9;
    gridline-color: #30363d; border: 1px solid #30363d;
}
QHeaderView::section {
    background: #161b22; color: #8b949e;
    border: 1px solid #30363d; padding: 3px;
}
"""


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._bridge: Optional[SSHBridge] = None
        self.setWindowTitle("Jasmine Debugger")
        self.setStyleSheet(_STYLE)
        self._build_ui()

    def _build_ui(self) -> None:
        # Toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addWidget(QLabel("  IP:"))
        self._ip_field = QLineEdit("192.168.1.100")
        self._ip_field.setFixedWidth(130)
        toolbar.addWidget(self._ip_field)

        toolbar.addWidget(QLabel("  User:"))
        self._user_field = QLineEdit("silentsentinel")
        self._user_field.setFixedWidth(110)
        toolbar.addWidget(self._user_field)

        toolbar.addWidget(QLabel("  Port:"))
        self._port_field = QSpinBox()
        self._port_field.setRange(1, 65535)
        self._port_field.setValue(22)
        self._port_field.setFixedWidth(80)
        toolbar.addWidget(self._port_field)

        toolbar.addWidget(QLabel("  Pass:"))
        self._pass_field = QLineEdit("Sentinel123")
        self._pass_field.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass_field.setFixedWidth(110)
        toolbar.addWidget(self._pass_field)

        toolbar.addWidget(QLabel("  Baud:"))
        self._baud_combo = QComboBox()
        for rate in (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600):
            self._baud_combo.addItem(str(rate), rate)
        self._baud_combo.setCurrentText("115200")
        toolbar.addWidget(self._baud_combo)

        self._btn_connect = QPushButton("Connect")
        self._btn_connect.clicked.connect(self._on_connect)
        toolbar.addWidget(self._btn_connect)

        self._btn_disconnect = QPushButton("Disconnect")
        self._btn_disconnect.setEnabled(False)
        self._btn_disconnect.clicked.connect(self._on_disconnect)
        toolbar.addWidget(self._btn_disconnect)

        self._status_label = QLabel("Disconnected")
        self._status_label.setSizePolicy(
            self._status_label.sizePolicy().horizontalPolicy(),
            self._status_label.sizePolicy().verticalPolicy(),
        )
        toolbar.addWidget(self._status_label)

        # Body — splitter with command panel left, comms log right
        self._command_panel = CommandPanel()
        self._comms_log = CommsLog()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._command_panel)
        splitter.addWidget(self._comms_log)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        self.setCentralWidget(splitter)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _on_connect(self) -> None:
        self._btn_connect.setEnabled(False)
        self._status_label.setText("Connecting...")

        self._bridge = SSHBridge(
            self._ip_field.text(),
            self._port_field.value(),
            self._user_field.text(),
            self._pass_field.text(),
            baud=self._baud_combo.currentData(),
        )
        self._bridge.connected.connect(self._on_connected)
        self._bridge.disconnected.connect(self._on_disconnected)
        self._bridge.rx_data.connect(lambda t: self._comms_log.append_entry("Rx", t))
        self._bridge.tx_logged.connect(lambda t: self._comms_log.append_entry("Tx", t))
        self._bridge.error.connect(self._on_error)
        self._bridge.status_update.connect(self._status_label.setText)
        self._bridge.status_update.connect(lambda t: self._comms_log.append_entry("---", t))
        self._command_panel.command_requested.connect(self._bridge.send_command)

        self._bridge.start()

    def _on_disconnect(self) -> None:
        if self._bridge is not None:
            self._bridge.stop()

    def _on_connected(self) -> None:
        self._btn_disconnect.setEnabled(True)
        self._command_panel.set_enabled(True)

    def _on_disconnected(self) -> None:
        self._command_panel.set_enabled(False)
        self._btn_connect.setEnabled(True)
        self._btn_disconnect.setEnabled(False)
        self._status_label.setText("Disconnected")
        if self._bridge is not None:
            self._bridge.wait()
        self._bridge = None

    def _on_error(self, msg: str) -> None:
        self._status_label.setText(f"Error: {msg}")
        self._comms_log.append_entry("ERR", msg)
        self._btn_connect.setEnabled(True)
        self._btn_disconnect.setEnabled(False)
        self._command_panel.set_enabled(False)

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        if self._bridge is not None:
            self._bridge.stop()
            self._bridge.wait(3000)
        super().closeEvent(event)
