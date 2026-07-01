from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CollectedConfig:
    vendor: str
    hostname: str
    config_text: str
    source_type: str
    source_ref: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseCollector:
    source_type: str = 'base'

    def collect(self, **kwargs: Any) -> CollectedConfig:
        raise NotImplementedError
