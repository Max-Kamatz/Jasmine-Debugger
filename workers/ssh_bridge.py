import base64
import json
import ssl
import urllib.request
from typing import Optional, Tuple

import paramiko
from PyQt6.QtCore import QThread, pyqtSignal

RELAY_SCRIPT = """\
import sys, threading, os

_PORT = '{port}'
_BAUD = {baud}

try:
    import serial
    _ser = serial.Serial(_PORT, _BAUD, timeout=0.1)
    def _read(): return _ser.read(256)
    def _write(d): _ser.write(d); _ser.flush()
except ImportError:
    import termios
    _B = {{9600:termios.B9600,19200:termios.B19200,38400:termios.B38400,
           57600:termios.B57600,115200:termios.B115200,230400:termios.B230400,
           460800:termios.B460800,921600:termios.B921600}}
    if _BAUD not in _B:
        raise RuntimeError('pyserial required for baud rate ' + str(_BAUD))
    _fd = os.open(_PORT, os.O_RDWR | os.O_NOCTTY)
    _a = termios.tcgetattr(_fd)
    _a[0] = 0; _a[1] = 0
    _a[2] = _B[_BAUD] | termios.CS8 | termios.CREAD | termios.CLOCAL
    _a[3] = 0; _a[4] = _B[_BAUD]; _a[5] = _B[_BAUD]
    _a[6][termios.VMIN] = 0; _a[6][termios.VTIME] = 1
    termios.tcsetattr(_fd, termios.TCSANOW, _a)
    def _read():
        try: return os.read(_fd, 256)
        except OSError: return b''
    def _write(d): os.write(_fd, d)

def _r():
    while True:
        try:
            d = _read()
            if d: sys.stdout.buffer.write(d); sys.stdout.buffer.flush()
        except Exception: break
threading.Thread(target=_r, daemon=True).start()
try:
    while True:
        d = os.read(sys.stdin.fileno(), 256)
        if not d: break
        _write(d)
except Exception: pass
"""



