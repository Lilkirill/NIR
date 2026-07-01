from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_bulk_validation_and_prometheus_metrics():
    config_text = Path('configs/samples/cisco_ok.cfg').read_text(encoding='utf-8')
    response = client.post(
        '/api/v1/validate/bulk',
        json={
            'items': [
                {'vendor': 'cisco', 'hostname': 'branch-r1-a', 'config_text': config_text, 'profile': 'branch-router'},
                {'vendor': 'cisco', 'hostname': 'branch-r1-b', 'config_text': config_text, 'profile': 'branch-router'},
            ]
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['total'] == 2
    assert payload['passed'] + payload['failed'] == 2

    metrics = client.get('/api/v1/metrics')
    assert metrics.status_code == 200
    assert 'ncv_total_runs' in metrics.text


def test_redaction_and_device_inventory():
    config_text = Path('configs/samples/cisco_ok.cfg').read_text(encoding='utf-8').replace('hostname branch-r1', 'hostname branch-secure-1') + '\nusername admin privilege 15 secret 5 supersecret\n'
    response = client.post(
        '/api/v1/validate',
        json={
            'vendor': 'cisco',
            'hostname': 'branch-secure-1',
            'config_text': config_text,
            'redact_secrets': True,
            'device_ip': '10.0.0.10',
            'site': 'ams-1',
            'role': 'branch-router',
            'environment': 'lab',
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['redacted_config_path']
    redacted_text = Path(payload['redacted_config_path']).read_text(encoding='utf-8')
    assert 'supersecret' not in redacted_text
    assert '<redacted>' in redacted_text

    devices = client.get('/api/v1/devices').json()
    row = next(item for item in devices if item['hostname'] == 'branch-secure-1')
    assert row['ip_address'] == '10.0.0.10'
    assert row['site'] == 'ams-1'
    assert row['role'] == 'branch-router'


def test_diff_endpoint_and_topology_validation():
    good_config = Path('configs/samples/cisco_ok.cfg').read_text(encoding='utf-8').replace('hostname branch-r1', 'hostname branch-diff-1')
    bad_config = good_config.replace('ip route 0.0.0.0 0.0.0.0 10.0.0.2\n', '')

    first = client.post('/api/v1/validate', json={'vendor': 'cisco', 'hostname': 'branch-diff-1', 'config_text': good_config})
    second = client.post('/api/v1/validate', json={'vendor': 'cisco', 'hostname': 'branch-diff-1', 'config_text': bad_config})
    assert first.status_code == 200 and second.status_code == 200

    devices = client.get('/api/v1/devices').json()
    device_id = next(item['id'] for item in devices if item['hostname'] == 'branch-diff-1')
    diff = client.get(f'/api/v1/devices/{device_id}/diff')
    assert diff.status_code == 200
    diff_payload = diff.json()
    assert 'changes' in diff_payload
    assert 'routes_removed' in diff_payload['changes']

    topology = client.post(
        '/api/v1/validate/topology',
        json={
            'items': [
                {'vendor': 'cisco', 'hostname': 'dup-1', 'config_text': good_config},
                {'vendor': 'cisco', 'hostname': 'dup-2', 'config_text': good_config.replace('hostname branch-diff-1', 'hostname dup-2')},
            ]
        },
    )
    assert topology.status_code == 200
    topology_payload = topology.json()
    assert topology_payload['findings']
    assert any(item['code'] == 'DUPLICATE_IP_ADDRESS' for item in topology_payload['findings'])
