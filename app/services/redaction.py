from __future__ import annotations

import re
from typing import Final

SECRET_PATTERNS: Final[list[tuple[re.Pattern[str], str]]] = [
    (re.compile(r'(?im)^(\s*username\s+\S+\s+privilege\s+\d+\s+secret(?:\s+\d+)?\s+).+$'), r'\1<redacted>'),
    (re.compile(r'(?im)^(\s*username\s+\S+\s+secret(?:\s+\d+)?\s+).+$'), r'\1<redacted>'),
    (re.compile(r'(?im)^(\s*enable\s+secret\s+).+$'), r'\1<redacted>'),
    (re.compile(r'(?im)^(\s*snmp-server\s+community\s+)(\S+)'), r'\1<redacted>'),
    (re.compile(r'(?im)^(\s*set\s+system\s+root-authentication\s+encrypted-password\s+).+$'), r'\1<redacted>;'),
    (re.compile(r'(?im)^(\s*set\s+system\s+login\s+user\s+\S+\s+authentication\s+encrypted-password\s+).+$'), r'\1<redacted>;'),
    (re.compile(r'(?im)^(/user\s+add\s+[^\n]*password=)(\S+)'), r'\1<redacted>'),
]


def redact_config_text(config_text: str) -> str:
    redacted = config_text
    for pattern, replacement in SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted
