#!/usr/bin/env bash
set -euo pipefail
python tools/import_public_datasets.py --clean "$@"
