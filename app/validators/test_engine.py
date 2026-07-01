class TestEngine:
    def run(self, config: dict) -> list[dict]:
        tests = []
        tests.append({'name': 'hostname_present', 'status': 'passed' if config.get('hostname') else 'failed', 'details': 'Hostname must be present.'})
        interfaces = config.get('interfaces', [])
        tests.append({'name': 'at_least_one_interface', 'status': 'passed' if interfaces else 'failed', 'details': 'At least one interface required.'})
        addressed = sum(1 for iface in interfaces if iface.get('addresses'))
        tests.append({'name': 'addressed_interfaces_ratio', 'status': 'passed' if interfaces and addressed / len(interfaces) >= 0.5 else 'failed', 'details': f'Addressed interfaces: {addressed}/{len(interfaces) if interfaces else 0}'})
        routes = config.get('routes', [])
        tests.append({'name': 'route_consistency', 'status': 'passed' if all(r.get('next_hop') for r in routes) else 'failed', 'details': 'Each route must have next-hop.'})
        return tests
