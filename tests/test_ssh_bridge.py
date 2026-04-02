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
    for s in ("connected", "disconnected", "rx_data", "tx_logged", "error", "status_update"):
        assert hasattr(b, s)


def test_send_when_not_connected_does_not_raise():
    b = SSHBridge("192.168.1.100", 22, "silentsentinel", "Sentinel123")
    b.send_command("P RESET\r\n")


def test_stop_clears_running():
    b = SSHBridge("192.168.1.100", 22, "silentsentinel", "Sentinel123")
    b._running = True
    b.stop()
    assert not b._running
