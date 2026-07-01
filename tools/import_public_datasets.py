#!/usr/bin/env python3
"""Optional importer for public external network configuration datasets.

This script is intentionally separate from the built-in mixed 1000-file dataset.
It downloads public repositories, extracts config-like files for vendors supported
by the project, and writes a separate manifest:

    configs/datasets/public_external/manifest_public_external.json

Use only when you have reviewed the source licenses and your environment permits
downloading public GitHub archives.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "configs" / "datasets" / "public_external"

SOURCES = {
    "batfish_lab_validation": {
        "url": "https://github.com/batfish/lab-validation/archive/refs/heads/main.zip",
        "license_note": "Public GitHub repository; check repository license before redistribution.",
    },
    "batfish_examples": {
        "url": "https://github.com/batfish/batfish/archive/refs/heads/master.zip",
        "license_note": "Batfish is Apache-2.0; preserve license notices when redistributing.",
    },
    "intentionet_test_pyramid": {
        "url": "https://github.com/intentionet/test-pyramid/archive/refs/heads/master.zip",
        "license_note": "Repository is Apache-2.0; preserve license notices when redistributing.",
    },
}


def guess_vendor(text: str, path: Path) -> str | None:
    lower = text.lower()
    suffix = path.suffix.lower()

    if "/system identity set" in lower or "/ip service" in lower or suffix == ".rsc":
        return "mikrotik"
    if "set system host-name" in lower or "system {" in lower and "junos" in lower or "routing-options" in lower:
        return "juniper"
    if "sysname " in lower or "stelnet server enable" in lower or "ip route-static" in lower:
        return "huawei"
    if "management ssh" in lower or "daemon terminattr" in lower or "eos" in lower:
        return "arista"
    if "hostname " in lower and ("interface " in lower or "ip route " in lower):
        return "cisco"
    if suffix in {".cfg", ".conf", ".txt"}:
        # Fallback: many public Batfish examples are IOS-like.
        if "line vty" in lower or "transport input" in lower:
            return "cisco"
    return None


def looks_like_config(path: Path) -> bool:
    return path.suffix.lower() in {".cfg", ".conf", ".txt", ".rsc", ".set"}


def download_zip(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=60) as response:
        dest.write_bytes(response.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit-per-vendor-source", type=int, default=100)
    parser.add_argument("--clean", action="store_true", help="Remove previously imported public_external files first.")
    args = parser.parse_args()

    if args.clean and OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    manifest: list[dict] = []

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for source_name, meta in SOURCES.items():
            zip_path = tmp / f"{source_name}.zip"
            print(f"Downloading {source_name}...")
            try:
                download_zip(meta["url"], zip_path)
            except Exception as exc:
                print(f"WARNING: failed to download {source_name}: {exc}")
                continue

            extract_dir = tmp / source_name
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(extract_dir)

            counters: dict[str, int] = {}
            for path in extract_dir.rglob("*"):
                if not path.is_file() or not looks_like_config(path):
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                vendor = guess_vendor(text, path)
                if vendor not in {"cisco", "juniper", "mikrotik", "arista", "huawei"}:
                    continue

                counters.setdefault(vendor, 0)
                if counters[vendor] >= args.limit_per_vendor_source:
                    continue
                counters[vendor] += 1

                out_dir = OUT_ROOT / vendor / "raw"
                out_dir.mkdir(parents=True, exist_ok=True)
                safe_name = f"{source_name}_{counters[vendor]:04d}_{path.name}".replace(" ", "_")
                out_path = out_dir / safe_name
                out_path.write_text(text, encoding="utf-8")

                manifest.append({
                    "path": str(out_path.relative_to(ROOT)).replace("\\", "/"),
                    "vendor": vendor,
                    "kind": "raw",
                    "origin": "public_external",
                    "source": source_name,
                    "source_url": meta["url"],
                    "license_note": meta["license_note"],
                })

    payload = {
        "dataset_name": "public_external_imported",
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_files": len(manifest),
        "files": manifest,
    }
    (OUT_ROOT / "manifest_public_external.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Imported {len(manifest)} public external config-like files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
