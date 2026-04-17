import base64
import json
import ssl
import urllib.request
from typing import Optional, Tuple

import paramiko
from PyQt6.QtCore import QThread, pyqtSignal

RELAY_SCRIPT = """\
import serial, sys, threading, os
s = serial.Serial('{port}', {baud}, timeout=0.1)
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
        s.flush()
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

    def __init__(self, host: str, port: int, username: str, password: str,
                 baud: int = 115200, hop_target: Optional[str] = None, parent=None):
        super().__init__(parent)
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._baud = baud
        self._hop_target = hop_target
        self._running = False
        self._client: Optional[paramiko.SSHClient] = None
        self._hop_client: Optional[paramiko.SSHClient] = None
        self._channel: Optional[paramiko.Channel] = None

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
        # 1. SSH into primary host
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

        if self._hop_target:
            # 2a. Hop — tunnel through primary to secondary; skip MotorControl shutdown
            self.status_update.emit(f"Hopping to {self._hop_target}...")
            try:
                hop_sock = self._client.get_transport().open_channel(
                    "direct-tcpip", (self._hop_target, 22), ("127.0.0.1", 0)
                )
                hop_transport = paramiko.Transport(hop_sock)
                hop_transport.connect(username=self._username, password=self._password)
                self._hop_client = paramiko.SSHClient()
                self._hop_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self._hop_client._transport = hop_transport
            except Exception as exc:
                self.error.emit(f"Hop to {self._hop_target} failed: {exc}")
                return
            serial_client = self._hop_client
        else:
            # 2b. Direct — shut down MotorControl on primary before touching the port
            self.status_update.emit("Shutting down MotorControl...")
            ok, err = self._shutdown_motor_control()
            if not ok:
                self.error.emit(f"ServiceManager shutdown failed: {err}")
                return
            self.msleep(2000)  # allow ServiceManager to release the port
            serial_client = self._client

        # 3. Locate JASMINE serial port on the target host
        self.status_update.emit("Locating JASMINE serial port...")
        _, ls_output = self._exec_on(serial_client, "ls /dev/serial/by-id/ 2>/dev/null")
        port_name = _find_jasmine_port(ls_output)
        if port_name is None:
            self.error.emit("JASMINE port not found in /dev/serial/by-id/")
            return

        # 4. Resolve symlink to absolute device path
        ok, device_path = self._exec_on(serial_client, f"readlink -f /dev/serial/by-id/{port_name}")
        if not device_path:
            self.error.emit(f"Could not resolve device path for {port_name}")
            return

        # 5. Launch serial relay over persistent SSH channel on the target host
        self.status_update.emit(f"Port: /dev/serial/by-id/{port_name} → {device_path}")
        self.status_update.emit(f"Starting serial relay on {device_path}...")
        script = RELAY_SCRIPT.format(port=device_path, baud=self._baud)
        encoded = base64.b64encode(script.encode()).decode()
        relay_cmd = (
            'sudo -S python3 -c '
            f'"import base64; exec(base64.b64decode(\\"{encoded}\\").decode())"'
        )

        transport = serial_client.get_transport()
        self._channel = transport.open_session()
        self._channel.exec_command(relay_cmd)
        # Feed sudo password via stdin; channel stays open for serial data after this
        self._channel.sendall(f"{self._password}\n".encode("utf-8"))

        # 6. Give relay a moment to start; fail fast if it exits immediately
        self.msleep(500)
        if self._channel.exit_status_ready():
            self.error.emit("Serial relay failed to start")
            return

        # 7. Mark as connected
        self._running = True
        target_label = self._hop_target if self._hop_target else self._host
        self.status_update.emit(f"Connected — {target_label} → {device_path}")
        self.connected.emit()

        # 8. Read loop — poll recv() to avoid blocking on newline detection
        buf = b""
        while self._running:
            if self._channel.recv_ready():
                buf += self._channel.recv(4096)
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    text = line.decode("utf-8", errors="replace").rstrip("\r")
                    if text:
                        self.rx_data.emit(text)
            elif self._channel.exit_status_ready():
                break
            else:
                self.msleep(10)

    def send_command(self, text: str) -> None:
        if self._channel is None or not self._running:
            return
        self._channel.sendall(text.encode("utf-8"))
        self.tx_logged.emit(text.rstrip("\r\n"))

    def stop(self) -> None:
        self._running = False
        if self._channel is not None:
            self._channel.close()

    def _exec_on(self, client: paramiko.SSHClient, cmd: str) -> Tuple[bool, str]:
        """Run a command on the given SSHClient, return (success, stdout+stderr)."""
        _, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        exit_code = stdout.channel.recv_exit_status()
        return exit_code == 0, (out + err).strip()

    def _exec(self, cmd: str) -> Tuple[bool, str]:
        return self._exec_on(self._client, cmd)

    def _exec_sudo(self, cmd: str) -> Tuple[bool, str]:
        """Run a command with sudo on the primary host, feeding password via stdin."""
        channel = self._client.get_transport().open_session()
        channel.exec_command(f"sudo -S {cmd} 2>&1")
        channel.sendall(f"{self._password}\n".encode("utf-8"))
        channel.shutdown_write()
        out = channel.makefile("rb").read().decode("utf-8", errors="replace")
        exit_code = channel.recv_exit_status()
        channel.close()
        return exit_code == 0, out.strip()

    def _shutdown_motor_control(self) -> Tuple[bool, str]:
        """POST a Shutdown request to ServiceManager for MotorControl."""
        url = f"https://{self._host}/SMv2/ServiceStatus"
        payload = json.dumps({"ServiceName": "MotorControl", "Op": "Shutdown"}).encode()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=10):
                pass
            return True, ""
        except Exception as exc:
            return False, str(exc)

    def _restart_service(self) -> None:
        pass  # MotorControl is restarted manually after disconnect

    def _cleanup(self) -> None:
        self._channel = None
        if self._hop_client is not None:
            try:
                self._hop_client.close()
            except Exception:
                pass
            self._hop_client = None
        if self._client is not None:
            self._client.close()
            self._client = None
