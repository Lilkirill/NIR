from __future__ import annotations

from typing import Any

from app.core.identity import normalize_hostname


def infer_run_context(
    *,
    metadata: dict[str, Any] | None,
    source_type: str,
    run_kind: str | None,
    source_scope: str | None,
    expected_outcome: str | None,
    environment: str | None,
) -> dict[str, Any]:
    metadata = metadata or {}
    source = str(metadata.get('source', '')).lower()
    dataset_name = metadata.get('dataset_name')
    inferred_run_kind = run_kind or 'api'
    inferred_source_scope = source_scope or ('production' if environment == 'production' else 'lab' if environment == 'lab' else 'unknown')
    inferred_expected = expected_outcome or 'unknown'
    is_test_data = False

    if 'pytest' in source:
        inferred_run_kind = run_kind or 'regression'
        inferred_source_scope = source_scope or 'lab'
        is_test_data = True
    elif 'dataset' in source:
        inferred_run_kind = run_kind or 'dataset'
        inferred_source_scope = source_scope or str(metadata.get('dataset_kind', 'dataset'))
        dataset_name = dataset_name or metadata.get('dataset_kind') or 'dataset'
        is_test_data = True
    elif 'negative' in source or 'manual-failed' in source:
        inferred_run_kind = run_kind or 'negative'
        inferred_expected = expected_outcome or 'failed'
        inferred_source_scope = source_scope or 'lab'
        is_test_data = True
    elif source_type == 'file' and 'collector' in metadata:
        inferred_run_kind = run_kind or 'collect'

    return {
        'run_kind': inferred_run_kind,
        'source_scope': inferred_source_scope,
        'expected_outcome': inferred_expected,
        'dataset_name': dataset_name,
        'is_test_data': is_test_data,
    }
