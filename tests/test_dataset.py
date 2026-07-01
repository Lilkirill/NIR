import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.parsers.arista import AristaParser
from app.parsers.cisco import CiscoParser
from app.parsers.huawei import HuaweiParser
from app.parsers.juniper import JuniperParser
from app.parsers.mikrotik import MikroTikParser
from app.validators.rule_engine import RuleEngine


BASE_DIR = Path("configs/datasets")
client = TestClient(app)


def collect_files(folder: Path, patterns: tuple[str, ...]):
    if not folder.exists():
        return []
    files = []
    for pattern in patterns:
        files.extend(folder.rglob(pattern))
    return sorted(set(files))


def build_cases():
    cases = []

    vendor_map = {
        "cisco": {"patterns": ("*.cfg", "*.txt"), "parser": CiscoParser},
        "juniper": {"patterns": ("*.conf", "*.txt", "*.set"), "parser": JuniperParser},
        "mikrotik": {"patterns": ("*.rsc",), "parser": MikroTikParser},
        "arista": {"patterns": ("*.cfg", "*.txt"), "parser": AristaParser},
        "huawei": {"patterns": ("*.cfg", "*.txt"), "parser": HuaweiParser},
    }

    for vendor, meta in vendor_map.items():
        for kind in ("raw", "partial", "invalid"):
            folder = BASE_DIR / vendor / kind
            for path in collect_files(folder, meta["patterns"]):
                cases.append((path, vendor, kind))

    return cases


def build_api_cases(cases: list[tuple[Path, str, str]]):
    """Keep the default API smoke-test fast even with the 1000-file dataset.

    Set NCV_FULL_DATASET_API_TESTS=1 to validate every raw file through the API.
    Parser/rule tests still cover all files by default.
    """
    raw_cases = [(p, v, k) for p, v, k in cases if k == "raw"]
    if os.getenv("NCV_FULL_DATASET_API_TESTS") == "1":
        return raw_cases

    selected: list[tuple[Path, str, str]] = []
    per_vendor_limit = int(os.getenv("NCV_API_DATASET_PER_VENDOR_LIMIT", "5"))
    for vendor in ("cisco", "juniper", "mikrotik", "arista", "huawei"):
        vendor_cases = [(p, v, k) for p, v, k in raw_cases if v == vendor]
        curated = [case for case in vendor_cases if "regression_" not in case[0].name]
        regression = [case for case in vendor_cases if "regression_" in case[0].name]
        selected.extend((curated + regression)[:per_vendor_limit])
    return selected


DATASET_CASES = build_cases()
API_DATASET_CASES = build_api_cases(DATASET_CASES)


def test_dataset_has_expected_mixed_1000_size():
    assert len(DATASET_CASES) == 1000


@pytest.mark.parametrize(
    "path,vendor,kind",
    DATASET_CASES,
    ids=[f"{vendor}:{kind}:{path.name}" for path, vendor, kind in DATASET_CASES],
)
def test_dataset_parser_and_rules(path: Path, vendor: str, kind: str):
    text = path.read_text(encoding="utf-8", errors="ignore")

    parser_map = {
        "cisco": CiscoParser,
        "juniper": JuniperParser,
        "mikrotik": MikroTikParser,
        "arista": AristaParser,
        "huawei": HuaweiParser,
    }

    parser = parser_map[vendor]()
    parsed = parser.parse(path.name, text)

    assert isinstance(parsed, dict)
    assert parsed.get("vendor") == vendor
    assert "hostname" in parsed
    assert "interfaces" in parsed
    assert "routes" in parsed
    assert "services" in parsed
    assert "users" in parsed

    findings = RuleEngine().evaluate(parsed)
    assert isinstance(findings, list)

    if kind == "raw":
        assert parsed["hostname"] is not None

    if kind == "invalid":
        assert len(findings) > 0


@pytest.mark.parametrize(
    "path,vendor,kind",
    API_DATASET_CASES,
    ids=[f"{vendor}:{kind}:{path.name}" for path, vendor, kind in API_DATASET_CASES],
)
def test_dataset_api_validate_raw_configs(path: Path, vendor: str, kind: str):
    text = path.read_text(encoding="utf-8", errors="ignore")

    response = client.post(
        "/api/v1/validate",
        json={
            "vendor": vendor,
            "hostname": path.stem.lower(),
            "config_text": text,
            "metadata": {
                "source": "dataset-test",
                "file": path.name,
                "dataset_name": "ncv_5vendor_mixed_1000",
            },
            "source_scope": "dataset",
            "run_kind": "dataset",
            "expected_outcome": "regression",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["vendor"] == vendor
    assert payload["status"] in {"passed", "failed"}
    assert "report_json_path" in payload
    assert "metrics" in payload
