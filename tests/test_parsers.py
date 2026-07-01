from pathlib import Path

from app.parsers.arista import AristaParser
from app.parsers.cisco import CiscoParser
from app.parsers.huawei import HuaweiParser
from app.parsers.juniper import JuniperParser
from app.parsers.mikrotik import MikroTikParser


def test_cisco_parser_extracts_hostname_and_routes():
    text = Path('configs/samples/cisco_ok.cfg').read_text(encoding='utf-8')
    parsed = CiscoParser().parse('ignored', text)
    assert parsed['hostname'] == 'branch-r1'
    assert parsed['routes'][0]['destination'] == '0.0.0.0/0'
    assert parsed['services']['ssh_enabled'] is True


def test_juniper_parser_extracts_hostname():
    text = Path('configs/samples/juniper_ok.conf').read_text(encoding='utf-8')
    parsed = JuniperParser().parse('ignored', text)
    assert parsed['hostname'] == 'dc-edge-1'
    assert parsed['vendor'] == 'juniper'


def test_mikrotik_parser_extracts_identity():
    text = Path('configs/samples/mikrotik_ok.rsc').read_text(encoding='utf-8')
    parsed = MikroTikParser().parse('ignored', text)
    assert parsed['hostname'] == 'mt-core-1'
    assert len(parsed['interfaces']) == 2


def test_arista_parser_extracts_eos_config():
    text = Path('configs/samples/arista_ok.cfg').read_text(encoding='utf-8')
    parsed = AristaParser().parse('ignored', text)
    assert parsed['vendor'] == 'arista'
    assert parsed['hostname'] == 'leaf-eos-1'
    assert parsed['services']['ssh_enabled'] is True
    assert parsed['routes'][0]['destination'] == '0.0.0.0/0'
    assert len(parsed['interfaces']) == 2


def test_huawei_parser_extracts_vrp_config():
    text = Path('configs/samples/huawei_ok.cfg').read_text(encoding='utf-8')
    parsed = HuaweiParser().parse('ignored', text)
    assert parsed['vendor'] == 'huawei'
    assert parsed['hostname'] == 'hw-edge-1'
    assert parsed['services']['ssh_enabled'] is True
    assert parsed['routes'][0]['destination'] == '0.0.0.0/0'
    assert len(parsed['interfaces']) == 2
