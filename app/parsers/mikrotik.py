import re
from app.parsers.base import BaseParser
from app.parsers.utils import make_interface

class MikroTikParser(BaseParser):
    def parse(self, hostname: str, config_text: str) -> dict:
        interfaces, routes, users = {}, [], []
        services = {'ssh_enabled': '/ip service set ssh disabled=no' in config_text or 'name=ssh disabled=no' in config_text, 'password_encryption': True}
        match = re.search(r'/system identity set name=(\S+)', config_text)
        if match:
            hostname = match.group(1)
        for m in re.finditer(r'/interface ethernet add name=(\S+)(?: comment="([^"]+)")?', config_text):
            interfaces[m.group(1)] = make_interface(m.group(1), description=m.group(2) or '')
        for m in re.finditer(r'/ip address add address=(\d+\.\d+\.\d+\.\d+/\d+) interface=(\S+)', config_text):
            iface = interfaces.setdefault(m.group(2), make_interface(m.group(2)))
            iface['addresses'].append(m.group(1))
        for m in re.finditer(r'/ip route add dst-address=(\d+\.\d+\.\d+\.\d+/\d+) gateway=(\d+\.\d+\.\d+\.\d+)', config_text):
            routes.append({'destination': m.group(1), 'next_hop': m.group(2)})
        for m in re.finditer(r'/user add name=(\S+) group=(\S+)', config_text):
            users.append({'username': m.group(1), 'role': m.group(2), 'secret_configured': True})
        return {'vendor': 'mikrotik', 'hostname': hostname, 'interfaces': list(interfaces.values()), 'routes': routes, 'services': services, 'users': users}
