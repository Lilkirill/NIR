import json
from pathlib import Path
from jsonschema import Draft202012Validator

BASE_DIR = Path(__file__).resolve().parents[2]
SCHEMA_PATH = BASE_DIR / 'schemas' / 'unified_config.schema.json'

class SchemaValidator:
    def __init__(self) -> None:
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
        self.validator = Draft202012Validator(self.schema)

    def validate(self, config: dict) -> list[dict]:
        findings = []
        for error in sorted(self.validator.iter_errors(config), key=lambda e: list(e.path)):
            path = '.'.join(str(p) for p in error.path) or '$'
            findings.append({'code': 'SCHEMA_ERROR', 'severity': 'error', 'message': error.message, 'path': path})
        return findings
