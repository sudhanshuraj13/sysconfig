"""Task definitions for SysConfig environment."""

from __future__ import annotations

from models import (
    CronJob,
    FilePermission,
    FirewallRule,
    LoggingConfig,
    ServerState,
    Service,
    SSHConfig,
    User,
)


def get_task(task_id: str) -> dict:
    """Return initial state, target state, and task description."""
    tasks = {
        "basic_webserver": _basic_webserver,
        "multi_service": _multi_service,
        "security_hardening": _security_hardening,
    }
    if task_id not in tasks:
        raise ValueError(f"Unknown task: {task_id}. Available: {list(tasks.keys())}")
    return tasks[task_id]()


def _basic_webserver() -> dict:
    """Easy: Set up a basic web server."""
    initial = ServerState(
        users=[User(name="root", groups=["root"], shell="/bin/bash")],
        firewall_rules=[],
        services=[
            Service(name="nginx", enabled=False, running=False),
            Service(name="ssh", enabled=True, running=True),
        ],
        file_permissions=[
            FilePermission(path="/var/www/html", owner="root", group="root", mode="0755"),
        ],
        installed_packages=["nginx", "openssh-server"],
        ssh_config=SSHConfig(),
        logging_config=LoggingConfig(),
    )

    target = ServerState(
        users=[
            User(name="root", groups=["root"], shell="/bin/bash"),
            User(name="www-data", groups=["www-data"], shell="/usr/sbin/nologin", has_login=False),
        ],
        firewall_rules=[
            FirewallRule(port=80, protocol="tcp", action="allow", source="any"),
            FirewallRule(port=443, protocol="tcp", action="allow", source="any"),
            FirewallRule(port=22, protocol="tcp", action="allow", source="any"),
        ],
        services=[
            Service(name="nginx", enabled=True, running=True),
            Service(name="ssh", enabled=True, running=True),
        ],
        file_permissions=[
            FilePermission(path="/var/www/html", owner="www-data", group="www-data", mode="0755"),
        ],
        installed_packages=["nginx", "openssh-server"],
        ssh_config=SSHConfig(),
        logging_config=LoggingConfig(access_log=True, error_log=True),
    )

    return {
        "task_id": "basic_webserver",
        "name": "Basic Web Server Setup",
        "difficulty": "easy",
        "description": (
            "Set up a basic web server on this machine. You need to:\n"
            "1. Create a 'www-data' user (no login shell) for nginx\n"
            "2. Open firewall ports 80 (HTTP) and 443 (HTTPS), keep SSH (22) open\n"
            "3. Enable and start the nginx service\n"
            "4. Set /var/www/html ownership to www-data:www-data\n"
            "5. Enable access and error logging"
        ),
        "initial_state": initial,
        "target_state": target,
        "max_steps": 15,
    }


def _multi_service() -> dict:
    """Medium: Configure a multi-service application stack."""
    initial = ServerState(
        users=[
            User(name="root", groups=["root"], shell="/bin/bash"),
        ],
        firewall_rules=[
            FirewallRule(port=22, protocol="tcp", action="allow", source="any"),
        ],
        services=[
            Service(name="nginx", enabled=False, running=False),
            Service(name="postgresql", enabled=False, running=False),
            Service(name="redis", enabled=False, running=False),
            Service(name="ssh", enabled=True, running=True),
        ],
        file_permissions=[
            FilePermission(path="/var/www/app", owner="root", group="root", mode="0755"),
            FilePermission(path="/var/lib/postgresql", owner="root", group="root", mode="0755"),
            FilePermission(path="/var/lib/redis", owner="root", group="root", mode="0755"),
            FilePermission(path="/etc/app/config", owner="root", group="root", mode="0755"),
        ],
        installed_packages=["nginx", "postgresql", "redis-server", "openssh-server"],
        ssh_config=SSHConfig(),
        logging_config=LoggingConfig(),
    )

    target = ServerState(
        users=[
            User(name="root", groups=["root"], shell="/bin/bash"),
            User(name="www-data", groups=["www-data"], shell="/usr/sbin/nologin", has_login=False),
            User(name="postgres", groups=["postgres"], shell="/usr/sbin/nologin", has_login=False),
            User(name="redis", groups=["redis"], shell="/usr/sbin/nologin", has_login=False),
            User(name="appuser", groups=["www-data", "appgroup"], shell="/bin/bash"),
        ],
        firewall_rules=[
            FirewallRule(port=22, protocol="tcp", action="allow", source="any"),
            FirewallRule(port=80, protocol="tcp", action="allow", source="any"),
            FirewallRule(port=443, protocol="tcp", action="allow", source="any"),
            FirewallRule(port=5432, protocol="tcp", action="allow", source="127.0.0.1"),
            FirewallRule(port=6379, protocol="tcp", action="allow", source="127.0.0.1"),
        ],
        services=[
            Service(name="nginx", enabled=True, running=True),
            Service(name="postgresql", enabled=True, running=True),
            Service(name="redis", enabled=True, running=True),
            Service(name="ssh", enabled=True, running=True),
        ],
        file_permissions=[
            FilePermission(path="/var/www/app", owner="appuser", group="www-data", mode="0750"),
            FilePermission(path="/var/lib/postgresql", owner="postgres", group="postgres", mode="0700"),
            FilePermission(path="/var/lib/redis", owner="redis", group="redis", mode="0700"),
            FilePermission(path="/etc/app/config", owner="appuser", group="appgroup", mode="0640"),
        ],
        environment_variables={
            "DATABASE_URL": "postgresql://appuser:password@localhost:5432/appdb",
            "REDIS_URL": "redis://localhost:6379/0",
            "APP_ENV": "production",
            "APP_SECRET_KEY": "generated-secret-key",
        },
        installed_packages=["nginx", "postgresql", "redis-server", "openssh-server"],
        ssh_config=SSHConfig(),
        logging_config=LoggingConfig(access_log=True, error_log=True),
    )

    return {
        "task_id": "multi_service",
        "name": "Multi-Service Configuration",
        "difficulty": "medium",
        "description": (
            "Configure a web application stack with nginx, PostgreSQL, and Redis.\n"
            "You need to:\n"
            "1. Create service users: www-data, postgres, redis (all no-login)\n"
            "2. Create appuser in www-data and appgroup groups\n"
            "3. Open ports 80/443 to public, 5432/6379 to localhost only\n"
            "4. Enable and start nginx, postgresql, redis services\n"
            "5. Set proper ownership: app dirs to appuser, db to postgres, cache to redis\n"
            "6. Set restrictive permissions (750 for app, 700 for data, 640 for config)\n"
            "7. Set environment variables: DATABASE_URL, REDIS_URL, APP_ENV, APP_SECRET_KEY\n"
            "8. Enable access and error logging"
        ),
        "initial_state": initial,
        "target_state": target,
        "max_steps": 35,
    }


