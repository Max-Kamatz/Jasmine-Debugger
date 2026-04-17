# Jasmine Debugger — User Guide

**Version:** 1.0  
**Audience:** Internal R&D / Systems Engineering  
**Hardware:** Jasmine PCBA (stepper motor + relay controller) via AAEON MTU4 SBC

---

## 1. Overview

Jasmine Debugger is a desktop diagnostic tool for direct serial access to the Jasmine PCBA. It establishes an SSH connection to the primary AAEON MTU4 SBC and opens a serial relay channel to the Jasmine board. Commands are sent and responses received in real time through the structured command panel.

The tool supports two connection modes:

- **Direct** — connects to the primary SBC, shuts down MotorControl via the ServiceManager API, then opens the serial relay on the primary host.
- **Hop** — connects to the primary SBC and tunnels through it to a secondary device (`10.10.10.2`–`10.10.10.7`). MotorControl shutdown is skipped; the serial relay runs on the secondary host.

**MotorControl must be restarted manually on the primary SBC after disconnecting from a direct session.**

---

## 2. Connection

Fields in the toolbar:

| Field | Default | Description |
|-------|---------|-------------|
| IP | 192.168.1.100 | IP address of the primary AAEON MTU4 SBC |
| User | silentsentinel | SSH username (applied to both primary and secondary hosts) |
| Port | 22 | SSH port |
| Pass | *(password)* | SSH password — used to authenticate and to invoke sudo for serial port access |
| Baud | 800000 | Serial baud rate — must match firmware configuration |
| Target | Primary (Direct) | Connection target — select **Primary (Direct)** or a secondary IP (`10.10.10.2`–`10.10.10.7`) |

The **Target** selector is disabled while connected and can only be changed after disconnecting.

Click **Connect** to begin the connection sequence.

**Direct connection (Target = Primary):**

1. SSH connection established to the primary SBC
2. MotorControl shut down via ServiceManager HTTP API
3. Jasmine serial port located under `/dev/serial/by-id/` and resolved on the primary host
4. Python serial relay launched on the primary host under sudo
5. Tool becomes ready — command panel enabled

**Hop connection (Target = 10.10.10.x):**

1. SSH connection established to the primary SBC
2. TCP tunnel opened through the primary to the selected secondary IP on port 22
3. SSH session authenticated on the secondary host
4. Jasmine serial port located under `/dev/serial/by-id/` and resolved on the secondary host
5. Python serial relay launched on the secondary host under sudo
6. Tool becomes ready — command panel enabled

Click **Disconnect** to close the serial relay and SSH session(s).

---

## 3. Communication Log

The log table on the right side of the window records all traffic with columns: **Timestamp**, **Dir**, **Data**.

| Dir | Colour | Meaning |
|-----|--------|---------|
| Tx | Blue | Command sent to device |
| Rx | Green | Response received from device |
| --- | Grey | Connection status message |
| ERR | Red | Error |

**Controls:**
- **Auto-scroll** — keeps the latest entry visible
- **Clear** — removes all rows from the display
- **Export Log** — saves log as CSV or TXT

The log holds up to 20,000 rows; oldest entries are discarded when the limit is reached.

---

## 4. Protocol

Commands follow the format:

```
={CMD} [p1 p2 ...]\r\n         set / action
=?{CMD} [p1 ...]\r\n           query
```

The axis letter (`P` for pan, `T` for tilt) is embedded in the command mnemonic where shown as `x` (e.g. `MxA` → `=MPA` or `=MTA`). Joint and system commands do not carry an axis letter.

An optional 8-bit checksum can be appended by enabling the **Checksum** checkbox. The checksum is the arithmetic sum of all command bytes, expressed as two hex digits, e.g. `=MPA 45.0\4F\r\n`.

---

## 5. Command Panel

The **Axis** selector (P / T) and **Checksum** checkbox at the top of the panel apply to all structured commands. A **Manual Send** field at the bottom allows raw command entry.

---

### 5.1 Motion Tab

