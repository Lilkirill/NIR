from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_validate_endpoint_returns_passed_or_failed():
    config_text = Path('configs/samples/cisco_ok.cfg').read_text(encoding='utf-8')
    response = client.post('/api/v1/validate', json={'vendor': 'cisco', 'hostname': 'branch-r1', 'config_text': config_text, 'metadata': {'source': 'pytest'}})
    assert response.status_code == 200
    payload = response.json()
    assert payload['vendor'] == 'cisco'
    assert payload['status'] in {'passed', 'failed'}
    assert 'report_json_path' in payload
    assert 'metrics' in payload
