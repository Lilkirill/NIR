from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import BASE_DIR, settings


class ReportBuilder:
    def __init__(self) -> None:
        self.env = Environment(
            loader=FileSystemLoader(BASE_DIR / 'templates'),
            autoescape=select_autoescape(['html'])
        )

    def build(self, payload: dict) -> tuple[str, str]:
        ts = datetime.now(UTC).strftime('%Y%m%d_%H%M%S_%f')
        safe_vendor = payload['vendor']
        safe_hostname = payload['hostname']
        json_path = settings.reports_path / f"{safe_vendor}_{safe_hostname}_{ts}.json"
        html_path = settings.reports_path / f"{safe_vendor}_{safe_hostname}_{ts}.html"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        template = self.env.get_template('report.html.j2')
        html = template.render(**payload)
        html_path.write_text(html, encoding='utf-8')
        return str(json_path), str(html_path)
