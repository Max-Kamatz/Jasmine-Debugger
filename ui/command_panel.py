# ui/command_panel.py
from typing import List, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
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

from core.command_builder import build_command
from ui.jog_pad import JogPad


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
        self._tabs.setEnabled(enabled)
        self._manual_field.setEnabled(enabled)
        self._btn_manual_send.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _axis(self) -> str:
        checked = self._axis_group.checkedButton()
        return checked.text() if checked else "P"

    def _cs(self) -> bool:
        return self._chk_checksum.isChecked()

    def _send(self, cmd: str, params: Optional[List] = None, query: bool = False) -> None:
        text = build_command(cmd, params=params, query=query, checksum=self._cs())
        self.command_requested.emit(text)

    def _send_axis(self, template: str, params: Optional[List] = None, query: bool = False) -> None:
        """Substitute 'x' in *template* with the selected axis letter (P or T)."""
        self._send(template.replace("x", self._axis()), params=params, query=query)

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

        # Axis selector + checksum
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Axis:"))
        self._axis_group = QButtonGroup(self)
        self._axis_group.setExclusive(True)
        for label in ("P", "T"):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedWidth(36)
            self._axis_group.addButton(btn)
            top_row.addWidget(btn)
            if label == "P":
                btn.setChecked(True)
        self._chk_checksum = QCheckBox("Checksum")
        top_row.addStretch()
        top_row.addWidget(self._chk_checksum)
        layout.addLayout(top_row)

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.addTab(
            self._scrollable(self._vbox(
                self._build_axis_motion(),
                self._build_joint_motion(),
                self._build_motion_queries(),
                self._build_jog_pad(),
            )),
            "Motion",
        )
        self._tabs.addTab(
            self._scrollable(self._vbox(
                self._build_velocity(),
                self._build_profile(),
                self._build_update_period(),
            )),
            "Vel/Profile",
        )
        self._tabs.addTab(
            self._scrollable(self._vbox(
                self._build_limits(),
                self._build_sensitivity(),
                self._build_encoder(),
                self._build_flags(),
            )),
            "Config",
        )
        self._tabs.addTab(
            self._scrollable(self._vbox(
                self._build_homing_run(),
                self._build_homing_velocities(),
                self._build_homing_config(),
            )),
            "Homing",
        )
        self._tabs.addTab(
            self._scrollable(self._vbox(
                self._build_system_actions(),
                self._build_system_settings(),
                self._build_cold_start(),
                self._build_network(),
            )),
            "System",
        )
        self._tabs.addTab(
            self._scrollable(self._vbox(
                self._build_power_channels(),
                self._build_motor_current(),
                self._build_half_bridge(),
                self._build_optical(),
                self._build_fan(),
                self._build_xio(),
            )),
            "Power/I-O",
        )
        self._tabs.addTab(
            self._scrollable(self._vbox(
                self._build_tmc_register(),
                self._build_debug_actions(),
            )),
            "Debug",
        )
        layout.addWidget(self._tabs)

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
    # Motion tab
    # ------------------------------------------------------------------

    def _build_axis_motion(self) -> QGroupBox:
        box = QGroupBox("Axis Motion")
        layout = QVBoxLayout(box)

        for label, cmd in [
            ("MxA  Absolute (deg):", "MxA"),
            ("MxR  Relative (deg):", "MxR"),
            ("MxJ  Jog vel (deg/s):", "MxJ"),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            spin = QDoubleSpinBox()
            spin.setRange(-9999, 9999)
            spin.setDecimals(1)
            btn = QPushButton("Send")
            btn.clicked.connect(lambda _, c=cmd, s=spin: self._send_axis(c, params=[s.value()]))
            row.addWidget(spin)
            row.addWidget(btn)
            layout.addLayout(row)

        row = QHBoxLayout()
        btn_stop = QPushButton("MxS  Stop axis")
        btn_stop.clicked.connect(lambda _: self._send_axis("MxS"))
        row.addWidget(btn_stop)
        row.addStretch()
        row.addWidget(QLabel("MxC  Set angle (deg):"))
        spin_c = QDoubleSpinBox()
        spin_c.setRange(-9999, 9999)
        spin_c.setDecimals(1)
        btn_c = QPushButton("Set")
        btn_c.clicked.connect(lambda _, s=spin_c: self._send_axis("MxC", params=[s.value()]))
        row.addWidget(spin_c)
        row.addWidget(btn_c)
        layout.addLayout(row)

        return box

    def _build_joint_motion(self) -> QGroupBox:
        box = QGroupBox("Joint Motion (Pan + Tilt)")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        row.addWidget(QLabel("MJJ  Pan vel (deg/s):"))
        self._mjj_spin_p = QDoubleSpinBox()
        self._mjj_spin_p.setRange(-9999, 9999)
        self._mjj_spin_p.setDecimals(1)
        row.addWidget(self._mjj_spin_p)
        row.addWidget(QLabel("Tilt vel (deg/s):"))
        self._mjj_spin_t = QDoubleSpinBox()
        self._mjj_spin_t.setRange(-9999, 9999)
        self._mjj_spin_t.setDecimals(1)
        btn = QPushButton("Send")
        btn.clicked.connect(lambda _: self._send("MJJ", params=[self._mjj_spin_p.value(), self._mjj_spin_t.value()]))
        row.addWidget(self._mjj_spin_t)
        row.addWidget(btn)
        layout.addLayout(row)

        row = QHBoxLayout()
        btn_stop = QPushButton("MJS  Stop both")
        btn_stop.clicked.connect(lambda _: self._send("MJS"))
        btn_q = QPushButton("?MJS  Are both still?")
        btn_q.clicked.connect(lambda _: self._send("MJS", query=True))
        row.addWidget(btn_stop)
        row.addWidget(btn_q)
        layout.addLayout(row)

        return box

    def _build_motion_queries(self) -> QGroupBox:
        box = QGroupBox("Motion Queries")
        layout = QHBoxLayout(box)
        for label, cmd in [
            ("?MxC Angle", "MxC"),
            ("?MxE Enc", "MxE"),
            ("?MxA Target", "MxA"),
            ("?MxS Still?", "MxS"),
            ("?MxJ Jog?", "MxJ"),
            ("?MxT Temp", "MxT"),
            ("?MxI Current", "MxI"),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, c=cmd: self._send_axis(c, query=True))
            layout.addWidget(btn)
        return box

    def _build_jog_pad(self) -> QGroupBox:
        box = QGroupBox("Jog Trackpad — drag to jog both axes, release to stop")
        layout = QHBoxLayout(box)

        self._jog_pad = JogPad()
        self._jog_pad.jog_requested.connect(self._on_jog)
        self._jog_pad.stop_requested.connect(lambda: self._send("MJS"))
        layout.addWidget(self._jog_pad)

        info = QLabel(
            "Drag within the circle to jog\n"
            "both axes simultaneously.\n\n"
            "Speed scales linearly with\n"
            "distance from centre.\n\n"
            "Max speed = MJJ spinboxes above\n"
            "(magnitude only)."
        )
        layout.addWidget(info)
        layout.addStretch()

        return box

    def _on_jog(self, pan_frac: float, tilt_frac: float) -> None:
        max_p = abs(self._mjj_spin_p.value())
        max_t = abs(self._mjj_spin_t.value())
        pan_vel = round(pan_frac * max_p, 1)
        tilt_vel = round(tilt_frac * max_t, 1)
        self._send("MJJ", params=[pan_vel, tilt_vel])

    # ------------------------------------------------------------------
    # Vel/Profile tab
    # ------------------------------------------------------------------

    def _build_velocity(self) -> QGroupBox:
        box = QGroupBox("Max Velocity (MxV)")
        layout = QHBoxLayout(box)
        layout.addWidget(QLabel("Vel (deg/s):"))
        spin = QDoubleSpinBox()
        spin.setRange(0, 9999)
        spin.setDecimals(1)
        spin.setValue(60.0)
        btn_set = QPushButton("Set")
        btn_get = QPushButton("Get")
        btn_set.clicked.connect(lambda _, s=spin: self._send_axis("MxV", params=[s.value()]))
        btn_get.clicked.connect(lambda _: self._send_axis("MxV", query=True))
        layout.addWidget(spin)
        layout.addWidget(btn_set)
        layout.addWidget(btn_get)
        return box

    def _build_profile(self) -> QGroupBox:
        box = QGroupBox("Accel/Decel Profile (MxP)")
        layout = QVBoxLayout(box)
        fields = [
            ("f1  Start vel (deg/s)", 0.0),
            ("f2  Init accel (deg/s^2)", 0.0),
            ("f3  Init target vel (deg/s)", 0.0),
            ("f4  Max accel (deg/s^2)", 0.0),
            ("f5  Max vel (deg/s)", 60.0),
            ("f6  Max decel (deg/s^2)", 0.0),
            ("f7  Stop decel (deg/s^2)", 0.0),
            ("f8  Release vel (deg/s)", 0.0),
        ]
        self._profile_spins: List[QDoubleSpinBox] = []
        for lbl, default in fields:
            row = QHBoxLayout()
            row.addWidget(QLabel(lbl + ":"))
            spin = QDoubleSpinBox()
            spin.setRange(0, 99999)
            spin.setDecimals(2)
            spin.setValue(default)
            row.addWidget(spin)
            self._profile_spins.append(spin)
            layout.addLayout(row)
        row = QHBoxLayout()
        btn_set = QPushButton("Set MxP")
        btn_get = QPushButton("Get ?MxP")
        btn_set.clicked.connect(lambda _: self._on_send_profile())
        btn_get.clicked.connect(lambda _: self._send_axis("MxP", query=True))
        row.addWidget(btn_set)
        row.addWidget(btn_get)
        layout.addLayout(row)
        return box

    def _on_send_profile(self) -> None:
        params = [round(s.value(), 2) for s in self._profile_spins]
        self._send_axis("MxP", params=params)

    def _build_update_period(self) -> QGroupBox:
        box = QGroupBox("Position Streaming (MxU)")
        layout = QHBoxLayout(box)
        layout.addWidget(QLabel("Period (ms):"))
        spin = QSpinBox()
        spin.setRange(0, 10000)
        spin.setValue(100)
        btn_set = QPushButton("Set")
        btn_get = QPushButton("Get")
        btn_set.clicked.connect(lambda _, s=spin: self._send_axis("MxU", params=[s.value()]))
        btn_get.clicked.connect(lambda _: self._send_axis("MxU", query=True))
        layout.addWidget(spin)
        layout.addWidget(btn_set)
        layout.addWidget(btn_get)
        return box

    # ------------------------------------------------------------------
    # Config tab
    # ------------------------------------------------------------------

    def _build_limits(self) -> QGroupBox:
        box = QGroupBox("Axis Limits (MxL)")
        layout = QHBoxLayout(box)
        layout.addWidget(QLabel("Lower (deg):"))
        spin_lo = QDoubleSpinBox()
        spin_lo.setRange(-9999, 9999)
        spin_lo.setDecimals(1)
        layout.addWidget(spin_lo)
        layout.addWidget(QLabel("Upper (deg):"))
        spin_hi = QDoubleSpinBox()
        spin_hi.setRange(-9999, 9999)
        spin_hi.setDecimals(1)
        btn_set = QPushButton("Set")
        btn_get = QPushButton("Get")
        btn_set.clicked.connect(
            lambda _, lo=spin_lo, hi=spin_hi: self._send_axis("MxL", params=[lo.value(), hi.value()])
        )
        btn_get.clicked.connect(lambda _: self._send_axis("MxL", query=True))
        layout.addWidget(spin_hi)
        layout.addWidget(btn_set)
        layout.addWidget(btn_get)
        return box

    def _build_sensitivity(self) -> QGroupBox:
        box = QGroupBox("Correction Sensitivity (MxD)")
        layout = QHBoxLayout(box)
        layout.addWidget(QLabel("Mismatch (deg):"))
        spin_m = QDoubleSpinBox()
        spin_m.setRange(0.01, 360)
        spin_m.setDecimals(2)
        spin_m.setValue(1.0)
        layout.addWidget(spin_m)
        layout.addWidget(QLabel("Stall (deg):"))
        spin_s = QDoubleSpinBox()
        spin_s.setRange(0.01, 360)
        spin_s.setDecimals(2)
        spin_s.setValue(1.0)
        btn_set = QPushButton("Set")
        btn_get = QPushButton("Get")
        btn_set.clicked.connect(
            lambda _, m=spin_m, s=spin_s: self._send_axis("MxD", params=[m.value(), s.value()])
        )
        btn_get.clicked.connect(lambda _: self._send_axis("MxD", query=True))
        layout.addWidget(spin_s)
        layout.addWidget(btn_set)
        layout.addWidget(btn_get)
        return box

    def _build_encoder(self) -> QGroupBox:
        box = QGroupBox("Encoder")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        row.addWidget(QLabel("MxX  Ticks/rev:"))
        spin_x = QSpinBox()
        spin_x.setRange(1, 999999)
        spin_x.setValue(4096)
        btn_xs = QPushButton("Set")
        btn_xg = QPushButton("Get")
        btn_xs.clicked.connect(lambda _, s=spin_x: self._send_axis("MxX", params=[s.value()]))
        btn_xg.clicked.connect(lambda _: self._send_axis("MxX", query=True))
        row.addWidget(spin_x)
        row.addWidget(btn_xs)
        row.addWidget(btn_xg)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("MxW  Constant:"))
        spin_w = QDoubleSpinBox()
        spin_w.setRange(-99999, 99999)
        spin_w.setDecimals(4)
        btn_ws = QPushButton("Set")
        btn_wg = QPushButton("Get")
        btn_ws.clicked.connect(lambda _, s=spin_w: self._send_axis("MxW", params=[s.value()]))
        btn_wg.clicked.connect(lambda _: self._send_axis("MxW", query=True))
        row.addWidget(spin_w)
        row.addWidget(btn_ws)
        row.addWidget(btn_wg)
        layout.addLayout(row)

        return box

    def _build_flags(self) -> QGroupBox:
        box = QGroupBox("Axis Flags (MxF)")
        layout = QHBoxLayout(box)
        layout.addWidget(QLabel("Flags (decimal):"))
        spin = QSpinBox()
        spin.setRange(0, 255)
        btn = QPushButton("Set")
        btn.clicked.connect(lambda _, s=spin: self._send_axis("MxF", params=[s.value()]))
        layout.addWidget(spin)
        layout.addWidget(btn)
        return box

    # ------------------------------------------------------------------
    # Homing tab
    # ------------------------------------------------------------------

    def _build_homing_run(self) -> QGroupBox:
        box = QGroupBox("Run Homing")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        row.addWidget(QLabel("MJH  Both axes, debug:"))
        spin = QSpinBox()
        spin.setRange(0, 1)
        spin.setSpecialValueText("(off)")
        btn_h = QPushButton("Home Both")
        btn_q = QPushButton("?MJH Status")
        btn_h.clicked.connect(
            lambda _, s=spin: self._send("MJH", params=[s.value()] if s.value() else None)
        )
        btn_q.clicked.connect(lambda _: self._send("MJH", query=True))
        row.addWidget(spin)
        row.addWidget(btn_h)
        row.addWidget(btn_q)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("MxH  Mode:"))
        combo = QComboBox()
        for val, name in [
            (0, "(default)"),
            (1, "1 - manual"),
            (2, "2 - line"),
            (3, "3 - limits"),
            (4, "4 - strip"),
            (5, "5 - notch"),
            (6, "6 - Zline"),
        ]:
            combo.addItem(name, val)
        btn_h = QPushButton("Home Axis")
        btn_q = QPushButton("?MxH Mode")
        btn_h.clicked.connect(
            lambda _, c=combo: self._send_axis("MxH", params=[c.currentData()] if c.currentData() else None)
        )
        btn_q.clicked.connect(lambda _: self._send_axis("MxH", query=True))
        row.addWidget(combo)
        row.addWidget(btn_h)
        row.addWidget(btn_q)
        layout.addLayout(row)

        return box

    def _build_homing_velocities(self) -> QGroupBox:
        box = QGroupBox("Homing Velocities (MJV)")
        layout = QVBoxLayout(box)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Home vel (deg/s):"))
        spin_h = QDoubleSpinBox()
        spin_h.setRange(0, 9999)
        spin_h.setDecimals(1)
        spin_h.setValue(10.0)
        row1.addWidget(spin_h)
        row1.addWidget(QLabel("Post-home vel (deg/s):"))
        spin_p = QDoubleSpinBox()
        spin_p.setRange(0, 9999)
        spin_p.setDecimals(1)
        spin_p.setValue(5.0)
        row1.addWidget(spin_p)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Self-corr vel (deg/s, optional):"))
        spin_sc = QDoubleSpinBox()
        spin_sc.setRange(0, 9999)
        spin_sc.setDecimals(1)
        spin_sc.setSpecialValueText("---")
        btn_set = QPushButton("Set")
        btn_get = QPushButton("Get")
        btn_set.clicked.connect(
            lambda _, h=spin_h, p=spin_p, sc=spin_sc: self._send(
                "MJV",
                params=[h.value(), p.value()] + ([sc.value()] if sc.value() > 0 else []),
            )
        )
        btn_get.clicked.connect(lambda _: self._send("MJV", query=True))
        row2.addWidget(spin_sc)
        row2.addWidget(btn_set)
        row2.addWidget(btn_get)
        layout.addLayout(row2)

        return box

    def _build_homing_config(self) -> QGroupBox:
        box = QGroupBox("Homing Config")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        row.addWidget(QLabel("MxO  Post-home offset (deg):"))
        spin_o = QDoubleSpinBox()
        spin_o.setRange(-9999, 9999)
        spin_o.setDecimals(1)
        btn_os = QPushButton("Set")
        btn_og = QPushButton("Get")
        btn_os.clicked.connect(lambda _, s=spin_o: self._send_axis("MxO", params=[s.value()]))
        btn_og.clicked.connect(lambda _: self._send_axis("MxO", query=True))
        row.addWidget(spin_o)
        row.addWidget(btn_os)
        row.addWidget(btn_og)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("MxK  Temp comp offset (deg C):"))
        spin_k = QDoubleSpinBox()
        spin_k.setRange(-200, 200)
        spin_k.setDecimals(2)
        btn_ks = QPushButton("Set")
        btn_kg = QPushButton("Get")
        btn_ks.clicked.connect(lambda _, s=spin_k: self._send_axis("MxK", params=[s.value()]))
        btn_kg.clicked.connect(lambda _: self._send_axis("MxK", query=True))
        row.addWidget(spin_k)
        row.addWidget(btn_ks)
        row.addWidget(btn_kg)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("HDE  Homing delay (s):"))
        spin_d = QSpinBox()
        spin_d.setRange(0, 9999)
        btn_ds = QPushButton("Set")
        btn_dg = QPushButton("Get")
        btn_ds.clicked.connect(lambda _, s=spin_d: self._send("HDE", params=[s.value()]))
        btn_dg.clicked.connect(lambda _: self._send("HDE", query=True))
        row.addWidget(spin_d)
        row.addWidget(btn_ds)
        row.addWidget(btn_dg)
        layout.addLayout(row)

        return box

    # ------------------------------------------------------------------
    # System tab
    # ------------------------------------------------------------------

    def _build_system_actions(self) -> QGroupBox:
        box = QGroupBox("System Actions")
        layout = QHBoxLayout(box)
        for label, cmd, query in [
            ("Save (SL!)", "SL!", False),
            ("Defaults (SLD)", "SLD", False),
            ("Reset (SLR)", "SLR", False),
            ("Buf Reset (SLB)", "SLB", False),
            ("?Uptime", "SLR", True),
            ("?Buffers", "SLB", True),
            ("?Version", "SLV", True),
            ("MJR", "MJR", False),
            ("MJD", "MJD", False),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, c=cmd, q=query: self._send(c, query=q))
            layout.addWidget(btn)
        return box

    def _build_system_settings(self) -> QGroupBox:
        box = QGroupBox("System Settings")
        layout = QVBoxLayout(box)

        # SLM -- model
        row = QHBoxLayout()
        row.addWidget(QLabel("SLM  Model:"))
        combo_m = QComboBox()
        combo_m.addItem("AERON (12)", 12)
        combo_m.addItem("JAEGAR V1 (41)", 41)
        combo_m.addItem("JAEGAR V2 (42)", 42)
        combo_m.setCurrentIndex(2)
        btn_ms = QPushButton("Set")
        btn_mg = QPushButton("Get")
        btn_ms.clicked.connect(lambda _, c=combo_m: self._send("SLM", params=[c.currentData()]))
        btn_mg.clicked.connect(lambda _: self._send("SLM", query=True))
        row.addWidget(combo_m)
        row.addWidget(btn_ms)
        row.addWidget(btn_mg)
        layout.addLayout(row)

        # SLS -- serial number
        row = QHBoxLayout()
        row.addWidget(QLabel("SLS  Serial no.:"))
        spin_sn = QSpinBox()
        spin_sn.setRange(0, 99999)
        btn_ss = QPushButton("Set")
        btn_sg = QPushButton("Get")
        btn_ss.clicked.connect(lambda _, s=spin_sn: self._send("SLS", params=[s.value()]))
        btn_sg.clicked.connect(lambda _: self._send("SLS", query=True))
        row.addWidget(spin_sn)
        row.addWidget(btn_ss)
        row.addWidget(btn_sg)
        layout.addLayout(row)

        # SLF -- control flags
        row = QHBoxLayout()
        row.addWidget(QLabel("SLF  Control flags:"))
        spin_f = QSpinBox()
        spin_f.setRange(0, 65535)
        btn_fs = QPushButton("Set")
        btn_fg = QPushButton("Get")
        btn_fs.clicked.connect(lambda _, s=spin_f: self._send("SLF", params=[s.value()]))
        btn_fg.clicked.connect(lambda _: self._send("SLF", query=True))
        row.addWidget(spin_f)
        row.addWidget(btn_fs)
        row.addWidget(btn_fg)
        layout.addLayout(row)

        # SLT -- temperature
        row = QHBoxLayout()
        row.addWidget(QLabel("SLT  Temperature (deg C):"))
        spin_t = QDoubleSpinBox()
        spin_t.setRange(-100, 200)
        spin_t.setDecimals(1)
        btn_ts = QPushButton("Set")
        btn_tg = QPushButton("Get")
        btn_ts.clicked.connect(lambda _, s=spin_t: self._send("SLT", params=[s.value()]))
        btn_tg.clicked.connect(lambda _: self._send("SLT", query=True))
        row.addWidget(spin_t)
        row.addWidget(btn_ts)
        row.addWidget(btn_tg)
        layout.addLayout(row)

        # Misc queries
        row = QHBoxLayout()
        for label, cmd in [("?SLH Humidity", "SLH"), ("?SLI IMU", "SLI"), ("?SEV Events", "SEV")]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, c=cmd: self._send(c, query=True))
            row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)

        return box

    def _build_cold_start(self) -> QGroupBox:
        box = QGroupBox("Cold Start")
        layout = QVBoxLayout(box)

        for label, cmd, is_float, lo, hi in [
            ("SLZ  Heater config (bits):", "SLZ", False, 0, 1023),
            ("SLC  Cold threshold (deg C):", "SLC", True, -100, 100),
            ("SLW  Keep warm temp (deg C):", "SLW", True, -100, 100),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            if is_float:
                spin = QDoubleSpinBox()
                spin.setRange(lo, hi)
                spin.setDecimals(1)
            else:
                spin = QSpinBox()
                spin.setRange(lo, hi)
            btn_s = QPushButton("Set")
            btn_g = QPushButton("Get")
            btn_s.clicked.connect(lambda _, c=cmd, s=spin: self._send(c, params=[s.value()]))
            btn_g.clicked.connect(lambda _, c=cmd: self._send(c, query=True))
            row.addWidget(spin)
            row.addWidget(btn_s)
            row.addWidget(btn_g)
            layout.addLayout(row)

        return box

    def _build_network(self) -> QGroupBox:
        box = QGroupBox("Network (SLN)")
        layout = QVBoxLayout(box)

        row1 = QHBoxLayout()
        self._net_ip = QLineEdit()
        self._net_ip.setPlaceholderText("192.168.1.100")
        self._net_ip.setFixedWidth(120)
        self._net_gw = QLineEdit()
        self._net_gw.setPlaceholderText("192.168.1.1")
        self._net_gw.setFixedWidth(120)
        self._net_mask = QLineEdit()
        self._net_mask.setPlaceholderText("255.255.255.0")
        self._net_mask.setFixedWidth(120)
        for lbl, field in [("IP:", self._net_ip), ("Gateway:", self._net_gw), ("Mask:", self._net_mask)]:
            row1.addWidget(QLabel(lbl))
            row1.addWidget(field)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Port:"))
        self._net_port = QSpinBox()
        self._net_port.setRange(1, 65535)
        self._net_port.setValue(8080)
        btn_set = QPushButton("Set SLN")
        btn_get = QPushButton("Get ?SLN")
        btn_set.clicked.connect(lambda _: self._on_send_network())
        btn_get.clicked.connect(lambda _: self._send("SLN", query=True))
        row2.addWidget(self._net_port)
        row2.addWidget(btn_set)
        row2.addWidget(btn_get)
        layout.addLayout(row2)

        return box

    def _on_send_network(self) -> None:
        self._send("SLN", params=[
            self._net_ip.text(),
            self._net_gw.text(),
            self._net_mask.text(),
            self._net_port.value(),
        ])

    # ------------------------------------------------------------------
    # Power/I-O tab
    # ------------------------------------------------------------------

    def _build_power_channels(self) -> QGroupBox:
        box = QGroupBox("Power Channels (PxC, x=0-3)")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        row.addWidget(QLabel("Channel (0-3):"))
        spin_ch = QSpinBox()
        spin_ch.setRange(0, 3)
        spin_ch.setValue(1)
        row.addWidget(spin_ch)
        row.addWidget(QLabel("State (0/1):"))
        spin_s = QSpinBox()
        spin_s.setRange(0, 1)
        btn_set = QPushButton("Set PxC")
        btn_get = QPushButton("Get ?PxC")
        btn_set.clicked.connect(lambda _, ch=spin_ch, s=spin_s: self._send("P" + str(ch.value()) + "C", params=[s.value()]))
        btn_get.clicked.connect(lambda _, ch=spin_ch: self._send("P" + str(ch.value()) + "C", query=True))
        row.addWidget(spin_s)
        row.addWidget(btn_set)
        row.addWidget(btn_get)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("P2V  Output voltage (ch2 only, V):"))
        spin_v = QDoubleSpinBox()
        spin_v.setRange(0, 60)
        spin_v.setDecimals(1)
        btn_vs = QPushButton("Set P2V")
        btn_vs.clicked.connect(lambda _, s=spin_v: self._send("P2V", params=[s.value()]))
        row.addWidget(spin_v)
        row.addWidget(btn_vs)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Query ch (0-3):"))
        spin_qch = QSpinBox()
        spin_qch.setRange(0, 3)
        spin_qch.setValue(1)
        row.addWidget(spin_qch)
        for label, suffix in [("?Voltage", "V"), ("?Current", "I"), ("?Temp", "T")]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, ch=spin_qch, s=suffix: self._send("P" + str(ch.value()) + s, query=True))
            row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)

        return box

    def _build_motor_current(self) -> QGroupBox:
        box = QGroupBox("Motor Current")
        layout = QVBoxLayout(box)

        for label, cmd in [("SIR  IRUN (0-31):", "SIR"), ("SIH  IHOLD (0-31):", "SIH")]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            spin = QSpinBox()
            spin.setRange(0, 31)
            btn = QPushButton("Set")
            btn.clicked.connect(lambda _, c=cmd, s=spin: self._send(c, params=[s.value()]))
            row.addWidget(spin)
            row.addWidget(btn)
            layout.addLayout(row)

        return box

    def _build_half_bridge(self) -> QGroupBox:
        box = QGroupBox("Half Bridge (BcX, c=1-4)")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        row.addWidget(QLabel("Channel (1-4):"))
        spin_ch = QSpinBox()
        spin_ch.setRange(1, 4)
        row.addWidget(spin_ch)
        row.addWidget(QLabel("Output:"))
        combo_out = QComboBox()
        combo_out.addItem("0 - off", "0")
        combo_out.addItem("1 - on", "1")
        btn_cs = QPushButton("Set BcC")
        btn_cg = QPushButton("?BcC")
        btn_cs.clicked.connect(lambda _, ch=spin_ch, c=combo_out: self._send("B" + str(ch.value()) + "C", params=[c.currentData()]))
        btn_cg.clicked.connect(lambda _, ch=spin_ch: self._send("B" + str(ch.value()) + "C", query=True))
        row.addWidget(combo_out)
        row.addWidget(btn_cs)
        row.addWidget(btn_cg)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Duty cycle (0-100):"))
        spin_d = QSpinBox()
        spin_d.setRange(0, 100)
        btn_ds = QPushButton("Set BcD")
        btn_dg = QPushButton("?BcD")
        btn_ds.clicked.connect(lambda _, ch=spin_ch, s=spin_d: self._send("B" + str(ch.value()) + "D", params=[s.value()]))
        btn_dg.clicked.connect(lambda _, ch=spin_ch: self._send("B" + str(ch.value()) + "D", query=True))
        row.addWidget(spin_d)
        row.addWidget(btn_ds)
        row.addWidget(btn_dg)
        layout.addLayout(row)

        row = QHBoxLayout()
        for label, suffix in [("?BcI Current", "I"), ("?BcV Voltage", "V"), ("?BcT Temp", "T")]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, ch=spin_ch, s=suffix: self._send("B" + str(ch.value()) + s, query=True))
            row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)

        return box

    def _build_optical(self) -> QGroupBox:
        box = QGroupBox("Optically Isolated (OcX, c=1-2)")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        row.addWidget(QLabel("Channel (1-2):"))
        spin_ch = QSpinBox()
        spin_ch.setRange(1, 2)
        row.addWidget(spin_ch)
        row.addWidget(QLabel("State (0/1):"))
        spin_s = QSpinBox()
        spin_s.setRange(0, 1)
        btn_cs = QPushButton("Set OcC")
        btn_cg = QPushButton("?OcC")
        btn_cs.clicked.connect(lambda _, ch=spin_ch, s=spin_s: self._send("O" + str(ch.value()) + "C", params=[s.value()]))
        btn_cg.clicked.connect(lambda _, ch=spin_ch: self._send("O" + str(ch.value()) + "C", query=True))
        row.addWidget(spin_s)
        row.addWidget(btn_cs)
        row.addWidget(btn_cg)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Duty cycle (0-100):"))
        spin_d = QSpinBox()
        spin_d.setRange(0, 100)
        btn_ds = QPushButton("Set OcD")
        btn_dg = QPushButton("?OcD")
        btn_ds.clicked.connect(lambda _, ch=spin_ch, s=spin_d: self._send("O" + str(ch.value()) + "D", params=[s.value()]))
        btn_dg.clicked.connect(lambda _, ch=spin_ch: self._send("O" + str(ch.value()) + "D", query=True))
        row.addWidget(spin_d)
        row.addWidget(btn_ds)
        row.addWidget(btn_dg)
        layout.addLayout(row)

        return box

    def _build_fan(self) -> QGroupBox:
        box = QGroupBox("Fan Control (F1x - single channel)")
        layout = QHBoxLayout(box)
        for label, cmd, params, query in [
            ("Enable", "F1C", [1], False),
            ("Disable", "F1C", [0], False),
            ("?State", "F1C", None, True),
            ("?Voltage", "F1V", None, True),
            ("?Current", "F1I", None, True),
            ("?Duty", "F1D", None, True),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, c=cmd, p=params, q=query: self._send(c, params=p, query=q))
            layout.addWidget(btn)
        layout.addWidget(QLabel("  Duty (0-100):"))
        spin_d = QSpinBox()
        spin_d.setRange(0, 100)
        spin_d.setValue(50)
        btn_fd = QPushButton("Set F1D")
        btn_fd.clicked.connect(lambda _, s=spin_d: self._send("F1D", params=[s.value()]))
        layout.addWidget(spin_d)
        layout.addWidget(btn_fd)
        return box

    def _build_xio(self) -> QGroupBox:
        box = QGroupBox("XIO GPIO (XcS, c=0-7)")
        layout = QHBoxLayout(box)
        layout.addWidget(QLabel("Pin (0-7):"))
        spin_pin = QSpinBox()
        spin_pin.setRange(0, 7)
        layout.addWidget(spin_pin)
        layout.addWidget(QLabel("State (0/1):"))
        spin_s = QSpinBox()
        spin_s.setRange(0, 1)
        btn_set = QPushButton("Set")
        btn_get = QPushButton("Get")
        btn_set.clicked.connect(lambda _, p=spin_pin, s=spin_s: self._send("X" + str(p.value()) + "S", params=[s.value()]))
        btn_get.clicked.connect(lambda _, p=spin_pin: self._send("X" + str(p.value()) + "S", query=True))
        layout.addWidget(spin_s)
        layout.addWidget(btn_set)
        layout.addWidget(btn_get)
        return box

    # ------------------------------------------------------------------
    # Debug tab
    # ------------------------------------------------------------------

    def _build_tmc_register(self) -> QGroupBox:
        box = QGroupBox("TMC5160 Register (MxM)")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        row.addWidget(QLabel("Register addr (0-255):"))
        spin_addr = QSpinBox()
        spin_addr.setRange(0, 255)
        row.addWidget(spin_addr)
        row.addWidget(QLabel("Value:"))
        spin_val = QSpinBox()
        spin_val.setRange(0, 0x7FFFFFFF)
        row.addWidget(spin_val)
        layout.addLayout(row)

        row = QHBoxLayout()
        btn_write = QPushButton("Write MxM")
        btn_read = QPushButton("Read ?MxM")
        btn_write.clicked.connect(
            lambda _, a=spin_addr, v=spin_val: self._send_axis("MxM", params=[a.value(), v.value()])
        )
        btn_read.clicked.connect(
            lambda _, a=spin_addr: self._send_axis("MxM", params=[a.value()], query=True)
        )
        row.addWidget(btn_write)
        row.addWidget(btn_read)
        layout.addLayout(row)

        return box

    def _build_debug_actions(self) -> QGroupBox:
        box = QGroupBox("Debug Actions")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        for label, cmd in [
            ("PSE  Print settings", "PSE"),
            ("RSE  Refresh EEPROM", "RSE"),
            ("PMD  Print motor debug", "PMD"),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, c=cmd: self._send(c))
            row.addWidget(btn)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("SFT  Fake temp (deg C, outside -100..200 to disable):"))
        spin_t = QDoubleSpinBox()
        spin_t.setRange(-200, 300)
        spin_t.setDecimals(1)
        btn = QPushButton("Set SFT")
        btn.clicked.connect(lambda _, s=spin_t: self._send("SFT", params=[s.value()]))
        row.addWidget(spin_t)
        row.addWidget(btn)
        layout.addLayout(row)

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
