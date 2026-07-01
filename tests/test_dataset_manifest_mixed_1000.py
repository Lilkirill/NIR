import json
from pathlib import Path


MANIFEST_PATH = Path("configs/datasets/manifest_mixed_1000.json")


def test_manifest_mixed_1000_exists_and_counts_match_files():
    assert MANIFEST_PATH.exists()

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["dataset_name"] == "ncv_5vendor_mixed_1000"
    assert manifest["total_files"] == 1000
    assert manifest["origin_summary"]["curated_existing_project_or_sample_copy"] == 42
    assert manifest["origin_summary"]["regression_test_case"] == 958

    files = manifest["files"]
    assert len(files) == 1000

    for item in files:
        path = Path(item["path"])
        assert path.exists(), item["path"]
        assert item["vendor"] in {"cisco", "juniper", "mikrotik", "arista", "huawei"}
        assert item["kind"] in {"raw", "partial", "invalid"}
        assert item["origin"] in {"curated_existing_project", "curated_sample_copy", "regression_test_case"}


def test_manifest_has_balanced_vendor_counts():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    counts = manifest["counts"]

    for vendor in ("cisco", "juniper", "mikrotik", "arista", "huawei"):
        assert counts[vendor]["total"] == 200
        assert counts[vendor]["raw"] == 140
        assert counts[vendor]["partial"] == 45
        assert counts[vendor]["invalid"] == 15
