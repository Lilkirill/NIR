from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.models import ConfigSnapshot, Device, NormalizedConfig


class DiffService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def diff_latest(self, device_id: int) -> dict[str, Any]:
        device = self.db.query(Device).filter(Device.id == device_id).one_or_none()
        if not device:
            raise ValueError(f'Device {device_id} not found')
        snapshots = (
            self.db.query(ConfigSnapshot)
            .filter(ConfigSnapshot.device_id == device_id)
            .order_by(ConfigSnapshot.id.desc())
            .limit(2)
            .all()
        )
        if len(snapshots) < 2:
            raise ValueError('At least two snapshots are required for diff analysis.')
        newer, older = snapshots[0], snapshots[1]
        return self.diff_between(device_id=device_id, from_snapshot_id=older.id, to_snapshot_id=newer.id)

    def diff_between(self, device_id: int, from_snapshot_id: int, to_snapshot_id: int) -> dict[str, Any]:
        device = self.db.query(Device).filter(Device.id == device_id).one_or_none()
        if not device:
            raise ValueError(f'Device {device_id} not found')
        old_cfg = self._load_normalized(from_snapshot_id)
        new_cfg = self._load_normalized(to_snapshot_id)
        return {
            'device_id': device.id,
            'hostname': device.hostname,
            'vendor': device.vendor,
            'from_snapshot_id': from_snapshot_id,
            'to_snapshot_id': to_snapshot_id,
            'changes': {
                'interfaces_added': sorted(set(self._iface_names(new_cfg)) - set(self._iface_names(old_cfg))),
                'interfaces_removed': sorted(set(self._iface_names(old_cfg)) - set(self._iface_names(new_cfg))),
                'routes_added': sorted(set(self._route_dests(new_cfg)) - set(self._route_dests(old_cfg))),
                'routes_removed': sorted(set(self._route_dests(old_cfg)) - set(self._route_dests(new_cfg))),
                'services_changed': self._services_changed(old_cfg, new_cfg),
                'users_added': sorted(set(self._users(new_cfg)) - set(self._users(old_cfg))),
                'users_removed': sorted(set(self._users(old_cfg)) - set(self._users(new_cfg))),
            },
        }

    def _load_normalized(self, snapshot_id: int) -> dict[str, Any]:
        row = self.db.query(NormalizedConfig).filter(NormalizedConfig.config_snapshot_id == snapshot_id).order_by(NormalizedConfig.id.desc()).first()
        if not row:
            raise ValueError(f'Normalized config for snapshot {snapshot_id} not found')
        return json.loads(row.normalized_json)

    @staticmethod
    def _iface_names(cfg: dict[str, Any]) -> list[str]:
        return [item.get('name', '') for item in cfg.get('interfaces', []) if item.get('name')]

    @staticmethod
    def _route_dests(cfg: dict[str, Any]) -> list[str]:
        return [item.get('destination', '') for item in cfg.get('routes', []) if item.get('destination')]

    @staticmethod
    def _users(cfg: dict[str, Any]) -> list[str]:
        return [item.get('username', '') for item in cfg.get('users', []) if item.get('username')]

    @staticmethod
    def _services_changed(old_cfg: dict[str, Any], new_cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
        old = old_cfg.get('services', {})
        new = new_cfg.get('services', {})
        changed: dict[str, dict[str, Any]] = {}
        for key in sorted(set(old) | set(new)):
            if old.get(key) != new.get(key):
                changed[key] = {'from': old.get(key), 'to': new.get(key)}
        return changed
