from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_collect_and_metrics_endpoints(tmp_path: Path):
    sample_text = Path('configs/samples/cisco_ok.cfg').read_text(encoding='utf-8')
    sample_file = tmp_path / 'cisco_ok.cfg'
    sample_file.write_text(sample_text, encoding='utf-8')

    collect_response = client.post(
        '/api/v1/collect',
        json={
            'source_type': 'file',
            'vendor': 'cisco',
            'hostname': 'branch-r1-file',
            'file_path': str(sample_file),
            'metadata': {'source': 'pytest-collect'},
        },
    )
    assert collect_response.status_code == 200
    collect_payload = collect_response.json()
    assert collect_payload['source_type'] == 'file'
    assert Path(collect_payload['raw_config_path']).exists()

    validate_response = client.post(
        '/api/v1/collect-and-validate',
        json={
            'source_type': 'file',
            'vendor': 'cisco',
            'hostname': 'branch-r1-file',
            'file_path': str(sample_file),
            'metadata': {'source': 'pytest-collect-validate'},
        },
    )
    assert validate_response.status_code == 200
    validate_payload = validate_response.json()
    assert validate_payload['vendor'] == 'cisco'
    assert validate_payload['status'] in {'passed', 'failed'}

    metrics_response = client.get('/api/v1/metrics/summary')
    assert metrics_response.status_code == 200
    metrics_payload = metrics_response.json()
    assert metrics_payload['total_runs'] >= 1
    assert any(item['vendor'] == 'cisco' for item in metrics_payload['by_vendor'])

    devices_response = client.get('/api/v1/devices')
    assert devices_response.status_code == 200
    assert any(item['hostname'] == 'branch-r1-file' for item in devices_response.json())

    runs_response = client.get('/api/v1/runs')
    assert runs_response.status_code == 200
    assert len(runs_response.json()) >= 1
