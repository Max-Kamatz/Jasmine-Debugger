
# Jasmine Debugger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PyQt6 desktop tool that SSHes into an AAEON SBC, stops JafarService, opens a Python serial relay to the Jasmine PCBA, and provides a structured command panel plus live Tx/Rx log with export.

**Architecture:** A single `SSHBridge` QThread handles the full connection lifecycle (SSH connect, stop service, discover port, launch remote serial relay, read loop). The UI has three widgets: `CommandPanel` (left), `CommsLog` (right), and `MainWindow` (wires them). A pure-logic `command_builder` module formats all Jasmine ASCII commands.

**Tech Stack:** Python 3.x, PyQt6, paramiko, pyinstaller (build only)

---

## File Map

| File | Responsibility |
|---|---|
| `main.py` | Entry point |
| `core/__init__.py` | Package marker |
| `core/command_builder.py` | Pure logic: format Jasmine ASCII commands + optional checksum |
| `workers/__init__.py` | Package marker |
| `workers/ssh_bridge.py` | QThread: SSH connect, service stop, port discovery, serial relay, read loop |
| `ui/__init__.py` | Package marker |
| `ui/main_window.py` | Top-level window, toolbar, splitter, signal wiring |
| `ui/command_panel.py` | Left panel: axis selector, grouped command buttons, manual send |
| `ui/comms_log.py` | Right panel: timestamped Tx/Rx table, clear, export |
| `tests/__init__.py` | Package marker |
| `tests/conftest.py` | Session-scoped QApplication fixture |
| `tests/test_command_builder.py` | Unit tests for command_builder (no Qt) |
| `tests/test_comms_log.py` | Widget smoke tests |
| `tests/test_command_panel.py` | Widget smoke tests |
| `tests/test_ssh_bridge.py` | Unit tests with mocked paramiko |
| `tests/test_main_window.py` | Smoke tests for MainWindow |
| `JasmineDebugger.spec` | PyInstaller build spec |

---

## Task 1: Project Scaffolding

**Files:** `main.py`, `core/__init__.py`, `workers/__init__.py`, `ui/__init__.py`, `tests/__init__.py`, `tests/conftest.py`, `requirements.txt`

- [ ] Create empty `__init__.py` in `core/`, `workers/`, `ui/`, `tests/`
- [ ] Create `requirements.txt` with contents: `PyQt6>=6.4.0` and `paramiko>=3.0.0`
- [ ] Create `main.py`:

```python
# main.py
import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1280, 800)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] Create `tests/conftest.py`:

```python
# tests/conftest.py
import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def qapp_instance():
    app = QApplication.instance() or QApplication([])
    yield app
    app.quit()
```

- [ ] Verify: `find . -name "*.py" | grep -v ".git" | sort`
- [ ] `git add . && git commit -m "feat: project scaffolding"`

---

## Task 2: core/command_builder.py (TDD)

**Files:** `core/command_builder.py`, `tests/test_command_builder.py`

### Command format
`[?][axis] [CMD] [param1] [param2] [!][\XX]\r\n`
- `?` prefix for queries (attached directly to axis, no space: `?P PS`)
- `!` appended after params for real-time updates
- `\XX` = backslash + 8-bit hex checksum (sum of all bytes before `\`)

- [ ] **Write failing tests** in `tests/test_command_builder.py`:

```python
from core.command_builder import build_command

def test_simple_no_params():
    assert build_command("P", "RESET") == "P RESET\r\n"

def test_float_param():
    assert build_command("P", "AA", params=[45.0]) == "P AA 45.0\r\n"

def test_int_param_no_decimal():
    result = build_command("P", "SPR", params=[200])
    assert result == "P SPR 200\r\n"
    assert "200.0" not in result

def test_multiple_params():
    assert build_command("P", "REG", params=[10, 255]) == "P REG 10 255\r\n"

def test_query():
    assert build_command("P", "PS", query=True) == "?P PS\r\n"

