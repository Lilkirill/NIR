from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_validation_persists_raw_config_and_writes_log():
    config_text = Path('configs/samples/cisco_ok.cfg').read_text(encoding='utf-8')
    response = client.post(
        '/api/v1/validate',
        json={
            'vendor': 'cisco',
            'hostname': 'branch-r1',
            'config_text': config_text,
            'metadata': {'source': 'pytest-audit'},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    raw_config_path = Path(payload['raw_config_path'])
    assert raw_config_path.exists()
    assert raw_config_path.read_text(encoding='utf-8') == config_text

    log_path = Path('logs/validation.log')
    assert log_path.exists()
    log_text = log_path.read_text(encoding='utf-8')
    assert 'validation vendor=cisco hostname=branch-r1 status=' in log_text
    assert str(raw_config_path) in log_text