#### Axis Motion

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `MxA` | angle (deg) | `=MPA 45.0` | Move axis to absolute position |
| `MxR` | offset (deg) | `=MPA 10.0` | Move axis by relative offset from current position |
| `MxJ` | velocity (deg/s) | `=MPJ 5.0` | Jog axis continuously at given velocity; use 0 to stop |
| `MxS` | — | `=MPS` | Stop axis immediately |
| `MxC` | angle (deg) | `=MPC 0.0` | Set current position register to given value |

#### Joint Motion

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `MJJ` | pan_vel, tilt_vel (deg/s) | `=MJJ 5.0 -3.0` | Jog both axes simultaneously at independent velocities |
| `MJS` | — | `=MJS` | Stop both axes |

#### Motion Queries

| Query | Example | Returns |
|-------|---------|---------|
| `?MxC` | `=?MPC` | Current axis angle (deg) |
| `?MxE` | `=?MPE` | Raw encoder count |
| `?MxA` | `=?MPA` | Current target position (deg) |
| `?MxS` | `=?MPS` | 1 if axis is stationary, 0 if moving |
| `?MxJ` | `=?MPJ` | 1 if axis is currently jogging |
| `?MxT` | `=?MPT` | Motor temperature (deg C) |
| `?MxI` | `=?MPI` | Motor current (A) |
| `?MJS` | `=?MJS` | 1 if both axes are stationary |

---

### 5.2 Vel/Profile Tab

#### Max Velocity

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `MxV` | vel (deg/s, 0–9999) | `=MPV 60.0` | Set maximum velocity for axis motion commands |
| `?MxV` | — | `=?MPV` | Query current max velocity setting |

#### Accel/Decel Profile (MxP)

Eight-parameter trapezoidal motion profile sent as a single command.

| # | Parameter | Example | Description |
|---|-----------|---------|-------------|
| f1 | Start velocity (deg/s) | 0.0 | Velocity at which motion begins |
| f2 | Initial acceleration (deg/s²) | 100.0 | Acceleration rate during initial phase |
| f3 | Initial target velocity (deg/s) | 30.0 | Velocity target at end of initial acceleration |
| f4 | Max acceleration (deg/s²) | 200.0 | Peak acceleration rate |
| f5 | Max velocity (deg/s) | 60.0 | Peak cruise velocity |
| f6 | Max deceleration (deg/s²) | 200.0 | Peak deceleration rate |
| f7 | Stop deceleration (deg/s²) | 100.0 | Final deceleration rate approaching stop |
| f8 | Release velocity (deg/s) | 0.0 | Velocity below which motion is considered complete |

Example: `=MPP 0.0 100.0 30.0 200.0 60.0 200.0 100.0 0.0`

Use **Get ?MxP** to read back the active profile.

#### Position Streaming

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `MxU` | period (ms, 0–10000) | `=MPU 100` | Set interval for unsolicited position update messages; 0 disables streaming |
| `?MxU` | — | `=?MPU` | Query current streaming period |

---

### 5.3 Config Tab

#### Axis Limits

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `MxL` | lower, upper (deg) | `=MPL -170.0 170.0` | Set software travel limits; motion commands are clamped to this range |
| `?MxL` | — | `=?MPL` | Query current limits |

#### Correction Sensitivity

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `MxD` | mismatch, stall (deg) | `=MPD 1.0 5.0` | Mismatch: max allowed encoder/commanded position error before correction triggers; Stall: threshold for stall detection |
| `?MxD` | — | `=?MPD` | Query current sensitivity settings |

#### Encoder

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `MxX` | ticks (int, 1–999999) | `=MPX 4096` | Encoder resolution in counts per revolution |
| `?MxX` | — | `=?MPX` | Query encoder resolution |
| `MxW` | constant (float) | `=MPW 0.0879` | Encoder scaling constant (degrees per tick) |
| `?MxW` | — | `=?MPW` | Query scaling constant |

#### Axis Flags

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `MxF` | flags (int, 0–255) | `=MPF 3` | Bitmask of axis behaviour flags; refer to firmware documentation for bit definitions |

---

### 5.4 Homing Tab