def test_query_both_axes():
    assert build_command("*", "VER", query=True) == "?* VER\r\n"

def test_both_axes_command():
    assert build_command("*", "RESET") == "* RESET\r\n"

def test_realtime_flag():
    assert build_command("P", "AA", params=[45.0], realtime=True) == "P AA 45.0 !\r\n"

def test_query_with_realtime():
    assert build_command("T", "PS", query=True, realtime=True) == "?T PS !\r\n"

def test_checksum_no_params():
    cmd_str = "P RESET"
    cs = sum(ord(c) for c in cmd_str) & 0xFF
    assert build_command("P", "RESET", checksum=True) == f"P RESET\\{cs:02X}\r\n"

def test_checksum_with_param():
    cmd_str = "P AA 45.0"
    cs = sum(ord(c) for c in cmd_str) & 0xFF
    assert build_command("P", "AA", params=[45.0], checksum=True) == f"P AA 45.0\\{cs:02X}\r\n"

def test_checksum_query():
    cmd_str = "?T PS"
    cs = sum(ord(c) for c in cmd_str) & 0xFF
    assert build_command("T", "PS", query=True, checksum=True) == f"?T PS\\{cs:02X}\r\n"

def test_checksum_with_realtime():
    cmd_str = "P AA 45.0 !"
    cs = sum(ord(c) for c in cmd_str) & 0xFF
    assert build_command("P", "AA", params=[45.0], realtime=True, checksum=True) == f"P AA 45.0 !\\{cs:02X}\r\n"
```

- [ ] Run: `pytest tests/test_command_builder.py -v` — expect FAIL (module not found)
- [ ] **Implement** `core/command_builder.py`:

```python
# core/command_builder.py

def build_command(
    axis: str,
    cmd: str,
    params: list | None = None,
    query: bool = False,
    realtime: bool = False,
    checksum: bool = False,
) -> str:
    """Format a Jasmine ASCII command string.

    Args:
        axis:     "P" (pan), "T" (tilt), or "*" (both/system)
        cmd:      Command mnemonic e.g. "AA", "PS", "RESET"
        params:   Optional list of numeric parameters
        query:    Prefix with "?" for query form
        realtime: Append "!" for real-time position updates
        checksum: Append backslash + 8-bit hex checksum
    """
    prefix = f"?{axis}" if query else axis
    parts = [prefix, cmd]
    if params:
        parts.extend(str(p) for p in params)
    if realtime:
        parts.append("!")
    cmd_str = " ".join(parts)
    if checksum:
        cs = sum(ord(c) for c in cmd_str) & 0xFF
        return f"{cmd_str}\\{cs:02X}\r\n"
    return f"{cmd_str}\r\n"
```

- [ ] Run: `pytest tests/test_command_builder.py -v` — expect all 13 PASS
- [ ] `git add core/command_builder.py tests/test_command_builder.py && git commit -m "feat: add command_builder with full test coverage"`

---

## Task 3: ui/comms_log.py

**Files:** `ui/comms_log.py`, `tests/test_comms_log.py`

### Design
- `QTableWidget(0, 3)` with columns: Timestamp, Dir, Data
- Tx rows: background `#0a1a3d`; Rx rows: `#0d2b14`
- Internal `_entries: list[tuple[str, str, str]]` for export
- Max 20,000 rows; oldest row pruned when exceeded

- [ ] **Write failing tests** in `tests/test_comms_log.py`:

```python
from ui.comms_log import CommsLog

def test_append_tx(qapp_instance):
    log = CommsLog()
    log.append_entry("Tx", "P AA 45.0")
    assert log._table.rowCount() == 1
    assert log._table.item(0, 1).text() == "Tx"
    assert log._table.item(0, 2).text() == "P AA 45.0"

def test_append_rx(qapp_instance):
    log = CommsLog()
    log.append_entry("Rx", "OK")
    assert log._table.item(0, 1).text() == "Rx"

def test_clear(qapp_instance):
    log = CommsLog()
    log.append_entry("Tx", "P AA 45.0")
    log.append_entry("Rx", "OK")
    log.clear_log()
    assert log._table.rowCount() == 0
    assert log._entries == []

def test_entries_accumulate(qapp_instance):
    log = CommsLog()
    log.append_entry("Tx", "P AA 45.0")
    log.append_entry("Rx", "PA 45.0")
    assert len(log._entries) == 2
    assert log._entries[0][1] == "Tx"
    assert log._entries[1][1] == "Rx"
```

