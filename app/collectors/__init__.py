from __future__ import annotations

from app.collectors.base import BaseCollector, CollectedConfig
from app.collectors.file import FileCollector
from app.collectors.ssh import SSHCollector


def get_collector(source_type: str) -> BaseCollector:
    registry = {
        'file': FileCollector(),
        'ssh': SSHCollector(),
    }
    try:
        return registry[source_type.lower()]
    except KeyError as exc:
        raise ValueError(f'Unsupported source_type: {source_type}') from exc


__all__ = ['BaseCollector', 'CollectedConfig', 'get_collector']
