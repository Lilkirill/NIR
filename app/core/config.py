from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = 'network-config-validator'
    app_env: str = 'dev'
    app_host: str = '0.0.0.0'
    app_port: int = 8000
    app_dashboard_title: str = 'Network Configuration Validator'
    database_url: str = f"sqlite:///{(BASE_DIR / 'validator.db').as_posix()}"
    reports_dir: str = str(BASE_DIR / 'reports_output')
    logs_dir: str = str(BASE_DIR / 'logs')
    archived_configs_dir: str = str(BASE_DIR / 'saved_configs')
    temp_export_dir: str = str(BASE_DIR / 'exports')
    grafana_admin_user: str = 'admin'
    grafana_admin_password: str = 'admin'
    grafana_port: int = 3000
    prometheus_metrics_enabled: bool = True
    job_store_max_items: int = 200
    model_config = SettingsConfigDict(env_file=BASE_DIR / '.env', env_file_encoding='utf-8', extra='ignore')

    @property
    def reports_path(self) -> Path:
        path = Path(self.reports_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def logs_path(self) -> Path:
        path = Path(self.logs_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def archived_configs_path(self) -> Path:
        path = Path(self.archived_configs_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def export_path(self) -> Path:
        path = Path(self.temp_export_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()

if ('@db:' in settings.database_url or settings.database_url.startswith('postgresql')) and os.getenv('NCV_FORCE_POSTGRES', '0') != '1':
    settings.database_url = f"sqlite:///{(BASE_DIR / 'validator.db').as_posix()}"
