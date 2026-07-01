from abc import ABC, abstractmethod
from typing import Any

class BaseParser(ABC):
    @abstractmethod
    def parse(self, hostname: str, config_text: str) -> dict[str, Any]:
        raise NotImplementedError