- [ ] Run: `pytest tests/test_comms_log.py -v` — expect FAIL
- [ ] **Implement** `ui/comms_log.py`:
  - Controls row: Auto-scroll QCheckBox, Clear QPushButton, Export Log QPushButton
  - `append_entry(direction, text)`: timestamp `HH:MM:SS.mmm`, set row bg, append to `_entries`
  - `clear_log()`: clears table rows and `_entries`
  - `_on_export()`: QFileDialog filtering "CSV (*.csv);;Text (*.txt)"
  - `_export_csv(path)`: csv.writer with header `["Timestamp","Direction","Data"]`
  - `_export_txt(path)`: writes `[ts] [dir] text\n` per entry
- [ ] Run: `pytest tests/test_comms_log.py -v` — expect all 4 PASS
- [ ] `git add ui/comms_log.py tests/test_comms_log.py && git commit -m "feat: add CommsLog with Tx/Rx display and CSV/TXT export"`

---

## Task 4: ui/command_panel.py

**Files:** `ui/command_panel.py`, `tests/test_command_panel.py`

### Design
- Emits single `command_requested = pyqtSignal(str)` — never touches SSH bridge
- `set_enabled(bool)` — enables/disables `_scroll_content`, `_manual_field`, `_btn_manual_send`
- Axis selector: three checkable QPushButtons (P/T/*) in exclusive QButtonGroup; default P
- `_axis() -> str`: returns text of currently checked button
- Checksum QCheckBox; when checked, passes `checksum=True` to `build_command`
- All command groups in QScrollArea

### Command groups
- **Motion Steps** (QGroupBox): AS, OS, RS — each row: label + QSpinBox (value) + QDoubleSpinBox (timing, 0=omit) + QCheckBox ("!") + Send button
- **Motion Degrees** (QGroupBox): AA, OA, RA — same layout but QDoubleSpinBox for value
- **Velocity** (QGroupBox): VS row (QSpinBox + "Set VS" button), VA row (QDoubleSpinBox + "Set VA" button)
- **Queries** (QGroupBox): 7 single-click buttons — ?PS, ?PA, ?NS, ?NA, ?S, ?MODE, ?VER — each calls `_send(cmd, query=True)`
- **Limits** (QGroupBox): LUS (QSpinBox), LUA (QDoubleSpinBox), LLS (QSpinBox), LLA (QDoubleSpinBox) — each with Set button
- **Current** (QGroupBox): IHOLD, IRUN — each: QSpinBox(0-31) + Get button + Set button
- **System** (QGroupBox): RESET, SAVE, DEFAULTS, FIX, UNFIX, INITCOM — single-click buttons
- **Register** (QGroupBox): Addr QSpinBox(0-255) + "Set value" QCheckBox + value QSpinBox + Send button
- **Test/Misc** (QGroupBox): TEST (count QSpinBox + button), SHAKE (count QSpinBox + button), DIR +1 / DIR -1 buttons, SPR (QSpinBox + Set button)

### Manual send (below scroll area)
QLineEdit with placeholder + Send QPushButton. `_on_manual_send()`: strips text, appends `\r\n` if missing, emits `command_requested`, clears field.

- [ ] **Write failing tests** in `tests/test_command_panel.py`:

```python
from ui.command_panel import CommandPanel

def test_instantiates(qapp_instance):
    assert CommandPanel() is not None

def test_disabled_by_default(qapp_instance):
    assert not CommandPanel()._scroll_content.isEnabled()

def test_set_enabled(qapp_instance):
    p = CommandPanel()
    p.set_enabled(True)
    assert p._scroll_content.isEnabled()

def test_manual_send_signal(qapp_instance):
    p = CommandPanel()
    p.set_enabled(True)
    received = []
    p.command_requested.connect(received.append)
    p._manual_field.setText("P RESET")
    p._on_manual_send()
    assert received == ["P RESET\r\n"]

def test_manual_send_clears_field(qapp_instance):
    p = CommandPanel()
    p.set_enabled(True)
    p._manual_field.setText("P RESET")
    p._on_manual_send()
    assert p._manual_field.text() == ""

def test_default_axis_pan(qapp_instance):
    assert CommandPanel()._axis() == "P"
```

- [ ] Run: `pytest tests/test_command_panel.py -v` — expect FAIL
- [ ] **Implement** `ui/command_panel.py` per design above
- [ ] Run: `pytest tests/test_command_panel.py -v` — expect all 6 PASS
- [ ] `git add ui/command_panel.py tests/test_command_panel.py && git commit -m "feat: add CommandPanel with all Jasmine command groups"`

---

## Task 5: workers/ssh_bridge.py

**Files:** `workers/ssh_bridge.py`, `tests/test_ssh_bridge.py`

### Signals
`connected`, `disconnected`, `rx_data(str)`, `tx_logged(str)`, `error(str)`, `status_update(str)`

### Module-level helper
```python
def _find_jasmine_port(ls_output: str) -> str | None:
    """Return first token in any ls output line containing 'JASMINE', or None."""
    for line in ls_output.splitlines():
        for token in line.split():
            if "JASMINE" in token:
                return token
    return None
```

### Connection sequence in `run()` → `_run_session()`
1. `status_update.emit("Connecting via SSH...")` then `paramiko.SSHClient().connect(host, port=22, username, password, timeout=10)` — on failure: `error.emit(...)` and return
2. `status_update.emit("Stopping JafarService...")` then `_exec(f"echo '{password}' | sudo -S systemctl stop JafarService 2>&1")` — on failure: `error.emit(...)` and return
3. `status_update.emit("Locating JASMINE serial port...")` then `_exec("ls /dev/serial/by-id/ 2>/dev/null")` → `_find_jasmine_port(output)` — if None: `error.emit("JASMINE port not found in /dev/serial/by-id/")` and return
4. `_exec(f"readlink -f /dev/serial/by-id/{port_name}")` to resolve to absolute device path — if empty: error and return
5. `status_update.emit(f"Starting serial relay on {device_path}...")` — build relay script (see below), base64-encode it, open persistent SSH channel via `transport.open_session()`, call `channel.get_pty()` and `channel.exec_command(relay_cmd)` where `relay_cmd = f'python3 -c "import base64; <python_exec_builtin>(base64.b64decode(\"{encoded}\").decode())"'`
6. `msleep(500)` — if `channel.exit_status_ready()`: `error.emit("Serial relay failed to start")` and return
7. `_running = True`, `status_update.emit(...)`, `connected.emit()`
8. Read loop: `for raw_line in channel.makefile("rb"):` — decode UTF-8, strip CR/LF, if non-empty: `rx_data.emit(text)` — break if `not _running`

Note on relay command: The Python exec builtin (`exec`) is used inside the base64 decode wrapper. Replace `<python_exec_builtin>` with the actual Python builtin function name `exec`.

### Relay script template (base64-encoded before sending)
```
import serial, sys, threading, os
s = serial.Serial('{port}', 115200, timeout=0.1)
def _r():
    while True:
        try:
            d = s.read(256)
            if d:
                sys.stdout.buffer.write(d)
                sys.stdout.buffer.flush()
        except Exception:
            break
threading.Thread(target=_r, daemon=True).start()
try:
    while True:
        d = os.read(sys.stdin.fileno(), 256)
        if not d:
            break
        s.write(d)
except Exception:
    pass
```

### Other methods
- `send_command(text)`: if `_channel` is None or not `_running`, return silently. Otherwise `channel.sendall(text.encode("utf-8"))` + `tx_logged.emit(text.rstrip("\r\n"))`
- `stop()`: `_running = False`, close channel if not None
- `_exec(cmd)`: runs SSH command, returns `(exit_code == 0, stdout+stderr stripped)`
- `_restart_service()`: called in finally block — `_exec(f"echo '{password}' | sudo -S systemctl start JafarService 2>&1")`
- `_cleanup()`: sets `_channel = None`, closes SSH client

### `run()` structure
```python
def run(self) -> None:
    try:
        self._run_session()
    except Exception as exc:
        self.error.emit(f"Unexpected error: {exc}")
    finally:
        self._restart_service()
        self._cleanup()
        self.disconnected.emit()
```

- [ ] **Write failing tests** in `tests/test_ssh_bridge.py`:

```python
from workers.ssh_bridge import SSHBridge, _find_jasmine_port

def test_find_jasmine_port_found():
    ls = "usb-FTDI_JASMINE_COMPANION-if00-port0\nusb-OTHER-if00-port0\n"
    assert _find_jasmine_port(ls) == "usb-FTDI_JASMINE_COMPANION-if00-port0"

def test_find_jasmine_port_not_found():
    assert _find_jasmine_port("usb-OTHER-if00-port0\n") is None

def test_find_jasmine_port_case_sensitive():
    assert _find_jasmine_port("usb-ftdi_jasmine-if00\n") is None

def test_signals_exist():
    b = SSHBridge("192.168.1.100", 22, "silentsentinel", "Sentinel123")
    for s in ("connected","disconnected","rx_data","tx_logged","error","status_update"):
        assert hasattr(b, s)

def test_send_when_not_connected_does_not_raise():
    b = SSHBridge("192.168.1.100", 22, "silentsentinel", "Sentinel123")
    b.send_command("P RESET\r\n")

def test_stop_clears_running():
    b = SSHBridge("192.168.1.100", 22, "silentsentinel", "Sentinel123")
    b._running = True
    b.stop()
    assert not b._running
```

- [ ] Run: `pytest tests/test_ssh_bridge.py -v` — expect FAIL
- [ ] **Implement** `workers/ssh_bridge.py` per design above
- [ ] Run: `pytest tests/test_ssh_bridge.py -v` — expect all 6 PASS
- [ ] `git add workers/ssh_bridge.py tests/test_ssh_bridge.py && git commit -m "feat: add SSHBridge with remote serial relay and read loop"`

---

## Task 6: ui/main_window.py

**Files:** `ui/main_window.py`, `tests/test_main_window.py`

### Toolbar (left to right)
`IP:` QLineEdit (130px, `192.168.1.100`) | `User:` QLineEdit (110px, `silentsentinel`) | `Pass:` QLineEdit (110px, Password echo, `Sentinel123`) | Connect QPushButton | Disconnect QPushButton (disabled initially) | Status QLabel (expanding)

### Body
`QSplitter(Horizontal)`: left=`CommandPanel`, right=`CommsLog`, stretch factor 3 on right

### `_on_connect()`
1. Disable Connect button, set status "Connecting..."
2. Create `SSHBridge(ip, 22, user, password)`
3. Wire signals:
   - `bridge.connected` → `_on_connected`
   - `bridge.disconnected` → `_on_disconnected`
   - `bridge.rx_data` → `lambda t: comms_log.append_entry("Rx", t)`
   - `bridge.tx_logged` → `lambda t: comms_log.append_entry("Tx", t)`
   - `bridge.error` → `_on_error`
   - `bridge.status_update` → `status_label.setText`
   - `command_panel.command_requested` → `bridge.send_command`
4. `bridge.start()`

### Slots
- `_on_connected`: enable Disconnect, `command_panel.set_enabled(True)`
- `_on_disconnected`: `command_panel.set_enabled(False)`, enable Connect, disable Disconnect, status="Disconnected", `_bridge = None`
- `_on_error(msg)`: status=`f"Error: {msg}"`, enable Connect, disable Disconnect, `command_panel.set_enabled(False)`

### Style (`_STYLE` module constant)
```python
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
```

### closeEvent
`bridge.stop()` + `bridge.wait(3000)` before `super().closeEvent(event)`

- [ ] **Write failing tests** in `tests/test_main_window.py`:

```python
from ui.main_window import MainWindow

def test_instantiates(qapp_instance):
    assert MainWindow().windowTitle() == "Jasmine Debugger"

def test_initial_credentials(qapp_instance):
    w = MainWindow()
    assert w._ip_field.text() == "192.168.1.100"
    assert w._user_field.text() == "silentsentinel"

def test_disconnect_disabled_initially(qapp_instance):
    w = MainWindow()
    assert not w._btn_disconnect.isEnabled()
    assert w._btn_connect.isEnabled()

def test_status_label_initial(qapp_instance):
    assert MainWindow()._status_label.text() == "Disconnected"
```

- [ ] Run: `pytest tests/test_main_window.py -v` — expect FAIL
- [ ] **Implement** `ui/main_window.py`
- [ ] Run: `pytest -v` — expect ALL tests in the full suite PASS
- [ ] `git add ui/main_window.py tests/test_main_window.py && git commit -m "feat: add MainWindow wiring CommandPanel, CommsLog, SSHBridge"`

---

## Task 7: PyInstaller Packaging

**Files:** `JasmineDebugger.spec`, `.gitignore`

- [ ] `pip install PyQt6 paramiko pyinstaller`
- [ ] `pyinstaller --onefile --windowed --name JasmineDebugger main.py` (generates initial spec)
- [ ] **Overwrite `JasmineDebugger.spec`**:

```python
# JasmineDebugger.spec
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'paramiko.ed25519key',
        'paramiko.ecdsakey',
        'paramiko.dsskey',
        'paramiko.rsakey',
        'cryptography.hazmat.primitives.asymmetric.ed25519',
        'cryptography.hazmat.backends.openssl',
        'cryptography.hazmat.backends.openssl.backend',
        'PyQt6.sip',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='JasmineDebugger',
    debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, upx_exclude=[],
    runtime_tmpdir=None, console=False,
    disable_windowed_traceback=False,
    argv_emulation=False, target_arch=None,
    codesign_identity=None, entitlements_file=None,
)
```

- [ ] `pyinstaller JasmineDebugger.spec` — `dist/JasmineDebugger.exe` must be created with no errors
  - If any `ModuleNotFoundError` in build output: add missing module to `hiddenimports` and rebuild
- [ ] Smoke test: double-click `dist/JasmineDebugger.exe` — window opens, no console, no error dialogs
- [ ] Create `.gitignore`:
  ```
  dist/
  build/
  __pycache__/
  *.pyc
  *.pyo
  ```
- [ ] `git add JasmineDebugger.spec .gitignore && git commit -m "feat: add PyInstaller spec for single-exe build"`

---

## Spec Coverage

| Requirement | Task |
|---|---|
| SSH with pre-filled credentials | Task 6 toolbar |
| Stop JafarService on connect | Task 5 `_run_session` |
| Discover JASMINE port dynamically | Task 5 `_find_jasmine_port` |
| Python serial relay over SSH (base64-encoded) | Task 5 relay template |
| Restart JafarService on disconnect | Task 5 `_restart_service` |
| Axis selector P / T / * | Task 4 |
| All command groups (motion, velocity, limits, etc.) | Task 4 |
| Checksum toggle | Task 4 |
| Manual send | Task 4 |
| Comms log Tx/Rx coloured rows | Task 3 |
| Clear + Export log (CSV/TXT) | Task 3 |
| All error scenarios from spec | Tasks 5 + 6 |
| Dark theme consistent with Tilt-Tester-Lite | Task 6 `_STYLE` |
| Single exe via PyInstaller | Task 7 |