def _security_hardening() -> dict:
    """Hard: Harden a misconfigured production server."""
    initial = ServerState(
        users=[
            User(name="root", groups=["root"], shell="/bin/bash"),
            User(name="admin", groups=["sudo", "root"], shell="/bin/bash"),
            User(name="www-data", groups=["www-data"], shell="/bin/bash", has_login=True),
            User(name="deploy", groups=["sudo", "www-data"], shell="/bin/bash"),
            User(name="tempuser", groups=["sudo"], shell="/bin/bash"),
            User(name="postgres", groups=["postgres"], shell="/bin/bash", has_login=True),
        ],
        firewall_rules=[
            FirewallRule(port=22, protocol="tcp", action="allow", source="any"),
            FirewallRule(port=80, protocol="tcp", action="allow", source="any"),
            FirewallRule(port=443, protocol="tcp", action="allow", source="any"),
            FirewallRule(port=5432, protocol="tcp", action="allow", source="any"),  # DB exposed!
            FirewallRule(port=6379, protocol="tcp", action="allow", source="any"),  # Redis exposed!
            FirewallRule(port=3306, protocol="tcp", action="allow", source="any"),  # MySQL exposed!
            FirewallRule(port=8080, protocol="tcp", action="allow", source="any"),  # Debug port!
            FirewallRule(port=9090, protocol="tcp", action="allow", source="any"),  # Metrics exposed!
        ],
        services=[
            Service(name="nginx", enabled=True, running=True),
            Service(name="postgresql", enabled=True, running=True),
            Service(name="redis", enabled=True, running=True),
            Service(name="ssh", enabled=True, running=True),
            Service(name="telnet", enabled=True, running=True),  # Insecure!
            Service(name="ftp", enabled=True, running=True),  # Insecure!
        ],
        cron_jobs=[
            CronJob(user="root", schedule="0 2 * * *", command="/usr/local/bin/backup.sh"),
            CronJob(user="tempuser", schedule="*/5 * * * *", command="curl http://external-site.com/beacon"),  # Suspicious!
            CronJob(user="root", schedule="0 * * * *", command="chmod 777 /tmp/*"),  # Dangerous!
        ],
        file_permissions=[
            FilePermission(path="/var/www/html", owner="root", group="root", mode="0777"),  # Too open!
            FilePermission(path="/etc/app/secrets", owner="root", group="root", mode="0644"),  # Secrets readable!
            FilePermission(path="/var/log/app", owner="root", group="root", mode="0755"),
            FilePermission(path="/home/deploy/.ssh", owner="deploy", group="deploy", mode="0755"),  # SSH dir too open!
            FilePermission(path="/var/lib/postgresql", owner="postgres", group="postgres", mode="0755"),
        ],
        ssh_config=SSHConfig(
            permit_root_login="yes",  # Insecure!
            password_authentication="yes",  # Should use keys
            port=22,
            max_auth_tries=10,  # Too many
            pubkey_authentication="yes",
        ),
        environment_variables={
            "APP_ENV": "production",
            "DEBUG": "true",  # Debug in production!
            "DATABASE_URL": "postgresql://root:password123@localhost:5432/appdb",  # Root with weak password
        },
        sysctl_params={
            "net.ipv4.ip_forward": "1",  # Should be 0 unless routing
            "net.ipv4.conf.all.accept_redirects": "1",  # Should be 0
            "net.ipv4.conf.all.send_redirects": "1",  # Should be 0
        },
        installed_packages=["nginx", "postgresql", "redis-server", "openssh-server", "telnet", "ftp", "gcc", "make"],
        logging_config=LoggingConfig(
            auth_log=False,  # Auth logging disabled!
            syslog=True,
            access_log=False,  # Access logging disabled!
            error_log=False,  # Error logging disabled!
            audit_log=False,  # Audit logging disabled!
        ),
    )

    target = ServerState(
        users=[
            User(name="root", groups=["root"], shell="/bin/bash"),
            User(name="admin", groups=["sudo"], shell="/bin/bash"),
            User(name="www-data", groups=["www-data"], shell="/usr/sbin/nologin", has_login=False),
            User(name="deploy", groups=["www-data"], shell="/bin/bash"),
            User(name="postgres", groups=["postgres"], shell="/usr/sbin/nologin", has_login=False),
        ],
        firewall_rules=[
            FirewallRule(port=22, protocol="tcp", action="allow", source="any"),
            FirewallRule(port=80, protocol="tcp", action="allow", source="any"),
            FirewallRule(port=443, protocol="tcp", action="allow", source="any"),
            FirewallRule(port=5432, protocol="tcp", action="allow", source="127.0.0.1"),
            FirewallRule(port=6379, protocol="tcp", action="allow", source="127.0.0.1"),
        ],
        services=[
            Service(name="nginx", enabled=True, running=True),
            Service(name="postgresql", enabled=True, running=True),
            Service(name="redis", enabled=True, running=True),
            Service(name="ssh", enabled=True, running=True),
            Service(name="telnet", enabled=False, running=False),
            Service(name="ftp", enabled=False, running=False),
        ],
        cron_jobs=[
            CronJob(user="root", schedule="0 2 * * *", command="/usr/local/bin/backup.sh"),
        ],
        file_permissions=[
            FilePermission(path="/var/www/html", owner="www-data", group="www-data", mode="0755"),
            FilePermission(path="/etc/app/secrets", owner="root", group="root", mode="0600"),
            FilePermission(path="/var/log/app", owner="root", group="root", mode="0750"),
            FilePermission(path="/home/deploy/.ssh", owner="deploy", group="deploy", mode="0700"),
            FilePermission(path="/var/lib/postgresql", owner="postgres", group="postgres", mode="0700"),
        ],
        ssh_config=SSHConfig(
            permit_root_login="no",
            password_authentication="no",
            port=22,
            max_auth_tries=3,
            pubkey_authentication="yes",
        ),
        environment_variables={
            "APP_ENV": "production",
            "DATABASE_URL": "postgresql://appuser:secure-password@localhost:5432/appdb",
        },
        sysctl_params={
            "net.ipv4.ip_forward": "0",
            "net.ipv4.conf.all.accept_redirects": "0",
            "net.ipv4.conf.all.send_redirects": "0",
        },
        installed_packages=["nginx", "postgresql", "redis-server", "openssh-server"],
        logging_config=LoggingConfig(
            auth_log=True,
            syslog=True,
            access_log=True,
            error_log=True,
            audit_log=True,
        ),
    )

    return {
        "task_id": "security_hardening",
        "name": "Security Hardening",
        "difficulty": "hard",
        "description": (
            "This production server has multiple security issues. Audit and fix them:\n"
            "1. Remove unauthorized user 'tempuser' and fix user configurations\n"
            "   - Service accounts (www-data, postgres) should have no-login shells\n"
            "   - Remove 'deploy' from sudo group, remove 'admin' from root group\n"
            "2. Fix firewall: restrict DB ports (5432, 6379) to localhost, remove exposed debug/metrics/MySQL ports\n"
            "3. Disable insecure services: telnet, ftp\n"
            "4. Remove suspicious cron jobs (beacon + chmod 777)\n"
            "5. Fix file permissions: no 777, secrets at 600, SSH dirs at 700\n"
            "6. Harden SSH: disable root login, disable password auth, max 3 auth tries\n"
            "7. Fix environment: remove DEBUG=true, fix database URL (no root user)\n"
            "8. Harden sysctl: disable ip_forward, accept_redirects, send_redirects\n"
            "9. Remove unnecessary packages: telnet, ftp, gcc, make\n"
            "10. Enable all logging: auth, access, error, audit"
        ),
        "initial_state": initial,
        "target_state": target,
        "max_steps": 50,
    }
