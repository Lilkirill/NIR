import re
from app.parsers.base import BaseParser
from app.parsers.utils import make_interface

class JuniperParser(BaseParser):
    def parse(self, hostname: str, config_text: str) -> dict:
        interfaces_map, routes, users = {}, [], []
        services = {'ssh_enabled': 'system services ssh' in config_text or 'ssh;' in config_text, 'password_encryption': True}
        host_match = re.search(r'system\s*\{.*?host-name\s+(\S+);', config_text, re.DOTALL)
        if host_match:
            hostname = host_match.group(1)
        for m in re.finditer(r'(?:ge|xe|et)-\d+/\d+/\d+\s*\{', config_text):
            name = m.group(0).split()[0]
            interfaces_map.setdefault(name, make_interface(name))
        current_iface = None
        for line in config_text.splitlines():
            line = line.strip()
            if re.match(r'(?:ge|xe|et)-\d+/\d+/\d+\s*\{', line):
                current_iface = line.split()[0]
                interfaces_map.setdefault(current_iface, make_interface(current_iface))
            elif current_iface and line.startswith('address '):
                interfaces_map[current_iface]['addresses'].append(line.split()[1].rstrip(';'))
            elif line == '}':
                current_iface = current_iface
        for m in re.finditer(r'route\s+(\d+\.\d+\.\d+\.\d+/\d+)\s+next-hop\s+(\d+\.\d+\.\d+\.\d+);', config_text):
            routes.append({'destination': m.group(1), 'next_hop': m.group(2)})
        for m in re.finditer(r'user\s+(\S+)\s*\{.*?class\s+(\S+);', config_text, re.DOTALL):
            users.append({'username': m.group(1), 'role': m.group(2), 'secret_configured': 'encrypted-password' in config_text})
        return {'vendor': 'juniper', 'hostname': hostname, 'interfaces': list(interfaces_map.values()), 'routes': routes, 'services': services, 'users': users}
