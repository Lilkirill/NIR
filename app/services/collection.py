from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.collectors import get_collector
from app.core.identity import build_identity_key, normalize_hostname
from app.core.models import ConfigSnapshot, Device
from app.services.context import infer_run_context
from app.services.redaction import redact_config_text
from app.services.storage import save_config_bundle


class CollectionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def collect(self, **kwargs) -> dict:
        source_type = kwargs['source_type']
        collector = get_collector(source_type)
        collected = collector.collect(**kwargs)
        context = infer_run_context(
            metadata=collected.metadata,
            source_type=source_type,
            run_kind=kwargs.get('run_kind'),
            source_scope=kwargs.get('source_scope'),
            expected_outcome=kwargs.get('expected_outcome'),
            environment=kwargs.get('environment'),
        )
        redacted_text = redact_config_text(collected.config_text) if kwargs.get('redact_secrets') else None
        saved = save_config_bundle(
            vendor=collected.vendor,
            hostname=collected.hostname,
            config_text=collected.config_text,
            redacted_text=redacted_text,
        )
        device = _get_or_create_device(
            self.db,
            vendor=collected.vendor,
            hostname=collected.hostname,
            ip_address=kwargs.get('host'),
            site=kwargs.get('site'),
            role=kwargs.get('role'),
            environment=kwargs.get('environment'),
            collection_method=source_type,
            metadata=collected.metadata,
        )
        snapshot = ConfigSnapshot(
            device_id=device.id,
            vendor=collected.vendor,
            hostname=collected.hostname,
            source_type=collected.source_type,
            source_ref=collected.source_ref,
            source_scope=context['source_scope'],
            dataset_name=context['dataset_name'],
            is_test_data=context['is_test_data'],
            raw_config_path=saved.raw.path,
            redacted_config_path=saved.redacted.path if saved.redacted else None,
            raw_config_sha256=saved.raw.sha256,
            raw_config_size=saved.raw.size_bytes,
            collected_success='true',
            profile=kwargs.get('profile', 'default'),
            metadata_json=json.dumps(collected.metadata or {}, ensure_ascii=False),
        )
        self.db.add(snapshot)
        device.last_seen_at = datetime.now(UTC).replace(tzinfo=None)
        self.db.commit()
        self.db.refresh(snapshot)
        return {
            'snapshot_id': snapshot.id,
            'vendor': collected.vendor,
            'hostname': collected.hostname,
            'source_type': collected.source_type,
            'source_ref': collected.source_ref,
            'source_scope': context['source_scope'],
            'dataset_name': context['dataset_name'],
            'is_test_data': context['is_test_data'],
            'metadata': collected.metadata,
            'raw_config_path': saved.raw.path,
            'redacted_config_path': saved.redacted.path if saved.redacted else None,
            'raw_config_sha256': saved.raw.sha256,
            'raw_config_size': saved.raw.size_bytes,
            'config_text': collected.config_text,
            'profile': kwargs.get('profile', 'default'),
        }


def _append_alias(device: Device, previous_hostname: str | None) -> None:
    aliases = json.loads(device.aliases_json or '[]') if isinstance(device.aliases_json, str) else list(device.aliases_json or [])
    if previous_hostname and previous_hostname != device.hostname and previous_hostname not in aliases:
        aliases.append(previous_hostname)
    device.aliases_json = json.dumps(sorted(dict.fromkeys(aliases)), ensure_ascii=False)


def _get_or_create_device(
    db: Session,
    vendor: str,
    hostname: str,
    ip_address: str | None = None,
    site: str | None = None,
    role: str | None = None,
    environment: str | None = None,
    collection_method: str | None = None,
    metadata: dict[str, Any] | None = None,
    explicit_device_id: int | None = None,
) -> Device:
    hostname_normalized = normalize_hostname(hostname)
    identity_key = build_identity_key(vendor=vendor, hostname=hostname, management_ip=ip_address, explicit_device_id=explicit_device_id)
    now = datetime.now(UTC).replace(tzinfo=None)

    device = None
    if explicit_device_id is not None:
        device = db.query(Device).filter(Device.id == explicit_device_id).order_by(Device.id.asc()).first()
    if device is None:
        device = db.query(Device).filter(Device.identity_key == identity_key).order_by(Device.id.asc()).first()
    if device is None and ip_address:
        device = db.query(Device).filter(Device.vendor == vendor, Device.ip_address == ip_address).order_by(Device.id.asc()).first()
    if device is None:
        device = db.query(Device).filter(Device.vendor == vendor, Device.hostname_normalized == hostname_normalized).order_by(Device.id.asc()).first()

    if device:
        previous_hostname = device.hostname
        device.hostname = hostname
        device.hostname_normalized = hostname_normalized
        device.identity_key = build_identity_key(vendor=vendor, hostname=hostname, management_ip=device.ip_address or ip_address, explicit_device_id=device.id)
        if ip_address:
            device.ip_address = ip_address
        if site:
            device.site = site
        if role:
            device.role = role
        if environment:
            device.environment = environment
        if collection_method:
            device.collection_method = collection_method
        if metadata is not None:
            device.metadata_json = json.dumps(metadata, ensure_ascii=False)
        device.updated_at = now
        device.last_seen_at = now
        _append_alias(device, previous_hostname)
        return device

    device = Device(
        vendor=vendor,
        hostname=hostname,
        hostname_normalized=hostname_normalized,
        identity_key=identity_key,
        aliases_json='[]',
        ip_address=ip_address,
        site=site,
        role=role,
        environment=environment,
        collection_method=collection_method,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(device)
    db.flush()
    device.identity_key = build_identity_key(vendor=vendor, hostname=hostname, management_ip=device.ip_address, explicit_device_id=device.id)
    return device
