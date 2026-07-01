import re

from app.parsers.base import BaseParser
from app.parsers.utils import make_interface, mask_to_prefix


class AristaParser(BaseParser):
    """Parser for Arista EOS running-config style text.

    EOS is intentionally handled as a separate vendor rather than as Cisco,
    because the rule catalog, profiles and capability reporting can diverge
    while the parser still reuses IOS-like syntax patterns where appropriate.
    """

    def parse(self, hostname: str, config_text: str) -> dict:
        interfaces: list[dict] = []
        routes: list[dict] = []
        users: list[dict] = []
        services = {
            'ssh_enabled': bool(
                re.search(r'^\s*management\s+ssh\b', config_text, re.MULTILINE)
                or re.search(r'^\s*ip\s+ssh\b', config_text, re.MULTILINE)
                or re.search(r'^\s*transport\s+input\s+ssh\b', config_text, re.MULTILINE)
            ),
            'password_encryption': bool(
                re.search(r'^\s*service\s+password-encryption\b', config_text, re.MULTILINE)
                or re.search(r'^\s*username\s+\S+\s+.*\bsecret\b', config_text, re.MULTILINE)
            ),
        }

        current: dict | None = None
        for raw_line in config_text.splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped == '!':
                if current:
                    interfaces.append(current)
                    current = None
                continue

            if stripped.startswith('hostname '):
                hostname = stripped.split(maxsplit=1)[1]
                continue

            if stripped.startswith('interface '):
                if current:
                    interfaces.append(current)
                current = make_interface(stripped.split(maxsplit=1)[1])
                continue

            if current and stripped.startswith('description '):
                current['description'] = stripped.split(maxsplit=1)[1]
                continue

            if current and stripped.startswith('ip address '):
                parts = stripped.split()
                # EOS commonly uses CIDR notation: ip address 10.0.0.1/24
                if len(parts) >= 3 and '/' in parts[2]:
                    current['addresses'].append(parts[2])
                # Also accept IOS-like dotted masks for compatibility.
                elif len(parts) >= 4 and parts[2].count('.') == 3 and parts[3].count('.') == 3:
                    current['addresses'].append(f"{parts[2]}/{mask_to_prefix(parts[3])}")
                continue

            if current and stripped == 'shutdown':
                current['enabled'] = False
                continue

            if current and stripped == 'no shutdown':
                current['enabled'] = True
                continue

            if stripped.startswith('ip route '):
                parts = stripped.split()
                # ip route 0.0.0.0/0 10.0.0.1
                if len(parts) >= 4 and '/' in parts[2]:
                    routes.append({'destination': parts[2], 'next_hop': parts[3]})
                # ip route 0.0.0.0 0.0.0.0 10.0.0.1
                elif len(parts) >= 5 and parts[2].count('.') == 3 and parts[3].count('.') == 3:
                    routes.append({'destination': f"{parts[2]}/{mask_to_prefix(parts[3])}", 'next_hop': parts[4]})
                continue

            if stripped.startswith('username '):
                match = re.match(r'username\s+(\S+)(?:\s+privilege\s+(\d+))?.*\b(secret|password)\b\s+(.+)', stripped)
                if match:
                    users.append({
                        'username': match.group(1),
                        'privilege': int(match.group(2)) if match.group(2) else 1,
                        'secret_configured': bool(match.group(4)),
                    })

        if current:
            interfaces.append(current)

        return {
            'vendor': 'arista',
            'hostname': hostname,
            'interfaces': interfaces,
            'routes': routes,
            'services': services,
            'users': users,
        }
