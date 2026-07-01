import re

from app.parsers.base import BaseParser
from app.parsers.utils import make_interface, mask_to_prefix


class HuaweiParser(BaseParser):
    """Parser for Huawei VRP display current-configuration text."""

    def parse(self, hostname: str, config_text: str) -> dict:
        interfaces: list[dict] = []
        routes: list[dict] = []
        users_by_name: dict[str, dict] = {}
        services = {
            'ssh_enabled': bool(
                re.search(r'^\s*(stelnet|ssh)\s+server\s+enable\b', config_text, re.MULTILINE)
                or re.search(r'^\s*local-user\s+\S+\s+service-type\s+.*\bssh\b', config_text, re.MULTILINE)
            ),
            'password_encryption': bool(
                re.search(r'\bpassword\s+(?:irreversible-cipher|cipher)\b', config_text)
                or re.search(r'\bset\s+authentication\s+password\s+(?:cipher|irreversible-cipher)\b', config_text)
            ),
        }

        current: dict | None = None
        in_interface = False

        for raw_line in config_text.splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped == '#':
                if current:
                    interfaces.append(current)
                    current = None
                in_interface = False
                continue

            if stripped.startswith('sysname '):
                hostname = stripped.split(maxsplit=1)[1]
                continue

            if stripped.startswith('interface '):
                if current:
                    interfaces.append(current)
                current = make_interface(stripped.split(maxsplit=1)[1])
                in_interface = True
                continue

            if in_interface and current:
                if stripped.startswith('description '):
                    current['description'] = stripped.split(maxsplit=1)[1]
                    continue
                if stripped.startswith('ip address '):
                    parts = stripped.split()
                    # ip address 10.0.0.1 255.255.255.0
                    if len(parts) >= 4 and parts[2].count('.') == 3 and parts[3].count('.') == 3:
                        current['addresses'].append(f"{parts[2]}/{mask_to_prefix(parts[3])}")
                    # ip address 10.0.0.1 24
                    elif len(parts) >= 4 and parts[2].count('.') == 3 and parts[3].isdigit():
                        current['addresses'].append(f"{parts[2]}/{parts[3]}")
                    continue
                if stripped == 'shutdown':
                    current['enabled'] = False
                    continue
                if stripped == 'undo shutdown':
                    current['enabled'] = True
                    continue
                if stripped == 'quit':
                    interfaces.append(current)
                    current = None
                    in_interface = False
                    continue

            if stripped.startswith('ip route-static '):
                parts = stripped.split()
                # ip route-static 0.0.0.0 0.0.0.0 10.0.0.254
                if len(parts) >= 5 and parts[2].count('.') == 3 and parts[3].count('.') == 3:
                    routes.append({'destination': f"{parts[2]}/{mask_to_prefix(parts[3])}", 'next_hop': parts[4]})
                continue

            if stripped.startswith('local-user '):
                parts = stripped.split()
                if len(parts) >= 2:
                    username = parts[1]
                    user = users_by_name.setdefault(username, {
                        'username': username,
                        'role': '',
                        'privilege': 1,
                        'secret_configured': False,
                    })
                    if 'privilege' in parts and 'level' in parts:
                        try:
                            user['privilege'] = int(parts[parts.index('level') + 1])
                        except (ValueError, IndexError):
                            pass
                    if 'password' in parts:
                        user['secret_configured'] = True
                    if 'service-type' in parts:
                        user['role'] = ' '.join(parts[parts.index('service-type') + 1:])

        if current:
            interfaces.append(current)

        return {
            'vendor': 'huawei',
            'hostname': hostname,
            'interfaces': interfaces,
            'routes': routes,
            'services': services,
            'users': list(users_by_name.values()),
        }
