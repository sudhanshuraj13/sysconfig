"""Typed models for the SysConfig environment."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class User:
    name: str
    groups: list[str] = field(default_factory=list)
    shell: str = "/bin/bash"
    has_login: bool = True
    password_policy: str = "default"


@dataclass
class FirewallRule:
    port: int
    protocol: str = "tcp"
    action: str = "allow"
    source: str = "any"


@dataclass
class Service:
    name: str
    enabled: bool = False
    running: bool = False


@dataclass
class CronJob:
    user: str
    schedule: str
    command: str


@dataclass
class FilePermission:
    path: str
    owner: str = "root"
    group: str = "root"
    mode: str = "0755"


@dataclass
class SSHConfig:
    permit_root_login: str = "yes"
    password_authentication: str = "yes"
    port: int = 22
    max_auth_tries: int = 6
    pubkey_authentication: str = "yes"


@dataclass
class LoggingConfig:
    auth_log: bool = True
    syslog: bool = True
    access_log: bool = False
    error_log: bool = False
    audit_log: bool = False


@dataclass
class ServerState:
    users: list[User] = field(default_factory=list)
    firewall_rules: list[FirewallRule] = field(default_factory=list)
    services: list[Service] = field(default_factory=list)
    cron_jobs: list[CronJob] = field(default_factory=list)
    file_permissions: list[FilePermission] = field(default_factory=list)
    ssh_config: SSHConfig = field(default_factory=SSHConfig)
    environment_variables: dict[str, str] = field(default_factory=dict)
    sysctl_params: dict[str, str] = field(default_factory=dict)
    installed_packages: list[str] = field(default_factory=list)
    logging_config: LoggingConfig = field(default_factory=LoggingConfig)

    def to_dict(self) -> dict[str, Any]:
        return {
            "users": [
                {
                    "name": u.name,
                    "groups": u.groups,
                    "shell": u.shell,
                    "has_login": u.has_login,
                    "password_policy": u.password_policy,
                }
                for u in self.users
            ],
            "firewall_rules": [
                {
                    "port": r.port,
                    "protocol": r.protocol,
                    "action": r.action,
                    "source": r.source,
                }
                for r in self.firewall_rules
            ],
            "services": [
                {"name": s.name, "enabled": s.enabled, "running": s.running}
                for s in self.services
            ],
            "cron_jobs": [
                {"user": c.user, "schedule": c.schedule, "command": c.command}
                for c in self.cron_jobs
            ],
            "file_permissions": [
                {
                    "path": f.path,
                    "owner": f.owner,
                    "group": f.group,
                    "mode": f.mode,
                }
                for f in self.file_permissions
            ],
            "ssh_config": {
                "permit_root_login": self.ssh_config.permit_root_login,
                "password_authentication": self.ssh_config.password_authentication,
                "port": self.ssh_config.port,
                "max_auth_tries": self.ssh_config.max_auth_tries,
                "pubkey_authentication": self.ssh_config.pubkey_authentication,
            },
            "environment_variables": dict(self.environment_variables),
            "sysctl_params": dict(self.sysctl_params),
            "installed_packages": list(self.installed_packages),
            "logging_config": {
                "auth_log": self.logging_config.auth_log,
                "syslog": self.logging_config.syslog,
                "access_log": self.logging_config.access_log,
                "error_log": self.logging_config.error_log,
                "audit_log": self.logging_config.audit_log,
            },
        }
