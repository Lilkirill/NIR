from __future__ import annotations

from pathlib import Path
from typing import Any

from app.collectors.base import BaseCollector, CollectedConfig
from app.services.storage import read_file_source


class FileCollector(BaseCollector):
    source_type = 'file'

    def collect(self, **kwargs: Any) -> CollectedConfig:
        file_path = kwargs.get('file_path')
        vendor = kwargs.get('vendor')
        if not file_path:
            raise ValueError('file_path is required for file collection.')
        if not vendor:
            raise ValueError('vendor is required for file collection.')
        hostname = kwargs.get('hostname') or Path(file_path).stem
        metadata = dict(kwargs.get('metadata') or {})
        metadata.setdefault('collector', self.source_type)
        text = read_file_source(file_path)
        return CollectedConfig(
            vendor=vendor,
            hostname=hostname,
            config_text=text,
            source_type=self.source_type,
            source_ref=str(file_path),
            metadata=metadata,
        )
