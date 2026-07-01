from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import hashlib
import re

from app.core.config import settings

_EXTENSIONS = {
    'cisco': '.cfg',
    'juniper': '.conf',
    'mikrotik': '.rsc',
    'arista': '.cfg',
    'huawei': '.cfg',
}


@dataclass(slots=True)
class SavedConfig:
    path: str
    sha256: str
    size_bytes: int


@dataclass(slots=True)
class SavedArtifacts:
    raw: SavedConfig
    redacted: SavedConfig | None = None


def save_raw_config(vendor: str, hostname: str, config_text: str) -> str:
    return save_raw_config_details(vendor=vendor, hostname=hostname, config_text=config_text).path


def save_raw_config_details(vendor: str, hostname: str, config_text: str, subfolder: str | None = None) -> SavedConfig:
    safe_vendor = _slugify(vendor) or 'unknown'
    safe_hostname = _slugify(hostname) or 'unknown-host'
    timestamp = datetime.now(UTC).strftime('%Y%m%d_%H%M%S_%f')
    ext = _EXTENSIONS.get(vendor, '.txt')
    vendor_dir = settings.archived_configs_path / (subfolder or safe_vendor)
    vendor_dir.mkdir(parents=True, exist_ok=True)
    path = vendor_dir / f'{safe_hostname}_{timestamp}{ext}'
    path.write_text(config_text, encoding='utf-8')
    data = config_text.encode('utf-8')
    return SavedConfig(path=str(path), sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))


def save_config_bundle(vendor: str, hostname: str, config_text: str, redacted_text: str | None = None) -> SavedArtifacts:
    raw = save_raw_config_details(vendor=vendor, hostname=hostname, config_text=config_text)
    redacted = None
    if redacted_text is not None and redacted_text != config_text:
        redacted = save_raw_config_details(vendor=vendor, hostname=f'{hostname}_redacted', config_text=redacted_text, subfolder=f'{_slugify(vendor)}/redacted')
    return SavedArtifacts(raw=raw, redacted=redacted)


def read_file_source(path: str) -> str:
    file_path = Path(path)
    return file_path.read_text(encoding='utf-8', errors='ignore')


def _slugify(value: str) -> str:
    return re.sub(r'[^a-zA-Z0-9._-]+', '-', value).strip('-_.').lower()
