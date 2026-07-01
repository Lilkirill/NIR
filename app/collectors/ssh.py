from __future__ import annotations

from typing import Any

from app.collectors.base import BaseCollector, CollectedConfig

try:
    import paramiko
except Exception:  # pragma: no cover - optional import guard for environments without paramiko
    paramiko = None


_VENDOR_COMMANDS = {
    'cisco': 'terminal length 0\nshow running-config\n',
    'juniper': 'show configuration | no-more\n',
    'mikrotik': '/export terse\n',
    'arista': 'show running-config\n',
    'huawei': 'display current-configuration | no-more\n',
}


class SSHCollector(BaseCollector):
    source_type = 'ssh'

    def collect(self, **kwargs: Any) -> CollectedConfig:
        if paramiko is None:
            raise RuntimeError('paramiko is required for SSH collection but is not installed.')

        vendor = kwargs.get('vendor')
        host = kwargs.get('host')
        port = int(kwargs.get('port', 22))
        username = kwargs.get('username')
        if not vendor:
            raise ValueError('vendor is required for SSH collection.')
        if not host:
            raise ValueError('host is required for SSH collection.')
        if not username:
            raise ValueError('username is required for SSH collection.')
        password = kwargs.get('password')
        hostname = kwargs.get('hostname') or host
        command = kwargs.get('command_override') or _VENDOR_COMMANDS.get(vendor.lower())
        if not command:
            raise ValueError(f'No default SSH collection command for vendor: {vendor}')

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(hostname=host, port=port, username=username, password=password, look_for_keys=False, allow_agent=False, timeout=15)
            shell = client.invoke_shell()
            shell.send(command)
            shell.send('exit\n')
            chunks: list[str] = []
            while True:
                data = shell.recv(65535)
                if not data:
                    break
                chunks.append(data.decode('utf-8', errors='ignore'))
                if shell.exit_status_ready():
                    break
            text = ''.join(chunks)
        finally:
            client.close()

        metadata = dict(kwargs.get('metadata') or {})
        metadata.setdefault('collector', self.source_type)
        metadata.setdefault('host', host)
        metadata.setdefault('port', port)
        return CollectedConfig(
            vendor=vendor,
            hostname=hostname,
            config_text=text,
            source_type=self.source_type,
            source_ref=f'ssh://{username}@{host}:{port}',
            metadata=metadata,
        )
