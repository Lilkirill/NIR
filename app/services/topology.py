from __future__ import annotations

from collections import defaultdict
from typing import Any


def validate_topology(items: list[dict[str, Any]]) -> dict[str, Any]:
    duplicate_ip_addresses: dict[str, list[str]] = defaultdict(list)
    duplicate_hostnames: list[str] = []
    seen_hostnames: set[str] = set()
    findings: list[dict[str, Any]] = []

    for item in items:
        hostname = item.get('hostname', '')
        if hostname in seen_hostnames:
            duplicate_hostnames.append(hostname)
            findings.append({
                'code': 'DUPLICATE_HOSTNAME',
                'severity': 'error',
                'category': 'topology',
                'message': f'Duplicate hostname detected: {hostname}',
                'path': 'hostname',
            })
        seen_hostnames.add(hostname)
        for iface in item.get('interfaces', []):
            for address in iface.get('addresses', []):
                duplicate_ip_addresses[address].append(hostname)

    duplicate_ip_addresses = {ip: sorted(set(hosts)) for ip, hosts in duplicate_ip_addresses.items() if len(set(hosts)) > 1}
    for ip, hosts in duplicate_ip_addresses.items():
        findings.append({
            'code': 'DUPLICATE_IP_ADDRESS',
            'severity': 'error',
            'category': 'topology',
            'message': f'Duplicate IP address {ip} detected on devices: {", ".join(hosts)}',
            'path': 'interfaces.addresses',
        })

    return {
        'findings': findings,
        'duplicate_ip_addresses': duplicate_ip_addresses,
        'duplicate_hostnames': sorted(set(duplicate_hostnames)),
    }
