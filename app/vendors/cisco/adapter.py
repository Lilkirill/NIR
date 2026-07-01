from __future__ import annotations

from app.parsers.cisco import CiscoParser
from app.vendors.base.adapter import BaseVendorAdapter


class CiscoAdapter(BaseVendorAdapter):
    vendor_name = 'cisco'

    def parse(self, hostname: str, config_text: str) -> dict:
        return CiscoParser().parse(hostname=hostname, config_text=config_text)

    def supported_profiles(self) -> list[str]:
        return ['default', 'branch-router', 'dc-leaf', 'edge-router', 'firewall']
