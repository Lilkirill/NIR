from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ai_analysis_endpoint_returns_llm_risk():
    config_text = Path('configs/samples/cisco_ok.cfg').read_text(encoding='utf-8')
    response = client.post(
        '/api/v1/ai/analyze',
        json={
            'vendor': 'cisco',
            'hostname': 'branch-ai-1',
            'config_text': config_text,
            'profile': 'branch-router',
            'metadata': {'source': 'pytest-ai'},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['ai_analysis']
    assert payload['ai_analysis']['model_name'] == 'ConfigGuard-Qwen2.5-3B-Instruct-Advisor'
    assert 0 <= payload['ai_analysis']['risk_score'] <= 1
    assert payload['ai_analysis']['risk_level'] in {'minimal', 'low', 'medium', 'high', 'critical'}
    assert isinstance(payload['ai_analysis']['recommendations'], list)


def test_validate_include_ai_flag():
    config_text = 'hostname no-ssh\ninterface GigabitEthernet0/0\n no shutdown\n'
    response = client.post(
        '/api/v1/validate',
        json={'vendor': 'cisco', 'hostname': 'no-ssh', 'config_text': config_text, 'include_ai': True},
    )
    assert response.status_code == 200
    analysis = response.json()['ai_analysis']
    assert analysis['predicted_failure_kind'] in {
        'failed_security_policy',
        'failed_routing_policy',
        'failed_incomplete_configuration',
        'failed_policy',
        'needs_review',
    }
    assert analysis['key_factors']
