from app.validators.rule_engine import RuleEngine

def test_rule_engine_flags_missing_default_route():
    config = {
        'vendor': 'cisco',
        'hostname': 'r1',
        'interfaces': [{'name': 'Gi0/0', 'description': '', 'enabled': True, 'addresses': ['10.0.0.1/24']}],
        'routes': [],
        'services': {'ssh_enabled': True, 'password_encryption': True},
        'users': [{'username': 'admin'}],
    }
    findings = RuleEngine().evaluate(config)
    codes = {item['code'] for item in findings}
    assert 'DEFAULT_ROUTE_REQUIRED' in codes


def test_rule_engine_flags_missing_arista_ssh():
    config = {
        'vendor': 'arista',
        'hostname': 'leaf1',
        'interfaces': [{'name': 'Ethernet1', 'description': '', 'enabled': True, 'addresses': ['10.0.0.1/31']}],
        'routes': [{'destination': '0.0.0.0/0', 'next_hop': '10.0.0.0'}],
        'services': {'ssh_enabled': False, 'password_encryption': True},
        'users': [{'username': 'admin'}],
    }
    findings = RuleEngine(vendor='arista').evaluate(config)
    codes = {item['code'] for item in findings}
    assert 'ARISTA_SSH_REQUIRED' in codes


def test_rule_engine_flags_missing_huawei_ssh():
    config = {
        'vendor': 'huawei',
        'hostname': 'hw1',
        'interfaces': [{'name': 'GigabitEthernet0/0/0', 'description': '', 'enabled': True, 'addresses': ['10.0.0.1/30']}],
        'routes': [{'destination': '0.0.0.0/0', 'next_hop': '10.0.0.2'}],
        'services': {'ssh_enabled': False, 'password_encryption': True},
        'users': [{'username': 'admin'}],
    }
    findings = RuleEngine(vendor='huawei').evaluate(config)
    codes = {item['code'] for item in findings}
    assert 'HUAWEI_SSH_REQUIRED' in codes
