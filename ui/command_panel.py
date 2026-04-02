from typing import Optional, List

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.command_builder import build_command


class CommandPanel(QWidget):
    command_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.set_enabled(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_enabled(self, enabled: bool) -> None:
        self._scroll_content.setEnabled(enabled)
        self._manual_field.setEnabled(enabled)
        self._btn_manual_send.setEnabled(enabled)

    def _axis(self) -> str:
        checked = self._axis_group.checkedButton()
        return checked.text() if checked else "P"

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Axis selector
        axis_row = QHBoxLayout()
        axis_row.addWidget(QLabel("Axis:"))
        self._axis_group = QButtonGroup(self)
        self._axis_group.setExclusive(True)
        for label in ("P", "T", "*"):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedWidth(36)
            self._axis_group.addButton(btn)
            axis_row.addWidget(btn)
            if label == "P":
                btn.setChecked(True)
        self._chk_checksum = QCheckBox("Checksum")
        axis_row.addStretch()
        axis_row.addWidget(self._chk_checksum)
        layout.addLayout(axis_row)

        # Scroll area with all command groups
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._scroll_content = QWidget()
        scroll_layout = QVBoxLayout(self._scroll_content)
        scroll_layout.setSpacing(6)

        scroll_layout.addWidget(self._build_motion_steps())
        scroll_layout.addWidget(self._build_motion_degrees())
        scroll_layout.addWidget(self._build_velocity())
        scroll_layout.addWidget(self._build_queries())
        scroll_layout.addWidget(self._build_limits())
        scroll_layout.addWidget(self._build_current())
        scroll_layout.addWidget(self._build_system())
        scroll_layout.addWidget(self._build_register())
        scroll_layout.addWidget(self._build_test_misc())
        scroll_layout.addStretch()

        scroll.setWidget(self._scroll_content)
        layout.addWidget(scroll)

        # Manual send
        manual_row = QHBoxLayout()
        self._manual_field = QLineEdit()
        self._manual_field.setPlaceholderText("Send raw command...")
        self._btn_manual_send = QPushButton("Send")
        self._btn_manual_send.clicked.connect(self._on_manual_send)
        manual_row.addWidget(self._manual_field)
        manual_row.addWidget(self._btn_manual_send)
        layout.addLayout(manual_row)

    # ------------------------------------------------------------------
    # Command group builders
    # ------------------------------------------------------------------

    def _build_motion_steps(self) -> QGroupBox:
        box = QGroupBox("Motion (Steps)")
        layout = QVBoxLayout(box)
        for cmd in ("AS", "OS", "RS"):
            row = QHBoxLayout()
            row.addWidget(QLabel(cmd))
            spin_val = QSpinBox()
            spin_val.setRange(-999999, 999999)
            spin_timing = QDoubleSpinBox()
            spin_timing.setRange(0, 9999)
            spin_timing.setDecimals(1)
            spin_timing.setSpecialValueText("—")
            chk_rt = QCheckBox("!")
            btn = QPushButton("Send")
            row.addWidget(spin_val)
            row.addWidget(QLabel("t:"))
            row.addWidget(spin_timing)
            row.addWidget(chk_rt)
            row.addWidget(btn)
            btn.clicked.connect(lambda _, c=cmd, sv=spin_val, st=spin_timing, rt=chk_rt: self._send(
                c,
                params=[sv.value()] + ([st.value()] if st.value() > 0 else []),
                realtime=rt.isChecked(),
            ))
            layout.addLayout(row)
        return box

    def _build_motion_degrees(self) -> QGroupBox:
        box = QGroupBox("Motion (Degrees)")
        layout = QVBoxLayout(box)
        for cmd in ("AA", "OA", "RA"):
            row = QHBoxLayout()
            row.addWidget(QLabel(cmd))
            spin_val = QDoubleSpinBox()
            spin_val.setRange(-9999, 9999)
            spin_val.setDecimals(1)
            spin_timing = QDoubleSpinBox()
            spin_timing.setRange(0, 9999)
            spin_timing.setDecimals(1)
            spin_timing.setSpecialValueText("—")
            chk_rt = QCheckBox("!")
            btn = QPushButton("Send")
            row.addWidget(spin_val)
            row.addWidget(QLabel("t:"))
            row.addWidget(spin_timing)
            row.addWidget(chk_rt)
            row.addWidget(btn)
            btn.clicked.connect(lambda _, c=cmd, sv=spin_val, st=spin_timing, rt=chk_rt: self._send(
                c,
                params=[sv.value()] + ([st.value()] if st.value() > 0 else []),
                realtime=rt.isChecked(),
            ))
            layout.addLayout(row)
        return box

    def _build_velocity(self) -> QGroupBox:
        box = QGroupBox("Velocity")
        layout = QVBoxLayout(box)

        row_vs = QHBoxLayout()
        row_vs.addWidget(QLabel("VS"))
        spin_vs = QSpinBox()
        spin_vs.setRange(0, 999999)
        btn_vs = QPushButton("Set VS")
        btn_vs.clicked.connect(lambda: self._send("VS", params=[spin_vs.value()]))
        row_vs.addWidget(spin_vs)
        row_vs.addWidget(btn_vs)
        layout.addLayout(row_vs)

        row_va = QHBoxLayout()
        row_va.addWidget(QLabel("VA"))
        spin_va = QDoubleSpinBox()
        spin_va.setRange(0, 9999)
        spin_va.setDecimals(1)
        btn_va = QPushButton("Set VA")
        btn_va.clicked.connect(lambda: self._send("VA", params=[spin_va.value()]))
        row_va.addWidget(spin_va)
        row_va.addWidget(btn_va)
        layout.addLayout(row_va)

        return box

    def _build_queries(self) -> QGroupBox:
        box = QGroupBox("Queries")
        layout = QHBoxLayout(box)
        for cmd in ("PS", "PA", "NS", "NA", "S", "MODE", "VER"):
            btn = QPushButton(f"?{cmd}")
            btn.clicked.connect(lambda _, c=cmd: self._send(c, query=True))
            layout.addWidget(btn)
        return box

    def _build_limits(self) -> QGroupBox:
        box = QGroupBox("Limits")
        layout = QVBoxLayout(box)
        limits = [("LUS", QSpinBox), ("LUA", QDoubleSpinBox),
                  ("LLS", QSpinBox), ("LLA", QDoubleSpinBox)]
        for cmd, SpinClass in limits:
            row = QHBoxLayout()
            row.addWidget(QLabel(cmd))
            spin = SpinClass()
            if SpinClass == QDoubleSpinBox:
                spin.setRange(-9999, 9999)
                spin.setDecimals(1)
            else:
                spin.setRange(-999999, 999999)
            btn = QPushButton("Set")
            btn.clicked.connect(lambda _, c=cmd, s=spin: self._send(c, params=[s.value()]))
            row.addWidget(spin)
            row.addWidget(btn)
            layout.addLayout(row)
        return box

    def _build_current(self) -> QGroupBox:
        box = QGroupBox("Current")
        layout = QVBoxLayout(box)
        for cmd in ("IHOLD", "IRUN"):
            row = QHBoxLayout()
            row.addWidget(QLabel(cmd))
            spin = QSpinBox()
            spin.setRange(0, 31)
            btn_get = QPushButton("Get")
            btn_set = QPushButton("Set")
            btn_get.clicked.connect(lambda _, c=cmd: self._send(c, query=True))
            btn_set.clicked.connect(lambda _, c=cmd, s=spin: self._send(c, params=[s.value()]))
            row.addWidget(spin)
            row.addWidget(btn_get)
            row.addWidget(btn_set)
            layout.addLayout(row)
        return box

    def _build_system(self) -> QGroupBox:
        box = QGroupBox("System")
        layout = QHBoxLayout(box)
        for cmd in ("RESET", "SAVE", "DEFAULTS", "FIX", "UNFIX", "INITCOM"):
            btn = QPushButton(cmd)
            btn.clicked.connect(lambda _, c=cmd: self._send(c))
            layout.addWidget(btn)
        return box

    def _build_register(self) -> QGroupBox:
        box = QGroupBox("Register")
        layout = QHBoxLayout(box)
        layout.addWidget(QLabel("Addr:"))
        spin_addr = QSpinBox()
        spin_addr.setRange(0, 255)
        chk_set = QCheckBox("Set value")
        spin_val = QSpinBox()
        spin_val.setRange(0, 255)
        btn = QPushButton("Send")
        btn.clicked.connect(lambda: self._send(
            "REG",
            params=[spin_addr.value(), spin_val.value()] if chk_set.isChecked() else [spin_addr.value()],
        ))
        layout.addWidget(spin_addr)
        layout.addWidget(chk_set)
        layout.addWidget(spin_val)
        layout.addWidget(btn)
        return box

    def _build_test_misc(self) -> QGroupBox:
        box = QGroupBox("Test/Misc")
        layout = QVBoxLayout(box)

        row1 = QHBoxLayout()
        spin_test = QSpinBox()
        spin_test.setRange(1, 9999)
        btn_test = QPushButton("TEST")
        btn_test.clicked.connect(lambda: self._send("TEST", params=[spin_test.value()]))
        spin_shake = QSpinBox()
        spin_shake.setRange(1, 9999)
        btn_shake = QPushButton("SHAKE")
        btn_shake.clicked.connect(lambda: self._send("SHAKE", params=[spin_shake.value()]))
        row1.addWidget(QLabel("TEST"))
        row1.addWidget(spin_test)
        row1.addWidget(btn_test)
        row1.addWidget(QLabel("SHAKE"))
        row1.addWidget(spin_shake)
        row1.addWidget(btn_shake)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        btn_dir_pos = QPushButton("DIR +1")
        btn_dir_neg = QPushButton("DIR -1")
        btn_dir_pos.clicked.connect(lambda: self._send("DIR", params=[1]))
        btn_dir_neg.clicked.connect(lambda: self._send("DIR", params=[-1]))
        spin_spr = QSpinBox()
        spin_spr.setRange(1, 99999)
        btn_spr = QPushButton("Set SPR")
        btn_spr.clicked.connect(lambda: self._send("SPR", params=[spin_spr.value()]))
        row2.addWidget(btn_dir_pos)
        row2.addWidget(btn_dir_neg)
        row2.addWidget(QLabel("SPR"))
        row2.addWidget(spin_spr)
        row2.addWidget(btn_spr)
        layout.addLayout(row2)

        return box

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _send(self, cmd: str, params: Optional[List] = None,
              query: bool = False, realtime: bool = False) -> None:
        text = build_command(
            self._axis(), cmd,
            params=params,
            query=query,
            realtime=realtime,
            checksum=self._chk_checksum.isChecked(),
        )
        self.command_requested.emit(text)

    def _on_manual_send(self) -> None:
        text = self._manual_field.text().strip()
        if not text:
            return
        if not text.endswith("\r\n"):
            text += "\r\n"
        self.command_requested.emit(text)
        self._manual_field.clear()
