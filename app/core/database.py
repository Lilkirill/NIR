from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def _datetime_ddl() -> str:
    return 'TIMESTAMP' if engine.dialect.name == 'postgresql' else 'DATETIME'


def _bool_default(value: bool) -> str:
    if engine.dialect.name == 'postgresql':
        return 'TRUE' if value else 'FALSE'
    return '1' if value else '0'


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    # devices
    _ensure_column('devices', 'hostname_normalized', "VARCHAR(255) NOT NULL DEFAULT ''")
    _ensure_column('devices', 'identity_key', "VARCHAR(255) NOT NULL DEFAULT ''")
    _ensure_column('devices', 'aliases_json', "TEXT NOT NULL DEFAULT '[]'")
    _ensure_column('devices', 'ip_address', 'VARCHAR(128) NULL')
    _ensure_column('devices', 'site', 'VARCHAR(128) NULL')
    _ensure_column('devices', 'role', 'VARCHAR(128) NULL')
    _ensure_column('devices', 'environment', 'VARCHAR(64) NULL')
    _ensure_column('devices', 'collection_method', 'VARCHAR(32) NULL')
    _ensure_column('devices', 'metadata_json', "TEXT NOT NULL DEFAULT '{}' ")
    _ensure_column('devices', 'updated_at', f'{_datetime_ddl()} NULL')
    _ensure_column('devices', 'is_active', f'BOOLEAN NOT NULL DEFAULT {_bool_default(True)}')
    # snapshots
    _ensure_column('config_snapshots', 'redacted_config_path', 'VARCHAR(1024) NULL')
    _ensure_column('config_snapshots', 'profile', 'VARCHAR(64) NULL')
    _ensure_column('config_snapshots', 'source_scope', "VARCHAR(64) NOT NULL DEFAULT 'unknown'")
    _ensure_column('config_snapshots', 'dataset_name', 'VARCHAR(255) NULL')
    _ensure_column('config_snapshots', 'is_test_data', f'BOOLEAN NOT NULL DEFAULT {_bool_default(False)}')
    _ensure_column('config_snapshots', 'metadata_json', "TEXT NOT NULL DEFAULT '{}' ")
    # normalized
    _ensure_column('normalized_configs', 'normalized_hash', 'VARCHAR(64) NULL')
    _ensure_column('normalized_configs', 'schema_version', "VARCHAR(32) NOT NULL DEFAULT '1.0'")
    _ensure_column('normalized_configs', 'vendor_extensions_json', "TEXT NOT NULL DEFAULT '{}' ")
    _ensure_column('normalized_configs', 'parsed_successfully', f'BOOLEAN NOT NULL DEFAULT {_bool_default(True)}')
    _ensure_column('normalized_configs', 'parse_error', 'TEXT NULL')
    # runs
    _ensure_column('validation_runs', 'raw_config_path', "VARCHAR(1024) NOT NULL DEFAULT ''")
    _ensure_column('validation_runs', 'redacted_config_path', 'VARCHAR(1024) NULL')
    _ensure_column('validation_runs', 'metrics_json', "TEXT NOT NULL DEFAULT '{}' ")
    _ensure_column('validation_runs', 'metadata_json', "TEXT NOT NULL DEFAULT '{}' ")
    _ensure_column('validation_runs', 'config_snapshot_id', 'INTEGER NULL')
    _ensure_column('validation_runs', 'normalized_config_id', 'INTEGER NULL')
    _ensure_column('validation_runs', 'profile', 'VARCHAR(64) NULL')
    _ensure_column('validation_runs', 'source_type', 'VARCHAR(32) NULL')
    _ensure_column('validation_runs', 'device_id', 'INTEGER NULL')
    _ensure_column('validation_runs', 'run_kind', "VARCHAR(32) NOT NULL DEFAULT 'api'")
    _ensure_column('validation_runs', 'source_scope', "VARCHAR(64) NOT NULL DEFAULT 'unknown'")
    _ensure_column('validation_runs', 'expected_outcome', "VARCHAR(32) NOT NULL DEFAULT 'unknown'")
    _ensure_column('validation_runs', 'failure_kind', 'VARCHAR(64) NULL')
    _ensure_column('validation_runs', 'profile_match_status', "VARCHAR(32) NOT NULL DEFAULT 'matched'")
    _ensure_column('validation_runs', 'profile_match_score', 'FLOAT NULL')
    _ensure_column('validation_runs', 'dataset_name', 'VARCHAR(255) NULL')
    _ensure_column('validation_runs', 'is_test_data', f'BOOLEAN NOT NULL DEFAULT {_bool_default(False)}')
    # findings
    _ensure_column('validation_findings', 'category', 'VARCHAR(64) NULL')
    _ensure_column('validation_findings', 'recommendation', 'TEXT NULL')
    _ensure_column('validation_findings', 'remediation_example', 'TEXT NULL')
    _ensure_column('validation_findings', 'rule_source', 'VARCHAR(64) NULL')
    _ensure_column('validation_findings', 'rule_version', 'VARCHAR(32) NULL')
    _ensure_column('validation_findings', 'confidence', 'FLOAT NULL')
    # metrics snapshots
    _ensure_column('metrics_snapshots', 'run_kind', "VARCHAR(32) NOT NULL DEFAULT 'api'")
    _ensure_column('metrics_snapshots', 'source_scope', "VARCHAR(64) NOT NULL DEFAULT 'unknown'")
    _ensure_column('metrics_snapshots', 'failure_kind', 'VARCHAR(64) NULL')
    # create new tables if missing
    Base.metadata.create_all(bind=engine)
    _backfill_hostname_normalized()
    _backfill_identity_columns()
    _backfill_updated_at()


def _backfill_hostname_normalized() -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE devices SET hostname_normalized = lower(hostname) WHERE hostname_normalized IS NULL OR hostname_normalized = ''"))


def _backfill_identity_columns() -> None:
    if engine.dialect.name == 'postgresql':
        sql = """
        UPDATE devices
        SET identity_key = CASE
            WHEN COALESCE(ip_address, '') <> '' THEN lower(vendor) || '::ip::' || ip_address
            ELSE lower(vendor) || '::host::' || lower(hostname)
        END,
        aliases_json = COALESCE(NULLIF(aliases_json, ''), '[]')
        WHERE COALESCE(identity_key, '') = '' OR COALESCE(aliases_json, '') = ''
        """
    else:
        sql = """
        UPDATE devices
        SET identity_key = CASE
            WHEN COALESCE(ip_address, '') <> '' THEN lower(vendor) || '::ip::' || ip_address
            ELSE lower(vendor) || '::host::' || lower(hostname)
        END,
        aliases_json = CASE WHEN aliases_json IS NULL OR aliases_json = '' THEN '[]' ELSE aliases_json END
        WHERE COALESCE(identity_key, '') = '' OR aliases_json IS NULL OR aliases_json = ''
        """
    with engine.begin() as conn:
        conn.execute(text(sql))


def _backfill_updated_at() -> None:
    with engine.begin() as conn:
        conn.execute(text(f'UPDATE devices SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)'))


def _ensure_column(table_name: str, column_name: str, ddl: str) -> None:
    inspector = inspect(engine)
    try:
        columns = {col['name'] for col in inspector.get_columns(table_name)}
    except Exception:
        columns = set()
    if column_name in columns:
        return
    with engine.begin() as conn:
        conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}'))


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
