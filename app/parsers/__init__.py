from app.parsers.base import BaseParser


def get_parser(vendor: str) -> BaseParser:
    normalized = vendor.lower()
    if normalized == 'cisco':
        from app.parsers.cisco import CiscoParser
        return CiscoParser()
    if normalized == 'juniper':
        from app.parsers.juniper import JuniperParser
        return JuniperParser()
    if normalized == 'mikrotik':
        from app.parsers.mikrotik import MikroTikParser
        return MikroTikParser()
    if normalized == 'arista':
        from app.parsers.arista import AristaParser
        return AristaParser()
    if normalized == 'huawei':
        from app.parsers.huawei import HuaweiParser
        return HuaweiParser()
    raise ValueError(f'Unsupported vendor: {vendor}')
