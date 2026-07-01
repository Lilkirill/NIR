from ipaddress import IPv4Interface

def mask_to_prefix(mask: str) -> int:
    return IPv4Interface(f'0.0.0.0/{mask}').network.prefixlen

def make_interface(name: str, description: str = '', enabled: bool = True, addresses: list[str] | None = None) -> dict:
    return {'name': name, 'description': description, 'enabled': enabled, 'addresses': addresses or []}
