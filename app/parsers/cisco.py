import re
from app.parsers.base import BaseParser
from app.parsers.utils import make_interface, mask_to_prefix

class CiscoParser(BaseParser):
    def parse(self, hostname: str, config_text: str) -> dict:
        interfaces, routes, users = [], [], []
        services = {
            'password_encryption': 'service password-encryption' in config_text,
            'ssh_enabled': 'transport input ssh' in config_text,
        }
        current = None
        for raw_line in config_text.splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped == '!':
                continue
            if stripped.startswith('hostname '):
                hostname = stripped.split(maxsplit=1)[1]
            elif stripped.startswith('interface '):
                if current:
                    interfaces.append(current)
                current = make_interface(stripped.split(maxsplit=1)[1])
            elif current and stripped.startswith('description '):
                current['description'] = stripped.split(maxsplit=1)[1]
            elif current and stripped.startswith('ip address '):
                parts = stripped.split()
                if len(parts) >= 4:
                    ip = parts[2]
                    mask = parts[3]
                    if ip.count('.') == 3 and mask.count('.') == 3:
                        current['addresses'].append(f"{ip}/{mask_to_prefix(mask)}")
            elif current and stripped == 'shutdown':
                current['enabled'] = False
            elif current and stripped == 'no shutdown':
                current['enabled'] = True
            elif stripped.startswith('ip route '):
                parts = stripped.split()
                if len(parts) >= 5:
                    routes.append({'destination': f"{parts[2]}/{mask_to_prefix(parts[3])}", 'next_hop': parts[4]})
            elif stripped.startswith('username '):
                match = re.match(r'username\s+(\S+)(?:\s+privilege\s+(\d+))?\s+secret(?:\s+\d+)?\s+(.+)', stripped)
                if match:
                    users.append({
                        'username': match.group(1),
                        'privilege': int(match.group(2)) if match.group(2) else 1,
                        'secret_configured': bool(match.group(3)),
                    })
        if current:
            interfaces.append(current)
        return {'vendor': 'cisco', 'hostname': hostname, 'interfaces': interfaces, 'routes': routes, 'services': services, 'users': users}
