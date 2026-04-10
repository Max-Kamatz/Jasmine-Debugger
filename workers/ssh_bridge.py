import base64
from typing import Optional, Tuple

import paramiko
from PyQt6.QtCore import QThread, pyqtSignal

RELAY_SCRIPT = """\
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
"""


def _find_jasmine_port(ls_output: str) -> Optional[str]:
    """Return first token in any ls output line containing 'JASMINE', or None."""
    for line in ls_output.splitlines():
        for token in line.split():
            if "JASMINE" in token:
                return token
    return None


class SSHBridge(QThread):
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    rx_data = pyqtSignal(str)
    tx_logged = pyqtSignal(str)
    error = pyqtSignal(str)
    status_update = pyqtSignal(str)

    def __init__(self, host: str, port: int, username: str, password: str, parent=None):
        super().__init__(parent)
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._running = False
        self._client: Optional[paramiko.SSHClient] = None
        self._channel: Optional[paramiko.Channel] = None
        self._service_name: Optional[str] = None

    def run(self) -> None:
        try:
            self._run_session()
        except Exception as exc:
            self.error.emit(f"Unexpected error: {exc}")
        finally:
            self._restart_service()
            self._cleanup()
            self.disconnected.emit()

    def _run_session(self) -> None:
        # 1. SSH connect
        self.status_update.emit("Connecting via SSH...")
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self._client.connect(
                self._host, port=self._port,
                username=self._username, password=self._password,
                timeout=10,
            )
        except Exception as exc:
            self.error.emit(f"SSH connection failed: {exc}")
            return

        # 2. Discover and stop the MotorControl service (name includes version suffix)
        self.status_update.emit("Locating MotorControl service...")
        self._service_name = self._find_motor_control_service()
        if self._service_name is None:
            self.error.emit("No running service containing 'MotorControl' found")
            return
        self.status_update.emit(f"Stopping {self._service_name}...")
        ok, output = self._exec_sudo(f"systemctl stop {self._service_name}")
        if not ok:
            self.error.emit(f"Failed to stop {self._service_name}: {output}")
            return

        # 3. Locate JASMINE serial port
        self.status_update.emit("Locating JASMINE serial port...")
        _, ls_output = self._exec("ls /dev/serial/by-id/ 2>/dev/null")
        port_name = _find_jasmine_port(ls_output)
        if port_name is None:
            self.error.emit("JASMINE port not found in /dev/serial/by-id/")
            return

        # 4. Resolve symlink to absolute device path
        ok, device_path = self._exec(f"readlink -f /dev/serial/by-id/{port_name}")
        if not device_path:
            self.error.emit(f"Could not resolve device path for {port_name}")
            return

        # 5. Launch serial relay over persistent SSH channel
        self.status_update.emit(f"Starting serial relay on {device_path}...")
        script = RELAY_SCRIPT.format(port=device_path)
        encoded = base64.b64encode(script.encode()).decode()
        relay_cmd = (
            'python3 -c '
            f'"import base64; exec(base64.b64decode(\\"{encoded}\\").decode())"'
        )

        transport = self._client.get_transport()
        self._channel = transport.open_session()
        self._channel.get_pty()
        self._channel.exec_command(relay_cmd)

        # 6. Give relay a moment to start; fail fast if it exits immediately
        self.msleep(500)
        if self._channel.exit_status_ready():
            self.error.emit("Serial relay failed to start")
            return

        # 7. Mark as connected
        self._running = True
        self.status_update.emit(f"Connected to {device_path}")
        self.connected.emit()

        # 8. Read loop
        for raw_line in self._channel.makefile("rb"):
            text = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if text:
                self.rx_data.emit(text)
            if not self._running:
                break

    def send_command(self, text: str) -> None:
        if self._channel is None or not self._running:
            return
        self._channel.sendall(text.encode("utf-8"))
        self.tx_logged.emit(text.rstrip("\r\n"))

    def stop(self) -> None:
        self._running = False
        if self._channel is not None:
            self._channel.close()

    def _exec(self, cmd: str) -> Tuple[bool, str]:
        """Run a command over SSH, return (success, stdout+stderr)."""
        _, stdout, stderr = self._client.exec_command(cmd)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        exit_code = stdout.channel.recv_exit_status()
        return exit_code == 0, (out + err).strip()

    def _exec_sudo(self, cmd: str) -> Tuple[bool, str]:
        """Run a command with sudo, feeding password via stdin."""
        channel = self._client.get_transport().open_session()
        channel.exec_command(f"sudo -S {cmd} 2>&1")
        channel.sendall(f"{self._password}\n".encode("utf-8"))
        channel.shutdown_write()
        out = channel.makefile("rb").read().decode("utf-8", errors="replace")
        exit_code = channel.recv_exit_status()
        channel.close()
        return exit_code == 0, out.strip()

    def _find_motor_control_service(self) -> Optional[str]:
        """Query running systemd services and return the name of the first
        unit whose name contains 'MotorControl', or None if not found."""
        _, output = self._exec(
            "systemctl list-units --type=service --state=running --no-legend --no-pager"
        )
        for line in output.splitlines():
            parts = line.split()
            if parts and "MotorControl" in parts[0]:
                return parts[0]
        return None

    def _restart_service(self) -> None:
        if self._client is None or self._client.get_transport() is None:
            return
        if self._service_name is None:
            return
        self._exec_sudo(f"systemctl start {self._service_name}")

    def _cleanup(self) -> None:
        self._channel = None
        if self._client is not None:
            self._client.close()
            self._client = None
