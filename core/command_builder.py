# core/command_builder.py
from typing import Optional


def build_command(
    cmd: str,
    params: Optional[list] = None,
    query: bool = False,
    checksum: bool = False,
) -> str:
    """Format a Jasmine ASCII command string.

    Every command is prefixed with '=' (or '=?' for query form).
    The axis letter or channel digit must already be embedded in *cmd*
    by the caller, e.g. "MPA", "MTR", "MJS", "P1C".

    Args:
        cmd:      Full command mnemonic with axis/channel embedded,
                  e.g. "MPA", "MTR", "MJS", "SLR", "P1C"
        params:   Optional list of parameters (ints, floats, or strings)
        query:    Use '=?' prefix for query form
        checksum: Append backslash + 8-bit hex checksum
    """
    prefix = f"=?{cmd}" if query else f"={cmd}"
    parts = [prefix]
    if params:
        parts.extend(str(p) for p in params)
    cmd_str = " ".join(parts)
    if checksum:
        cs = sum(ord(c) for c in cmd_str) & 0xFF
        return f"{cmd_str}\\{cs:02X}\r\n"
    return f"{cmd_str}\r\n"