#### Run Homing

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `MJH` | [debug 0/1] | `=MJH` or `=MJH 1` | Home both axes; optional debug flag enables verbose homing output |
| `?MJH` | — | `=?MJH` | Query current homing status |
| `MxH` | mode (0–6) | `=MPH 3` | Home selected axis using specified mode |
| `?MxH` | — | `=?MPH` | Query current homing mode |

Homing modes:

| Value | Mode | Description |
|-------|------|-------------|
| 0 | Default | Firmware default homing behaviour |
| 1 | Manual | Software-triggered home position |
| 2 | Line | Line sensor-based homing |
| 3 | Limits | Travel-to-limit homing |
| 4 | Strip | Optical strip sensor homing |
| 5 | Notch | Notch/slot sensor homing |
| 6 | Zline | Z-index line homing |

#### Homing Velocities

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `MJV` | home_vel, post_vel [, self_corr_vel] (deg/s) | `=MJV 10.0 5.0` | Home search velocity and post-trigger settling velocity; optional third parameter sets self-correction velocity |
| `?MJV` | — | `=?MJV` | Query current homing velocity settings |

#### Homing Config

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `MxO` | offset (deg) | `=MPO 0.0` | Angular offset applied to position register after homing completes |
| `?MxO` | — | `=?MPO` | Query post-home offset |
| `MxK` | temp_offset (deg C) | `=MPK 0.0` | Temperature compensation offset applied during homing |
| `?MxK` | — | `=?MPK` | Query temperature compensation offset |
| `HDE` | delay (s, 0–9999) | `=HDE 0` | Delay before homing sequence begins |
| `?HDE` | — | `=?HDE` | Query homing delay |

---

### 5.5 System Tab

#### System Actions

| Command | Description |
|---------|-------------|
| `SL!` | Save current settings to non-volatile memory |
| `SLD` | Restore factory defaults (does not save automatically) |
| `SLR` | System reset; `?SLR` returns uptime |
| `SLB` | Reset communication buffers; `?SLB` returns buffer status |
| `?SLV` | Query firmware version string |
| `MJR` | Reset joint motion controller |
| `MJD` | Disable joint motion |

#### System Settings

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `SLM` | model (12/41/42) | `=SLM 42` | Set product model: 12 = AERON, 41 = JAEGAR V1, 42 = JAEGAR V2 |
| `?SLM` | — | `=?SLM` | Query model number |
| `SLS` | serial_no (int, 0–99999) | `=SLS 1234` | Set unit serial number |
| `?SLS` | — | `=?SLS` | Query serial number |
| `SLF` | flags (int, 0–65535) | `=SLF 0` | System-level control flags bitmask |
| `?SLF` | — | `=?SLF` | Query control flags |
| `SLT` | temp (deg C) | `=SLT 25.0` | Override reported system temperature |
| `?SLT` | — | `=?SLT` | Query system temperature |
| `?SLH` | — | `=?SLH` | Query ambient humidity (%) |
| `?SLI` | — | `=?SLI` | Query IMU data |
| `?SEV` | — | `=?SEV` | Query recent event log |

#### Cold Start

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `SLZ` | bits (int, 0–1023) | `=SLZ 0` | Heater configuration bitmask |
| `?SLZ` | — | `=?SLZ` | Query heater config |
| `SLC` | threshold (deg C) | `=SLC 5.0` | Temperature below which cold-start behaviour activates |
| `?SLC` | — | `=?SLC` | Query cold threshold |
| `SLW` | temp (deg C) | `=SLW 20.0` | Keep-warm target temperature |
| `?SLW` | — | `=?SLW` | Query keep-warm temperature |

#### Network

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `SLN` | ip, gateway, mask, port | `=SLN 192.168.1.100 192.168.1.1 255.255.255.0 8080` | Set network interface configuration |
| `?SLN` | — | `=?SLN` | Query current network settings |

---

### 5.6 Power/I-O Tab

