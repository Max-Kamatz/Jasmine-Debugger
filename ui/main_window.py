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
    QStackedWidget,
    QToolBar,
    QWidget,
)

from ui.command_panel import CommandPanel
from ui.companion_panel import CompanionPanel
from ui.comms_log import CommsLog
from workers.ssh_bridge import SSHBridge

_STYLE = """
QMainWindow, QWidget { background: #0d1117; color: #c9d1d9; }
QLineEdit {
    background: #161b22; color: #c9d1d9;
    border: 1px solid #30363d; padding: 2px;
}
QSpinBox, QDoubleSpinBox {
    background: #161b22; color: #c9d1d9;
    border: 1px solid #30363d;
    padding-right: 18px;
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
QTabWidget::pane { border: 1px solid #30363d; }
QTabBar::tab {
    background: #161b22; color: #8b949e;
    padding: 4px 10px; border: 1px solid #30363d;
}
QTabBar::tab:selected { background: #0d1117; color: #c9d1d9; border-bottom: none; }
QTabBar::tab:hover { background: #1c2333; }
QTableWidget {
    background: #0d1117; color: #c9d1d9;
    gridline-color: #30363d; border: 1px solid #30363d;
}
QHeaderView::section {
    background: #161b22; color: #8b949e;
    border: 1px solid #30363d; padding: 3px;
}
"""

