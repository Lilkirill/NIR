from __future__ import annotations

from app.vendors.base.adapter import BaseVendorAdapter
from app.vendors.cisco.adapter import CiscoAdapter
from app.vendors.juniper.adapter import JuniperAdapter
from app.vendors.mikrotik.adapter import MikroTikAdapter
from app.vendors.arista.adapter import AristaAdapter
from app.vendors.huawei.adapter import HuaweiAdapter


VENDOR_REGISTRY: dict[str, BaseVendorAdapter] = {}


def register_vendor_adapter(vendor: str, adapter: BaseVendorAdapter) -> None:
    VENDOR_REGISTRY[vendor.lower()] = adapter


def supported_vendors() -> list[str]:
    return sorted(VENDOR_REGISTRY)


def get_vendor_adapter(vendor: str) -> BaseVendorAdapter:
    try:
        return VENDOR_REGISTRY[vendor.lower()]
    except KeyError as exc:
        raise ValueError(f'Unsupported vendor: {vendor}') from exc


register_vendor_adapter('cisco', CiscoAdapter())
register_vendor_adapter('juniper', JuniperAdapter())
register_vendor_adapter('mikrotik', MikroTikAdapter())
register_vendor_adapter('arista', AristaAdapter())
register_vendor_adapter('huawei', HuaweiAdapter())
