# core/command_builder.py
from typing import Optional


def build_command(
    axis: str,
    cmd: str,
    params: Optional[list] = None,
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
