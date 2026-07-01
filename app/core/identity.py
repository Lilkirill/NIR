from __future__ import annotations

import re
from typing import Optional


def normalize_hostname(hostname: str) -> str:
    value = (hostname or '').strip().lower()
    value = re.sub(r'\s+', '-', value)
    return value


def build_identity_key(
    vendor: str,
    hostname: str,
    management_ip: Optional[str] = None,
    explicit_device_id: Optional[int] = None,
) -> str:
    vendor_part = (vendor or '').strip().lower()
    if explicit_device_id is not None:
        return f'{vendor_part}::device::{explicit_device_id}'
    if management_ip:
        return f'{vendor_part}::ip::{management_ip.strip()}'
    return f'{vendor_part}::host::{normalize_hostname(hostname)}'
