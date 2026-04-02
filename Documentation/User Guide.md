# Jasmine Debugger — User Guide

## Connecting

Fill in the toolbar fields and click **Connect**:

| Field | Default | Notes |
|-------|---------|-------|
| IP | 192.168.1.100 | IP address of the AAEON SBC |
| Port | 22 | SSH port |
| User | silentsentinel | SSH username |
| Pass | Sentinel123 | SSH password |

On connect, the tool stops `JafarService` on the SBC, locates the Jasmine serial port, and launches a relay. Connection steps and any errors appear in the log panel on the right. When connected, the command panel enables and the Disconnect button becomes active. On disconnect (or error), `JafarService` is automatically restarted.

---

## Global Controls

### Axis Selector — P / T / *

Every command sent from the panel is prefixed with the selected axis:

- **P** — Pan axis only
- **T** — Tilt axis only
- **\*** — Both axes / system-level commands

The axis selector is at the top of the command panel. Only one axis can be active at a time.

### Checksum

When the **Checksum** checkbox is ticked, an 8-bit checksum is appended to every command in the form `\XX` (e.g. `P AA 45.0\A3`). The checksum is the sum of all character values in the command string, masked to one byte. Enable this if the firmware is configured to validate checksums.

---

## Command Groups

### Motion (Steps)

Moves the selected axis by a number of **motor steps** (integer counts). Useful for precise open-loop positioning when you know the exact step count rather than a degree angle.

| Control | Command | Description |
|---------|---------|-------------|
| AS | Absolute Steps | Move to an absolute step position |
| OS | Offset Steps | Move by a relative step offset from current position |
| RS | Reset Steps | Move to step position relative to the home reference |

**Fields per row:**
- **Value** (integer, ±999,999) — number of steps
- **t:** (decimal, 0–9999, shows `—` when zero) — optional timing parameter; when left at zero it is omitted from the command
- **!** checkbox — enables real-time position update streaming during the move
- **Send** — transmits the command

**Example:** AS with value `500`, t `—`, no `!` → sends `P AS 500`
**Example:** OS with value `-200`, t `2.5`, `!` checked → sends `P OS -200 2.5 !`

---

### Motion (Degrees)

Moves the selected axis by a number of **degrees** (decimal). Functionally identical layout to Motion (Steps) but uses floating-point degree values.

| Control | Command | Description |
|---------|---------|-------------|
| AA | Absolute Angle | Move to an absolute degree position |
| OA | Offset Angle | Move by a relative degree offset from current position |
| RA | Reset Angle | Move to degree position relative to the home reference |

**Fields per row:**
- **Value** (decimal, ±9,999.0°) — angle in degrees
- **t:** (decimal, 0–9999, shows `—` when zero) — optional timing; omitted when zero
- **!** checkbox — real-time position updates during move
- **Send** — transmits the command

**Example:** AA with value `90.0`, t `—` → sends `P AA 90.0`
**Example:** OA with value `-45.0`, `!` checked → sends `P OA -45.0 !`

---

### Velocity

Sets the motion velocity for the selected axis.

| Button | Command | Input | Description |
|--------|---------|-------|-------------|
| Set VS | VS | Integer (0–999,999) | Velocity in steps per second |
| Set VA | VA | Decimal (0.0–9,999.0) | Velocity in degrees per second |

Set the desired value in the spin box then click the corresponding button.

**Example:** VS with value `1000` → sends `P VS 1000`

---

### Queries

Single-click buttons that query the current state of the selected axis. No additional input required.

| Button | Command | Returns |
|--------|---------|---------|
| ?PS | PS | Current position in steps |
| ?PA | PA | Current position in degrees |
| ?NS | NS | Target/next position in steps |
| ?NA | NA | Target/next position in degrees |
| ?S | S | Motion status (moving, idle, etc.) |
| ?MODE | MODE | Current operating mode |
| ?VER | VER | Firmware version |