#### Power Channels (PxC, x = 0–3)

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `PxC` | state (0/1) | `=P1C 1` | Enable (1) or disable (0) power channel x |
| `?PxC` | — | `=?P1C` | Query power channel state |
| `P2V` | voltage (V, 0–60) | `=P2V 12.0` | Set output voltage on channel 2 (programmable channel only) |
| `?PxV` | — | `=?P1V` | Query voltage on channel x (V) |
| `?PxI` | — | `=?P1I` | Query current draw on channel x (A) |
| `?PxT` | — | `=?P1T` | Query temperature on channel x (deg C) |

#### Motor Current

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `SIR` | irun (int, 0–31) | `=SIR 20` | Set motor run current (TMC5160 IRUN register); higher values = more current |
| `SIH` | ihold (int, 0–31) | `=SIH 8` | Set motor hold current (TMC5160 IHOLD register); typically set lower than IRUN |

#### Half Bridge (BcX, c = 1–4)

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `BcC` | state (0/1) | `=B1C 1` | Enable (1) or disable (0) half-bridge channel c |
| `?BcC` | — | `=?B1C` | Query half-bridge channel state |
| `BcD` | duty (int, 0–100) | `=B1D 50` | Set PWM duty cycle on half-bridge channel c (%) |
| `?BcD` | — | `=?B1D` | Query duty cycle |
| `?BcI` | — | `=?B1I` | Query current through half-bridge channel c (A) |
| `?BcV` | — | `=?B1V` | Query voltage on half-bridge channel c (V) |
| `?BcT` | — | `=?B1T` | Query temperature of half-bridge channel c (deg C) |

#### Optically Isolated (OcX, c = 1–2)

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `OcC` | state (0/1) | `=O1C 1` | Enable (1) or disable (0) opto-isolated output channel c |
| `?OcC` | — | `=?O1C` | Query channel state |
| `OcD` | duty (int, 0–100) | `=O1D 75` | Set PWM duty cycle on opto-isolated channel c (%) |
| `?OcD` | — | `=?O1D` | Query duty cycle |

#### Fan Control (F1x)

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `F1C` | state (0/1) | `=F1C 1` | Enable (1) or disable (0) fan |
| `?F1C` | — | `=?F1C` | Query fan enable state |
| `F1D` | duty (int, 0–100) | `=F1D 50` | Set fan PWM duty cycle (%) |
| `?F1D` | — | `=?F1D` | Query current fan duty cycle |
| `?F1V` | — | `=?F1V` | Query fan supply voltage (V) |
| `?F1I` | — | `=?F1I` | Query fan current (A) |

#### XIO GPIO (XcS, c = 0–7)

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `XcS` | state (0/1) | `=X3S 1` | Set GPIO pin c high (1) or low (0) |
| `?XcS` | — | `=?X3S` | Query current state of GPIO pin c |

---

### 5.7 Debug Tab

#### TMC5160 Register (MxM)

Direct read/write access to the TMC5160 stepper driver register file. Use with care — incorrect register values can affect motor behaviour or cause fault conditions.

| Command | Parameters | Example | Description |
|---------|-----------|---------|-------------|
| `MxM` | addr (0–255), value (int) | `=MPM 0 0x00000000` | Write value to TMC5160 register at address addr on selected axis |
| `?MxM` | addr (0–255) | `=?MPM 0` | Read current value of TMC5160 register at address addr |

Refer to the TMC5160 datasheet for register addresses and field definitions.

#### Debug Actions

| Command | Parameters | Description |
|---------|-----------|-------------|
| `PSE` | — | Print all current settings to the communications log |
| `RSE` | — | Re-read and refresh settings from EEPROM |
| `PMD` | — | Print motor debug dump (driver state, currents, flags) |
| `SFT` | temp (deg C) | Set a fake temperature for testing purposes; values outside −100 to 200 disable the override |

---

### 5.8 Manual Send

The text field at the bottom of the command panel sends raw text directly to the serial port. `\r\n` is appended automatically if not already present. Use for commands not covered by the structured panel, one-off experiments, or entering multi-parameter commands by hand.

---

## 6. Notes

- Settings changed via commands are **not persisted** unless `SL!` (Save) is issued.
- After disconnecting, **MotorControl must be restarted manually** on the SBC. The tool does not restart it automatically.
- Correct baud rate for this hardware is **800000**.
