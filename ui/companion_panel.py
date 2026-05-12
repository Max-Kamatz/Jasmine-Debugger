from typing import List, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.command_builder import build_companion_command


class CompanionPanel(QWidget):
    command_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.set_enabled(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_enabled(self, enabled: bool) -> None:
        self._tabs.setEnabled(enabled)
        self._manual_field.setEnabled(enabled)
        self._btn_manual_send.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cs(self) -> bool:
        return self._chk_checksum.isChecked()

    def _send(self, cmd: str, params: Optional[List] = None, query: bool = False) -> None:
        text = build_companion_command(cmd, params=params, query=query, checksum=self._cs())
        self.command_requested.emit(text)

    @staticmethod
    def _scrollable(widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        return scroll

    @staticmethod
    def _vbox(*groups: QGroupBox) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(6)
        layout.setContentsMargins(4, 4, 4, 4)
        for g in groups:
            layout.addWidget(g)
        layout.addStretch()
        return w

    # ------------------------------------------------------------------
    # Top-level UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        top_row = QHBoxLayout()
        top_row.addStretch()
        self._chk_checksum = QCheckBox("Checksum")
        top_row.addWidget(self._chk_checksum)
        layout.addLayout(top_row)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._scrollable(self._vbox(self._build_system())), "System")
        self._tabs.addTab(self._scrollable(self._vbox(self._build_power())), "Power")
        self._tabs.addTab(self._scrollable(self._vbox(self._build_switch())), "Switch")
        self._tabs.addTab(self._scrollable(self._vbox(self._build_fan())), "Fan")
        self._tabs.addTab(self._scrollable(self._vbox(self._build_expansion())), "Expansion")
        self._tabs.addTab(self._scrollable(self._vbox(self._build_environment())), "Environment")
        layout.addWidget(self._tabs)

        manual_row = QHBoxLayout()
        self._manual_field = QLineEdit()
        self._manual_field.setPlaceholderText("Send raw command...")
        self._btn_manual_send = QPushButton("Send")
        self._btn_manual_send.clicked.connect(self._on_manual_send)
        manual_row.addWidget(self._manual_field)
        manual_row.addWidget(self._btn_manual_send)
        layout.addLayout(manual_row)

    # ------------------------------------------------------------------
    # System tab  (Device G, Channel S)
    # ------------------------------------------------------------------

    def _build_system(self) -> QGroupBox:
        box = QGroupBox("System (GS)")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        for label, cmd, query in [
            ("?GSV  Version", "GSV", True),
            ("GSR  Reset", "GSR", False),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, c=cmd, q=query: self._send(c, query=q))
            row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)

        for label, cmd in [("GSS  Cold Start", "GSS"), ("GSW  Keep Warm", "GSW")]:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{label}:"))
            btn_on = QPushButton("Enable")
            btn_off = QPushButton("Disable")
            btn_q = QPushButton("?Get")
            btn_on.clicked.connect(lambda _, c=cmd: self._send(c, params=[1]))
            btn_off.clicked.connect(lambda _, c=cmd: self._send(c, params=[0]))
            btn_q.clicked.connect(lambda _, c=cmd: self._send(c, query=True))
            row.addWidget(btn_on)
            row.addWidget(btn_off)
            row.addWidget(btn_q)
            row.addStretch()
            layout.addLayout(row)

        row = QHBoxLayout()
        btn_u = QPushButton("GSU  Bootloader")
        btn_uq = QPushButton("?GSU  Version")
        btn_u.clicked.connect(lambda _: self._send("GSU"))
        btn_uq.clicked.connect(lambda _: self._send("GSU", query=True))
        row.addWidget(btn_u)
        row.addWidget(btn_uq)
        row.addStretch()
        layout.addLayout(row)

        return box

    # ------------------------------------------------------------------
    # Power tab  (Device P, channels 0–3)
    # ------------------------------------------------------------------

    def _build_power(self) -> QGroupBox:
        box = QGroupBox("Power (P, ch 0–3)  — ch 0 always on, read-only")
        layout = QVBoxLayout(box)

        ch_row = QHBoxLayout()
        ch_row.addWidget(QLabel("Channel (0–3):"))
        spin_ch = QSpinBox()
        spin_ch.setRange(0, 3)
        spin_ch.setValue(1)
        ch_row.addWidget(spin_ch)
        ch_row.addStretch()
        layout.addLayout(ch_row)

        row = QHBoxLayout()
        row.addWidget(QLabel("PxC  Control:"))
        for label, val in [("Off", 0), ("On", 1), ("Cycle/delay", 2)]:
            btn = QPushButton(label)
            btn.clicked.connect(
                lambda _, ch=spin_ch, v=val: self._send(f"P{ch.value()}C", params=[v])
            )
            row.addWidget(btn)
        btn_q = QPushButton("?Get")
        btn_q.clicked.connect(lambda _, ch=spin_ch: self._send(f"P{ch.value()}C", query=True))
        row.addWidget(btn_q)
        row.addStretch()
        layout.addLayout(row)

        row = QHBoxLayout()
        for label, feat in [("?Voltage", "V"), ("?Current", "I"), ("?Temp", "T")]:
            btn = QPushButton(label)
            btn.clicked.connect(
                lambda _, ch=spin_ch, f=feat: self._send(f"P{ch.value()}{f}", query=True)
            )
            row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("PxW  Overheat warn (°C):"))
        spin_w = QDoubleSpinBox()
        spin_w.setRange(-100, 200)
        spin_w.setDecimals(1)
        spin_w.setValue(70.0)
        btn_ws = QPushButton("Set")
        btn_wg = QPushButton("Get")
        btn_ws.clicked.connect(
            lambda _, ch=spin_ch, s=spin_w: self._send(f"P{ch.value()}W", params=[s.value()])
        )
        btn_wg.clicked.connect(lambda _, ch=spin_ch: self._send(f"P{ch.value()}W", query=True))
        row.addWidget(spin_w)
        row.addWidget(btn_ws)
        row.addWidget(btn_wg)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("PxZ  Overheat shutdown (°C):"))
        spin_z = QDoubleSpinBox()
        spin_z.setRange(-100, 200)
        spin_z.setDecimals(1)
        spin_z.setValue(80.0)
        btn_zs = QPushButton("Set")
        btn_zg = QPushButton("Get")
        btn_zs.clicked.connect(
            lambda _, ch=spin_ch, s=spin_z: self._send(f"P{ch.value()}Z", params=[s.value()])
        )
        btn_zg.clicked.connect(lambda _, ch=spin_ch: self._send(f"P{ch.value()}Z", query=True))
        row.addWidget(spin_z)
        row.addWidget(btn_zs)
        row.addWidget(btn_zg)
        layout.addLayout(row)

        return box

    # ------------------------------------------------------------------
    # Switch tab  (Device S, channels 1–3)
    # ------------------------------------------------------------------

    def _build_switch(self) -> QGroupBox:
        box = QGroupBox("Switch (S, ch 1–3)")
        layout = QVBoxLayout(box)

        ch_row = QHBoxLayout()
        ch_row.addWidget(QLabel("Channel (1–3):"))
        spin_ch = QSpinBox()
        spin_ch.setRange(1, 3)
        ch_row.addWidget(spin_ch)
        ch_row.addStretch()
        layout.addLayout(ch_row)

        row = QHBoxLayout()
        row.addWidget(QLabel("SxC  Control:"))
        btn_on = QPushButton("On")
        btn_off = QPushButton("Off")
        btn_q = QPushButton("?Get")
        btn_on.clicked.connect(lambda _, ch=spin_ch: self._send(f"S{ch.value()}C", params=[1]))
        btn_off.clicked.connect(lambda _, ch=spin_ch: self._send(f"S{ch.value()}C", params=[0]))
        btn_q.clicked.connect(lambda _, ch=spin_ch: self._send(f"S{ch.value()}C", query=True))
        row.addWidget(btn_on)
        row.addWidget(btn_off)
        row.addWidget(btn_q)
        row.addStretch()
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("SxD  Duty (0–100 %):"))
        spin_d = QSpinBox()
        spin_d.setRange(0, 100)
        spin_d.setValue(50)
        btn_ds = QPushButton("Set")
        btn_dg = QPushButton("Get")
        btn_ds.clicked.connect(
            lambda _, ch=spin_ch, s=spin_d: self._send(f"S{ch.value()}D", params=[s.value()])
        )
        btn_dg.clicked.connect(lambda _, ch=spin_ch: self._send(f"S{ch.value()}D", query=True))
        row.addWidget(spin_d)
        row.addWidget(btn_ds)
        row.addWidget(btn_dg)
        layout.addLayout(row)

        return box

    # ------------------------------------------------------------------
    # Fan tab  (Device F, channel 1)
    # ------------------------------------------------------------------

    def _build_fan(self) -> QGroupBox:
        box = QGroupBox("Fan (F1)")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        for label, cmd, params, query in [
            ("Enable", "F1C", [1], False),
            ("Disable", "F1C", [0], False),
            ("?State", "F1C", None, True),
            ("?Voltage", "F1V", None, True),
            ("?Current", "F1I", None, True),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, c=cmd, p=params, q=query: self._send(c, params=p, query=q))
            row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("F1D  Duty (0–100 %):"))
        spin_d = QSpinBox()
        spin_d.setRange(0, 100)
        spin_d.setValue(50)
        btn_ds = QPushButton("Set")
        btn_dg = QPushButton("?Get")
        btn_ds.clicked.connect(lambda _, s=spin_d: self._send("F1D", params=[s.value()]))
        btn_dg.clicked.connect(lambda _: self._send("F1D", query=True))
        row.addWidget(spin_d)
        row.addWidget(btn_ds)
        row.addWidget(btn_dg)
        layout.addLayout(row)

        return box

    # ------------------------------------------------------------------
    # Expansion tab  (Device X, channels 1.0–1.3 / 2.0–2.3)
    # ------------------------------------------------------------------

    def _build_expansion(self) -> QGroupBox:
        box = QGroupBox("Expansion Port (X)")
        layout = QVBoxLayout(box)

        ch_row = QHBoxLayout()
        ch_row.addWidget(QLabel("Channel:"))
        self._x_ch_combo = QComboBox()
        for port in (1, 2):
            for pin in range(4):
                self._x_ch_combo.addItem(f"{port}.{pin}")
        ch_row.addWidget(self._x_ch_combo)
        ch_row.addStretch()
        layout.addLayout(ch_row)

        def _ch() -> str:
            return self._x_ch_combo.currentText()

        row = QHBoxLayout()
        row.addWidget(QLabel("State:"))
        for label, feat, params, query in [
            ("?XchG  Actual", "G", None, True),
            ("XchS=1  High", "S", [1], False),
            ("XchS=0  Low", "S", [0], False),
            ("?XchS  Desired", "S", None, True),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(
                lambda _, f=feat, p=params, q=query: self._send(f"X{_ch()}{f}", params=p, query=q)
            )
            row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Mode:"))
        for label, feat in [
            ("XchT  Toggle", "T"),
            ("XchO  Open-Drain", "O"),
            ("XchP  Push-Pull", "P"),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, f=feat: self._send(f"X{_ch()}{f}"))
            row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)

        return box

    # ------------------------------------------------------------------
    # Environment tab  (Device E, channels L and R)
    # ------------------------------------------------------------------

    def _build_environment(self) -> QGroupBox:
        box = QGroupBox("Environment (E)")
        layout = QVBoxLayout(box)

        local_box = QGroupBox("Local (EL) — SHT40 on I²C")
        local_layout = QVBoxLayout(local_box)

        row = QHBoxLayout()
        for label, feat in [("?ELT  Temp", "T"), ("?ELH  Humidity", "H")]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, f=feat: self._send(f"EL{f}", query=True))
            row.addWidget(btn)
        row.addStretch()
        local_layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("ELN  Setpoint (°C):"))
        spin_n = QDoubleSpinBox()
        spin_n.setRange(-100, 200)
        spin_n.setDecimals(1)
        btn_ns = QPushButton("Set")
        btn_ng = QPushButton("Get")
        btn_ns.clicked.connect(lambda _, s=spin_n: self._send("ELN", params=[s.value()]))
        btn_ng.clicked.connect(lambda _: self._send("ELN", query=True))
        row.addWidget(spin_n)
        row.addWidget(btn_ns)
        row.addWidget(btn_ng)
        local_layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("ELO  Overshoot (°C):"))
        spin_o = QDoubleSpinBox()
        spin_o.setRange(0, 50)
        spin_o.setDecimals(1)
        btn_os = QPushButton("Set")
        btn_og = QPushButton("Get")
        btn_os.clicked.connect(lambda _, s=spin_o: self._send("ELO", params=[s.value()]))
        btn_og.clicked.connect(lambda _: self._send("ELO", query=True))
        row.addWidget(spin_o)
        row.addWidget(btn_os)
        row.addWidget(btn_og)
        local_layout.addLayout(row)

        layout.addWidget(local_box)

        remote_box = QGroupBox("Remote (ER) — single-wire bus relay")
        remote_layout = QHBoxLayout(remote_box)
        remote_layout.addWidget(QLabel("Device addr (1+):"))
        spin_addr = QSpinBox()
        spin_addr.setRange(1, 32)
        remote_layout.addWidget(spin_addr)
        remote_layout.addWidget(QLabel("Feature:"))
        self._remote_feat = QLineEdit("T")
        self._remote_feat.setFixedWidth(40)
        remote_layout.addWidget(self._remote_feat)
        btn_relay = QPushButton("?Query")
        btn_relay.clicked.connect(
            lambda _, a=spin_addr: self._send(
                f"ER{a.value()}{self._remote_feat.text().strip() or 'T'}", query=True
            )
        )
        remote_layout.addWidget(btn_relay)
        remote_layout.addStretch()
        layout.addWidget(remote_box)

        return box

    # ------------------------------------------------------------------
    # Manual send
    # ------------------------------------------------------------------

    def _on_manual_send(self) -> None:
        text = self._manual_field.text().strip()
        if not text:
            return
        if not text.endswith("\r\n"):
            text += "\r\n"
        self.command_requested.emit(text)
        self._manual_field.clear()