class SSHBridge(QThread):
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    rx_data = pyqtSignal(str)
    tx_logged = pyqtSignal(str)
    error = pyqtSignal(str)
    status_update = pyqtSignal(str)

    def __init__(self, host: str, port: int, username: str, password: str,
                 baud: int = 115200, hop_target: Optional[str] = None,
                 port_filter: str = "JASMINE",
                 companion_service: Optional[str] = None,
                 config: str = "MK4",
                 parent=None):
        super().__init__(parent)
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._baud = baud
        self._hop_target = hop_target
        self._port_filter = port_filter
        self._companion_service = companion_service
        self._config = config
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
            # 2a. Hop — tunnel through primary to secondary
            self.status_update.emit(f"Hopping to {self._hop_target}...")
            try:
                hop_sock = self._client.get_transport().open_channel(
                    "direct-tcpip", (self._hop_target, 22), ("127.0.0.1", 0),
                    timeout=10,
                )
                hop_sock.settimeout(10)
                hop_transport = paramiko.Transport(hop_sock)
                hop_transport.connect(username=self._username, password=self._password)
                self._hop_client = paramiko.SSHClient()
                self._hop_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self._hop_client._transport = hop_transport
            except Exception as exc:
                self.error.emit(f"Hop to {self._hop_target} failed: {exc}")
                return

            self.status_update.emit(f"Shutting down CompanionService on {self._hop_target}...")
            ok, err = self._shutdown_service_remote("CompanionService", self._hop_target)
            if not ok:
                self.error.emit(f"ServiceManager shutdown failed: {err}")
                return
            self.status_update.emit("Waiting for port release...")
            self.msleep(2000)

            serial_client = self._hop_client
        else:
            # 2b. Direct — shut down the relevant service before touching the port
            service = self._companion_service or "MotorControl"
            self.status_update.emit(f"Shutting down {service}...")
            if self._config == "MK4":
                ok, err = self._shutdown_service(service)
            else:
                ok, err = self._shutdown_svcmgr(service, self._host)
            if not ok:
                self.error.emit(f"ServiceManager shutdown failed: {err}")
                return
            if self._companion_service:
                self.status_update.emit("Waiting for port release...")
                self.msleep(2000)
            serial_client = self._client

        # 3 & 4. Poll for target serial port — udev may take time to settle after service exits
        self.status_update.emit(f"Locating {self._port_filter} serial port...")
        _FIND_CMD = (
            f'f=$(ls /dev/serial/by-id/ 2>/dev/null | grep -i {self._port_filter} | head -1);'
            ' [ -n "$f" ] && readlink -f /dev/serial/by-id/$f'
        )
        _MAX_ATTEMPTS = 15  # 15 × 2 s = 30 s ceiling
        device_path = ""
        for attempt in range(_MAX_ATTEMPTS):
            ok, out = self._exec_on(serial_client, _FIND_CMD)
            if ok and out:
                device_path = out
                break
            if attempt < _MAX_ATTEMPTS - 1:
                self.status_update.emit(
                    f"Port not ready, retrying ({attempt + 1}/{_MAX_ATTEMPTS - 1})..."
                )
                self.msleep(2000)
        if not device_path:
            self.error.emit(
                f"{self._port_filter} port not found in /dev/serial/by-id/ after 30 s"
            )
            return

        # 5. Launch serial relay over persistent SSH channel on the target host
        self.status_update.emit(f"Serial port: {device_path}")
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
            stderr = b""
            while self._channel.recv_stderr_ready():
                stderr += self._channel.recv_stderr(4096)
            detail = stderr.decode("utf-8", errors="replace").strip()
            msg = f"Serial relay failed to start: {detail}" if detail else "Serial relay failed to start"
            self.error.emit(msg)
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
        """Run a command on the given SSHClient, return (success, combined output)."""
        channel = client.get_transport().open_session()
        channel.set_combine_stderr(True)
        channel.exec_command(cmd)
        out = channel.makefile("rb").read().decode("utf-8", errors="replace")
        exit_code = channel.recv_exit_status()
        channel.close()
        return exit_code == 0, out.strip()

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

    def _shutdown_service(self, service_name: str) -> Tuple[bool, str]:
        """POST a Shutdown request to ServiceManager for the named service."""
        url = f"https://{self._host}/SMv2/ServiceStatus"
        payload = json.dumps({"ServiceName": service_name, "Op": "Shutdown"}).encode()
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

    def _shutdown_svcmgr(self, service_name: str, host: str) -> Tuple[bool, str]:
        """POST a service shutdown via the MK2 SvcMgr API (HTTP port 8000, multipart/form-data).

        Used for all MK2 shutdowns — MotorControl and CompanionService alike.
        """
        boundary = "----JasmineDebuggerBoundary"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="SvcShutdown"\r\n\r\n'
            f"{service_name}\r\n"
            f"--{boundary}--\r\n"
        ).encode()
        url = f"http://{host}:8000/SvcMgr/ActionCommand"
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10):
                pass
            return True, ""
        except Exception as exc:
            return False, str(exc)

    def _shutdown_service_remote(self, service_name: str, host: str) -> Tuple[bool, str]:
        """Shut down a service on a hop target via the primary host's ServiceManager proxy.

        MK4: HTTPS to /SMv2/Payloads/{hop_ip}/ServiceStatus with text/plain JSON body.
        MK2: HTTP port 8000 to /SvcMgr/Payload/{hop_ip}/ActionCommand with multipart body.
        """
        if self._config == "MK4":
            payload = json.dumps({"ServiceName": service_name, "Op": "Shutdown"}).encode()
            url = f"https://{self._host}/SMv2/Payloads/{host}/ServiceStatus"
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "text/plain;charset=UTF-8"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, context=ctx, timeout=10):
                    pass
                return True, ""
            except Exception as exc:
                return False, str(exc)
        else:
            boundary = "----JasmineDebuggerBoundary"
            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="SvcShutdown"\r\n\r\n'
                f"{service_name}\r\n"
                f"--{boundary}--\r\n"
            ).encode()
            url = f"http://{self._host}:8000/SvcMgr/Payload/{host}/ActionCommand"
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=10):
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