_COMPANION_SERVICE = "CompanionService"


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
        for rate in (9600, 19200, 38400, 57600, 115200, 230400, 460800, 800000, 921600):
            self._baud_combo.addItem(str(rate), rate)
        self._baud_combo.setCurrentText("800000")
        toolbar.addWidget(self._baud_combo)

        toolbar.addWidget(QLabel("  Config:"))
        self._config_combo = QComboBox()
        self._config_combo.addItem("MK4", "MK4")
        self._config_combo.addItem("MK2", "MK2")
        self._config_combo.setFixedWidth(60)
        self._config_combo.currentIndexChanged.connect(self._on_config_changed)
        toolbar.addWidget(self._config_combo)

        self._board_label = QLabel("  Board:")
        toolbar.addWidget(self._board_label)
        self._board_combo = QComboBox()
        self._board_combo.addItem("JASMINE", "JASMINE")
        self._board_combo.addItem("COMPANION", "COMPANION")
        self._board_combo.setFixedWidth(110)
        self._board_combo.currentIndexChanged.connect(self._on_board_changed)
        toolbar.addWidget(self._board_combo)

        toolbar.addWidget(QLabel("  Target:"))
        self._target_combo = QComboBox()
        self._target_combo.addItem("Primary (Direct)", None)
        for ip in ("10.10.10.2", "10.10.10.3", "10.10.10.4",
                   "10.10.10.5", "10.10.10.6", "10.10.10.7"):
            self._target_combo.addItem(ip, ip)
        self._target_combo.setFixedWidth(140)
        toolbar.addWidget(self._target_combo)

        self._btn_connect = QPushButton("Connect")
        self._btn_connect.clicked.connect(self._on_connect)
        toolbar.addWidget(self._btn_connect)

        self._btn_disconnect = QPushButton("Disconnect")
        self._btn_disconnect.setEnabled(False)
        self._btn_disconnect.clicked.connect(self._on_disconnect)
        toolbar.addWidget(self._btn_disconnect)

        self._status_label = QLabel("Disconnected")
        toolbar.addWidget(self._status_label)

        # Panel stack — MK4, MK2-Jasmine, MK2-Companion
        self._mk4_panel = CommandPanel(mk2=False)
        self._mk2_jasmine_panel = CommandPanel(mk2=True)
        self._companion_panel = CompanionPanel()

        self._panel_stack = QStackedWidget()
        self._panel_stack.addWidget(self._mk4_panel)
        self._panel_stack.addWidget(self._mk2_jasmine_panel)
        self._panel_stack.addWidget(self._companion_panel)

        # Body
        self._comms_log = CommsLog()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._panel_stack)
        splitter.addWidget(self._comms_log)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        self.setCentralWidget(splitter)

        # Apply initial config state (MK4 defaults)
        self._apply_config_state()

    # ------------------------------------------------------------------
    # Config / board state
    # ------------------------------------------------------------------

    def _on_config_changed(self) -> None:
        self._apply_config_state()

    def _on_board_changed(self) -> None:
        self._apply_config_state()

    def _apply_config_state(self) -> None:
        """Sync panel, baud lock, and target lock to the current Config/Board selection."""
        config = self._config_combo.currentData()
        board = self._board_combo.currentData()
        is_mk2 = config == "MK2"

        self._board_label.setEnabled(is_mk2)
        self._board_combo.setEnabled(is_mk2)

        if not is_mk2:
            self._panel_stack.setCurrentWidget(self._mk4_panel)
            self._baud_combo.setCurrentText("800000")
            self._baud_combo.setEnabled(True)
            self._target_combo.setEnabled(True)
        elif board == "JASMINE":
            self._panel_stack.setCurrentWidget(self._mk2_jasmine_panel)
            self._baud_combo.setCurrentText("115200")
            self._baud_combo.setEnabled(False)
            self._target_combo.setCurrentIndex(0)
            self._target_combo.setEnabled(False)
        else:  # COMPANION
            self._panel_stack.setCurrentWidget(self._companion_panel)
            self._baud_combo.setCurrentText("9600")
            self._baud_combo.setEnabled(False)
            self._target_combo.setEnabled(True)

    def _active_panel(self) -> QWidget:
        return self._panel_stack.currentWidget()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _on_connect(self) -> None:
        self._btn_connect.setEnabled(False)
        self._config_combo.setEnabled(False)
        self._board_combo.setEnabled(False)
        self._baud_combo.setEnabled(False)
        self._target_combo.setEnabled(False)
        self._status_label.setText("Connecting...")

        config = self._config_combo.currentData()
        board = self._board_combo.currentData()

        if config == "MK2" and board == "COMPANION":
            port_filter = "COMPANION"
            companion_service = _COMPANION_SERVICE
        else:
            port_filter = "JASMINE"
            companion_service = None

        self._bridge = SSHBridge(
            self._ip_field.text(),
            self._port_field.value(),
            self._user_field.text(),
            self._pass_field.text(),
            baud=self._baud_combo.currentData(),
            hop_target=self._target_combo.currentData(),
            port_filter=port_filter,
            companion_service=companion_service,
            config=config,
        )
        self._bridge.connected.connect(self._on_connected)
        self._bridge.disconnected.connect(self._on_disconnected)
        self._bridge.rx_data.connect(lambda t: self._comms_log.append_entry("Rx", t))
        self._bridge.tx_logged.connect(lambda t: self._comms_log.append_entry("Tx", t))
        self._bridge.error.connect(self._on_error)
        self._bridge.status_update.connect(self._status_label.setText)
        self._bridge.status_update.connect(lambda t: self._comms_log.append_entry("---", t))
        self._active_panel().command_requested.connect(self._bridge.send_command)

        self._bridge.start()

    def _on_disconnect(self) -> None:
        if self._bridge is not None:
            self._bridge.stop()

    def _on_connected(self) -> None:
        self._btn_disconnect.setEnabled(True)
        self._active_panel().set_enabled(True)

    def _on_disconnected(self) -> None:
        self._active_panel().set_enabled(False)
        self._btn_connect.setEnabled(True)
        self._btn_disconnect.setEnabled(False)
        self._config_combo.setEnabled(True)
        self._status_label.setText("Disconnected")
        if self._bridge is not None:
            self._bridge.wait()
        self._bridge = None
        self._apply_config_state()

    def _on_error(self, msg: str) -> None:
        self._status_label.setText(f"Error: {msg}")
        self._comms_log.append_entry("ERR", msg)
        self._active_panel().set_enabled(False)
        self._btn_connect.setEnabled(True)
        self._btn_disconnect.setEnabled(False)
        self._config_combo.setEnabled(True)
        self._apply_config_state()

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        if self._bridge is not None:
            self._bridge.stop()
            self._bridge.wait(3000)
        super().closeEvent(event)