Responses appear as **Rx** rows in the log panel.

---

### Limits

Sets software travel limits for the selected axis. The upper limit must be greater than the lower limit.

| Label | Command | Input | Description |
|-------|---------|-------|-------------|
| LUS | LUS | Integer (steps) | Upper limit in steps |
| LUA | LUA | Decimal (degrees) | Upper limit in degrees |
| LLS | LLS | Integer (steps) | Lower limit in steps |
| LLA | LLA | Decimal (degrees) | Lower limit in degrees |

Enter the limit value and click **Set**.

**Example:** LUS with value `10000` → sends `P LUS 10000`

---

### Current

Controls the motor driver current for the selected axis. Values are in the range 0–31 (driver register units, not milliamps — consult the motor driver datasheet for the conversion).

| Label | Command | Description |
|-------|---------|-------------|
| IHOLD | IHOLD | Holding current (motor stationary) |
| IRUN | IRUN | Run current (motor moving) |

Each row has three controls:
- **Value** spin box (0–31)
- **Get** — queries the current value from firmware (response appears in log)
- **Set** — writes the spin box value to firmware

**Example:** IRUN Get → sends `?P IRUN`
**Example:** IHOLD Set with value `8` → sends `P IHOLD 8`

---

### System

Single-click commands that act on the selected axis (or both axes if `*` is selected). These have immediate effect — use with care.

| Button | Command | Description |
|--------|---------|-------------|
| RESET | RESET | Reset the axis controller |
| SAVE | SAVE | Save current settings to non-volatile memory |
| DEFAULTS | DEFAULTS | Restore factory default settings |
| FIX | FIX | Lock the axis (prevents motion commands) |
| UNFIX | UNFIX | Unlock the axis |
| INITCOM | INITCOM | Re-initialise communications |

---

### Register

Direct read/write access to a firmware register by address. For advanced debugging — consult the firmware documentation for register addresses and meanings.

**Fields:**
- **Addr** (0–255) — register address
- **Set value** checkbox — when ticked, the value field is included in the command (write); when unticked, only the address is sent (read)
- **Value** (0–255) — value to write (only used when **Set value** is ticked)
- **Send** — transmits the command

**Example (read):** Addr `5`, Set value unchecked → sends `P REG 5`
**Example (write):** Addr `5`, Set value checked, Value `128` → sends `P REG 5 128`

---

### Test/Misc

Miscellaneous test and configuration commands.

| Control | Command | Input | Description |
|---------|---------|-------|-------------|
| TEST | TEST | Count (1–9999) | Run a built-in self-test sequence N times |
| SHAKE | SHAKE | Count (1–9999) | Run a shake/oscillation test N times |
| DIR +1 | DIR | — | Set motor direction to forward (+1) |
| DIR -1 | DIR | — | Set motor direction to reverse (−1) |
| Set SPR | SPR | Integer (1–99,999) | Set steps per revolution |

---

## Manual Send

At the bottom of the command panel, below the scroll area, is a free-text input field. Type any raw command string and click **Send** (or press Enter). A `\r\n` terminator is automatically appended if not already present. This bypasses all command builder logic — the axis selector and checksum checkbox have no effect here.

**Example:** Type `* RESET` → sends `* RESET\r\n`

---

## Comms Log

The right-hand panel shows all traffic in chronological order:

| Row colour | Direction | Meaning |
|------------|-----------|---------|
| Dark blue | Tx | Command sent to Jasmine |
| Dark green | Rx | Response received from Jasmine |
| Dark red | ERR | Connection or communication error |
| Default | --- | Connection status update |

**Auto-scroll** — keeps the log scrolled to the latest entry. Uncheck to freeze the view.

**Clear** — removes all rows from the log display.

**Export Log** — saves the log to a file. Choose CSV (with Timestamp / Direction / Data columns) or plain text (`[HH:MM:SS.mmm] [Dir] data`).
