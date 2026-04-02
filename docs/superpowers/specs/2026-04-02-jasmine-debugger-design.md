# Jasmine Debugger — Design Spec
_Date: 2026-04-02_

## Overview

A PyQt6 desktop tool for Windows that connects to an AAEON MTU4 SBC (Ubuntu 24.04) via SSH, stops the `JafarService` motor control service to free the serial port, then establishes a live bidirectional serial link to the Jasmine PCBA (a stepper motor + relay controller). The user gets a structured command panel and a live raw comms log with Tx/Rx export.

---

## Architecture & File Structure

```
Jasmine-Debugger/
├── main.py
├── core/
│   ├── __init__.py
│   └── command_builder.py     # Formats Jasmine ASCII commands + optional checksum
├── workers/
│   ├── __init__.py
│   └── ssh_bridge.py          # QThread: SSH connect → stop service → find port → relay
├── ui/
│   ├── __init__.py
│   ├── main_window.py         # Top-level window, toolbar, layout
│   ├── command_panel.py       # Left panel: axis selector + grouped command buttons
│   └── comms_log.py           # Right panel: timestamped Tx/Rx log + export
└── Documentation/
    └── Jasmine commands.docx
```

---

## Connection Flow

All background work runs in `SSHBridge(QThread)`. The UI thread never blocks.

1. User clicks **Connect**
2. `paramiko.connect(ip, user, pass)` — SSH to AAEON
3. `exec_command("sudo systemctl stop JafarService")` — free the serial port
4. `exec_command("ls -la /dev/serial/by-id/")` — find the line containing `JASMINE`, resolve to full device path (e.g. `/dev/ttyUSB0`)
5. Open a persistent shell channel and launch a one-liner Python serial relay on the AAEON:
   ```
   python3 -c "import serial,sys,threading,os; s=serial.Serial('<port>',115200,timeout=0.1); ..."
   ```
   This bridges `stdin` → serial Tx and serial Rx → `stdout` over the SSH channel.
6. Emit `connected` signal → UI enables command panel
7. Read loop in the thread emits `rx_data(str)` for each line received from Jasmine
8. On **Disconnect**: close channel → `exec_command("sudo systemctl start JafarService")`

---

## UI Layout

### Toolbar (top bar)
- IP field — pre-filled `192.168.1.100`
- User field — pre-filled `silentsentinel`
- Password field — masked, pre-filled `Sentinel123`
- **Connect / Disconnect** toggle button
- Status label (`Disconnected` → `Connecting…` → `Connected` → error text)

### Body — horizontal QSplitter

**Left: Command Panel** (~380px minimum width, scrollable)

- Axis selector: `P` / `T` / `*` (three exclusive toggle buttons)
- Grouped commands:
  - **Motion** — AS, OS, RS (steps); AA, OA, RA (degrees) — each has a parameter field, optional timing field, and `!` (real-time updates) checkbox
  - **Velocity** — VS (steps/sec), VA (deg/sec)
  - **Position Queries** — `?PS`, `?PA`, `?NS`, `?NA`, `?S`, `?MODE`, `?VER` — single-click query buttons
  - **Limits** — LUS, LUA, LLS, LLA — each with a value field
  - **Current** — IHOLD, IRUN — get (query) or set (with value field)
  - **System** — RESET, SAVE, DEFAULTS, FIX, UNFIX, INITCOM — single-click
  - **Register** — REG — address field + optional value field
  - **Test/Misc** — TEST (count field), SHAKE (count field), DIR (+1/−1 selector), SPR (value field)
- **Manual send** — free-text input field + Send button (raw command entry)
- **Checksum toggle** — checkbox: "Append checksum" — appends `\XX` (8-bit arithmetic sum of all bytes before `\`) to every sent command

**Right: Comms Log** (stretches to fill remaining space)
- Timestamped rows: `[HH:MM:SS.mmm] [Tx/Rx] <raw text>`
- Tx lines: blue (`#3277ff`); Rx lines: green (`#3fb950`)
- **Clear** button
- **Export Log** button — saves in-memory log to `.txt` or `.csv` via `QFileDialog`

---

## Data Flow & Threading

```
UI Thread                          SSHBridge QThread
────────────────────────           ──────────────────────────────────
Connect clicked          ───────►  paramiko.connect()
                                   systemctl stop JafarService
                                   ls /dev/serial/by-id/ → JASMINE port
                                   launch Python serial relay on remote
                         ◄───────  connected signal → enable command panel

Send command             ───────►  write bytes to paramiko channel stdin
                         ◄───────  tx_logged(str) → Comms Log (blue)

                                   [read loop — blocks on channel stdout]
                         ◄───────  rx_data(str) → Comms Log (green)

Disconnect clicked       ───────►  close channel
                                   systemctl start JafarService
                         ◄───────  disconnected signal → reset UI
```

---

## Command Builder (`core/command_builder.py`)

Pure logic module — no threads, no Qt.

- **Input:** axis (`P`/`T`/`*`), command string, parameters (list), query flag, `!` flag, checksum flag
- **Output:** formatted ASCII string ready to write to the serial relay channel
- **Format:** `[?][axis][CMD] [param1] [param2] [!][\XX]\r\n`
- **Checksum:** 8-bit arithmetic sum of all bytes before the `\` character, formatted as two hex digits

---

## Log Export

`comms_log.py` maintains an in-memory list of `(timestamp, direction, text)` tuples throughout the session. On export:
- **TXT:** one line per entry: `[timestamp] [Tx/Rx] text`
- **CSV:** columns: `timestamp, direction, text`
- File saved via `QFileDialog.getSaveFileName`

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| SSH connection fails | Status label shows error, Connect button re-enabled |
| `JafarService` stop fails | Connection aborted, error in status label |
| `JASMINE` port not found | Status label: "JASMINE port not found", connection aborted |
| Serial relay fails to start | Status label error, connection aborted |
| SSH drops mid-session | Read loop exits → `disconnected` signal → UI resets, command panel disabled |
| Send while disconnected | Send buttons disabled — not possible by design |
| `JafarService` restart fails on disconnect | Warning logged to comms log (non-fatal) |

All errors from the worker thread emitted via `error(str)` signal → displayed in status label.

---

## Style

Dark theme consistent with Tilt-Tester-Lite:
```
background: #0d1117
foreground: #c9d1d9
input background: #161b22
border: #30363d
button: #3277ff
Tx colour: #3277ff
Rx colour: #3fb950
```

---

## Dependencies

- `PyQt6`
- `paramiko`
