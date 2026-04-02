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
