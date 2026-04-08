"""Core SysConfig environment implementing OpenEnv spec."""

from __future__ import annotations

import copy
import json
import re
import shlex
from typing import Any

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
from tasks import get_task


class SysConfigEnv:
    """OpenEnv environment for Linux server configuration tasks."""

    def __init__(self) -> None:
        self.state: ServerState | None = None
        self.target: ServerState | None = None
        self.task_id: str | None = None
        self.task_info: dict | None = None
        self.steps_taken: int = 0
        self.max_steps: int = 0
        self.action_history: list[dict] = []
        self.done: bool = False

    def reset(self, task_id: str = "basic_webserver") -> dict[str, Any]:
        """Reset the environment to the initial state for a given task."""
        task = get_task(task_id)
        self.task_id = task_id
        self.task_info = task
        self.state = copy.deepcopy(task["initial_state"])
        self.target = task["target_state"]
        self.steps_taken = 0
        self.max_steps = task["max_steps"]
        self.action_history = []
        self.done = False

        return self.get_state()

    def get_state(self) -> dict[str, Any]:
        """Return the current observable state."""
        if self.state is None:
            return {"error": "Environment not initialized. Call reset() first."}

        return {
            "task": {
                "id": self.task_id,
                "name": self.task_info["name"],
                "difficulty": self.task_info["difficulty"],
                "description": self.task_info["description"],
            },
            "server_state": self.state.to_dict(),
            "steps_taken": self.steps_taken,
            "max_steps": self.max_steps,
            "done": self.done,
        }

    def step(self, action: str) -> dict[str, Any]:
        """Execute an action and return the new state + reward."""
        if self.state is None:
            return {"error": "Environment not initialized. Call reset() first."}
        if self.done:
            return {
                "observation": self.get_state(),
                "reward": self._compute_reward(),
                "done": True,
                "info": {"message": "Episode already finished."},
            }

        self.steps_taken += 1

        # Parse and execute the action
        result = self._execute_action(action)

        self.action_history.append({"step": self.steps_taken, "action": action, "result": result})

        # Check if done
        if self.steps_taken >= self.max_steps:
            self.done = True

        reward = self._compute_reward()

        return {
            "observation": self.get_state(),
            "reward": reward,
            "done": self.done,
            "info": {"action_result": result},
        }

    def _execute_action(self, action: str) -> dict[str, Any]:
        """Parse and execute a single action on the server state."""
        action = action.strip()
        if not action:
            return {"success": False, "message": "Empty action."}

        # Use shlex-like parsing to handle quoted arguments
        try:
            parts = shlex.split(action)
        except ValueError:
            parts = action.split()
        cmd = parts[0].lower()

        try:
            if cmd == "useradd":
                return self._cmd_useradd(parts[1:])
            elif cmd == "userdel":
                return self._cmd_userdel(parts[1:])
            elif cmd == "usermod":
                return self._cmd_usermod(parts[1:])
            elif cmd == "passwd":
                return self._cmd_passwd(parts[1:])
            elif cmd == "chmod":
                return self._cmd_chmod(parts[1:])
            elif cmd == "chown":
                return self._cmd_chown(parts[1:])
            elif cmd == "firewall":
                return self._cmd_firewall(parts[1:])
            elif cmd == "service":
                return self._cmd_service(parts[1:])
            elif cmd == "cron":
                return self._cmd_cron(parts[1:])
            elif cmd == "sshd":
                return self._cmd_sshd(parts[1:])
            elif cmd == "env":
                return self._cmd_env(parts[1:])
            elif cmd == "sysctl":
                return self._cmd_sysctl(parts[1:])
            elif cmd == "apt":
                return self._cmd_apt(parts[1:])
            elif cmd == "log":
                return self._cmd_log(parts[1:])
            else:
                return {"success": False, "message": f"Unknown command: {cmd}"}
        except (IndexError, ValueError) as e:
            return {"success": False, "message": f"Invalid syntax: {e}"}

    def _cmd_useradd(self, args: list[str]) -> dict:
        if not args:
            return {"success": False, "message": "Usage: useradd <username> [--groups g1,g2] [--shell sh] [--no-login]"}
        username = args[0]
        if any(u.name == username for u in self.state.users):
            return {"success": False, "message": f"User '{username}' already exists."}

        groups = []
        shell = "/bin/bash"
        has_login = True

        i = 1
        while i < len(args):
            if args[i] == "--groups" and i + 1 < len(args):
                groups = args[i + 1].split(",")
                i += 2
            elif args[i] == "--shell" and i + 1 < len(args):
                shell = args[i + 1]
                i += 2
            elif args[i] == "--no-login":
                has_login = False
                shell = "/usr/sbin/nologin"
                i += 1
            else:
                i += 1

        self.state.users.append(User(name=username, groups=groups, shell=shell, has_login=has_login))
        return {"success": True, "message": f"User '{username}' created."}

    def _cmd_userdel(self, args: list[str]) -> dict:
        if not args:
            return {"success": False, "message": "Usage: userdel <username>"}
        username = args[0]
        before = len(self.state.users)
        self.state.users = [u for u in self.state.users if u.name != username]
        if len(self.state.users) == before:
            return {"success": False, "message": f"User '{username}' not found."}
        # Also remove their cron jobs
        self.state.cron_jobs = [c for c in self.state.cron_jobs if c.user != username]
        return {"success": True, "message": f"User '{username}' removed."}

    def _cmd_usermod(self, args: list[str]) -> dict:
        if not args:
            return {"success": False, "message": "Usage: usermod <username> [--groups g1,g2] [--shell sh] [--no-login]"}
        username = args[0]
        user = None
        for u in self.state.users:
            if u.name == username:
                user = u
                break
        if not user:
            return {"success": False, "message": f"User '{username}' not found."}

        i = 1
        while i < len(args):
            if args[i] == "--groups" and i + 1 < len(args):
                user.groups = args[i + 1].split(",")
                i += 2
            elif args[i] == "--shell" and i + 1 < len(args):
                user.shell = args[i + 1]
                if args[i + 1] == "/usr/sbin/nologin":
                    user.has_login = False
                else:
                    user.has_login = True
                i += 2
            elif args[i] == "--no-login":
                user.has_login = False
                user.shell = "/usr/sbin/nologin"
                i += 1
            else:
                i += 1

        return {"success": True, "message": f"User '{username}' modified."}

    def _cmd_passwd(self, args: list[str]) -> dict:
        if len(args) < 3 or args[1] != "--set-policy":
            return {"success": False, "message": "Usage: passwd <username> --set-policy <policy>"}
        username, policy = args[0], args[2]
        for u in self.state.users:
            if u.name == username:
                u.password_policy = policy
                return {"success": True, "message": f"Password policy for '{username}' set to '{policy}'."}
        return {"success": False, "message": f"User '{username}' not found."}

    def _cmd_chmod(self, args: list[str]) -> dict:
        if len(args) < 2:
            return {"success": False, "message": "Usage: chmod <mode> <path>"}
        mode, path = args[0], args[1]
        for fp in self.state.file_permissions:
            if fp.path == path:
                fp.mode = mode
                return {"success": True, "message": f"Permissions on '{path}' set to {mode}."}
        return {"success": False, "message": f"Path '{path}' not found in tracked files."}

    def _cmd_chown(self, args: list[str]) -> dict:
        if len(args) < 2:
            return {"success": False, "message": "Usage: chown <user>:<group> <path>"}
        ownership, path = args[0], args[1]
        if ":" not in ownership:
            return {"success": False, "message": "Format: user:group"}
        owner, group = ownership.split(":", 1)
        for fp in self.state.file_permissions:
            if fp.path == path:
                fp.owner = owner
                fp.group = group
                return {"success": True, "message": f"Ownership of '{path}' set to {owner}:{group}."}
        return {"success": False, "message": f"Path '{path}' not found in tracked files."}

    def _cmd_firewall(self, args: list[str]) -> dict:
        if len(args) < 2:
            return {"success": False, "message": "Usage: firewall allow|deny|remove <port>/<protocol> [--from <source>]"}
        action_type = args[0]
        port_proto = args[1]
        source = "any"

        if "--from" in args:
            idx = args.index("--from")
            if idx + 1 < len(args):
                source = args[idx + 1]

        if "/" in port_proto:
            port_str, protocol = port_proto.split("/", 1)
        else:
            port_str, protocol = port_proto, "tcp"

        port = int(port_str)

        if action_type == "remove":
            before = len(self.state.firewall_rules)
            self.state.firewall_rules = [
                r for r in self.state.firewall_rules
                if not (r.port == port and r.protocol == protocol)
            ]
            if len(self.state.firewall_rules) < before:
                return {"success": True, "message": f"Removed firewall rule for {port}/{protocol}."}
            return {"success": False, "message": f"No rule found for {port}/{protocol}."}
        elif action_type in ("allow", "deny"):
            # Remove existing rule for this port/proto first
            self.state.firewall_rules = [
                r for r in self.state.firewall_rules
                if not (r.port == port and r.protocol == protocol)
            ]
            self.state.firewall_rules.append(
                FirewallRule(port=port, protocol=protocol, action=action_type, source=source)
            )
            return {"success": True, "message": f"Firewall: {action_type} {port}/{protocol} from {source}."}
        else:
            return {"success": False, "message": f"Unknown firewall action: {action_type}"}

    def _cmd_service(self, args: list[str]) -> dict:
        if len(args) < 2:
            return {"success": False, "message": "Usage: service enable|disable|start|stop|restart <name>"}
        action_type, name = args[0], args[1]
        for svc in self.state.services:
            if svc.name == name:
                if action_type == "enable":
                    svc.enabled = True
                elif action_type == "disable":
                    svc.enabled = False
                    svc.running = False
                elif action_type == "start":
                    svc.running = True
                elif action_type == "stop":
                    svc.running = False
                elif action_type == "restart":
                    svc.running = True
                else:
                    return {"success": False, "message": f"Unknown service action: {action_type}"}
                return {"success": True, "message": f"Service '{name}': {action_type}."}
        return {"success": False, "message": f"Service '{name}' not found."}

    def _cmd_cron(self, args: list[str]) -> dict:
        if len(args) < 2:
            return {"success": False, "message": "Usage: cron add|remove <user> <schedule> <command>"}
        action_type = args[0]
        if action_type == "remove" and len(args) >= 2:
            user = args[1]
            if len(args) >= 3:
                # Remove specific cron by matching command substring
                cmd_match = " ".join(args[2:])
                before = len(self.state.cron_jobs)
                self.state.cron_jobs = [
                    c for c in self.state.cron_jobs
                    if not (c.user == user and cmd_match in c.command)
                ]
                if len(self.state.cron_jobs) < before:
                    return {"success": True, "message": f"Removed cron job for '{user}' matching '{cmd_match}'."}
                return {"success": False, "message": f"No matching cron job found."}
            else:
                # Remove all crons for user
                before = len(self.state.cron_jobs)
                self.state.cron_jobs = [c for c in self.state.cron_jobs if c.user != user]
                removed = before - len(self.state.cron_jobs)
                return {"success": True, "message": f"Removed {removed} cron job(s) for '{user}'."}
        elif action_type == "add" and len(args) >= 8:
            # cron add <user> <m> <h> <dom> <mon> <dow> <command...>
            user = args[1]
            schedule = " ".join(args[2:7])
            command = " ".join(args[7:])
            self.state.cron_jobs.append(CronJob(user=user, schedule=schedule, command=command))
            return {"success": True, "message": f"Added cron job for '{user}'."}
        return {"success": False, "message": "Invalid cron syntax."}

    def _cmd_sshd(self, args: list[str]) -> dict:
        if len(args) < 3 or args[0] != "set":
            return {"success": False, "message": "Usage: sshd set <key> <value>"}
        key, value = args[1], args[2]
        cfg = self.state.ssh_config
        key_map = {
            "permit_root_login": "permit_root_login",
            "permitrootlogin": "permit_root_login",
            "password_authentication": "password_authentication",
            "passwordauthentication": "password_authentication",
            "port": "port",
            "max_auth_tries": "max_auth_tries",
            "maxauthtries": "max_auth_tries",
            "pubkey_authentication": "pubkey_authentication",
            "pubkeyauthentication": "pubkey_authentication",
        }
        normalized = key.lower().replace("-", "_")
        if normalized in key_map:
            attr = key_map[normalized]
            if attr == "port" or attr == "max_auth_tries":
                setattr(cfg, attr, int(value))
            else:
                setattr(cfg, attr, value)
            return {"success": True, "message": f"SSH config: {key} = {value}"}
        return {"success": False, "message": f"Unknown SSH config key: {key}"}

    def _cmd_env(self, args: list[str]) -> dict:
        if len(args) < 2:
            return {"success": False, "message": "Usage: env set|unset <key> [<value>]"}
        action_type, key = args[0], args[1]
        if action_type == "set" and len(args) >= 3:
            value = " ".join(args[2:])
            self.state.environment_variables[key] = value
            return {"success": True, "message": f"Environment: {key} = {value}"}
        elif action_type == "unset":
            if key in self.state.environment_variables:
                del self.state.environment_variables[key]
                return {"success": True, "message": f"Unset environment variable: {key}"}
            return {"success": False, "message": f"Variable '{key}' not set."}
        return {"success": False, "message": "Invalid env syntax."}

    def _cmd_sysctl(self, args: list[str]) -> dict:
        if len(args) < 3 or args[0] != "set":
            return {"success": False, "message": "Usage: sysctl set <key> <value>"}
        key, value = args[1], args[2]
        self.state.sysctl_params[key] = value
        return {"success": True, "message": f"sysctl: {key} = {value}"}

    def _cmd_apt(self, args: list[str]) -> dict:
        if len(args) < 2:
            return {"success": False, "message": "Usage: apt install|remove <package>"}
        action_type, package = args[0], args[1]
        if action_type == "install":
            if package not in self.state.installed_packages:
                self.state.installed_packages.append(package)
            return {"success": True, "message": f"Package '{package}' installed."}
        elif action_type == "remove":
            if package in self.state.installed_packages:
                self.state.installed_packages.remove(package)
                return {"success": True, "message": f"Package '{package}' removed."}
            return {"success": False, "message": f"Package '{package}' not installed."}
        return {"success": False, "message": f"Unknown apt action: {action_type}"}

    def _cmd_log(self, args: list[str]) -> dict:
        if len(args) < 2:
            return {"success": False, "message": "Usage: log enable|disable <log_type>"}
        action_type, log_type = args[0], args[1]
        log_map = {
            "auth": "auth_log",
            "auth_log": "auth_log",
            "syslog": "syslog",
            "access": "access_log",
            "access_log": "access_log",
            "error": "error_log",
            "error_log": "error_log",
            "audit": "audit_log",
            "audit_log": "audit_log",
        }
        normalized = log_type.lower().replace("-", "_")
        if normalized in log_map:
            attr = log_map[normalized]
            if action_type == "enable":
                setattr(self.state.logging_config, attr, True)
            elif action_type == "disable":
                setattr(self.state.logging_config, attr, False)
            else:
                return {"success": False, "message": f"Unknown log action: {action_type}"}
            return {"success": True, "message": f"Logging: {log_type} {action_type}d."}
        return {"success": False, "message": f"Unknown log type: {log_type}"}

    def _compute_reward(self) -> float:
        """Compute reward by comparing current state to target state (0.0-1.0)."""
        if self.state is None or self.target is None:
            return 0.0

        current = self.state.to_dict()
        target = self.target.to_dict()

        total_checks = 0
        passed_checks = 0

        # Compare users
        target_users = {u["name"]: u for u in target["users"]}
        current_users = {u["name"]: u for u in current["users"]}
        for uname, tuser in target_users.items():
            total_checks += 1
            if uname in current_users:
                cu = current_users[uname]
                if (
                    set(cu["groups"]) == set(tuser["groups"])
                    and cu["shell"] == tuser["shell"]
                    and cu["has_login"] == tuser["has_login"]
                ):
                    passed_checks += 1
                else:
                    # Partial credit for user existing
                    passed_checks += 0.3

        # Check no extra users
        extra_users = set(current_users.keys()) - set(target_users.keys())
        for _ in extra_users:
            total_checks += 1  # penalize extra users

        # Compare firewall rules
        target_rules = {(r["port"], r["protocol"]): r for r in target["firewall_rules"]}
        current_rules = {(r["port"], r["protocol"]): r for r in current["firewall_rules"]}
        for key, trule in target_rules.items():
            total_checks += 1
            if key in current_rules:
                cr = current_rules[key]
                if cr["action"] == trule["action"] and cr["source"] == trule["source"]:
                    passed_checks += 1
                else:
                    passed_checks += 0.3

        # Penalize extra firewall rules
        extra_rules = set(current_rules.keys()) - set(target_rules.keys())
        for _ in extra_rules:
            total_checks += 1

        # Compare services
        target_svcs = {s["name"]: s for s in target["services"]}
        current_svcs = {s["name"]: s for s in current["services"]}
        for sname, tsvc in target_svcs.items():
            total_checks += 1
            if sname in current_svcs:
                cs = current_svcs[sname]
                if cs["enabled"] == tsvc["enabled"] and cs["running"] == tsvc["running"]:
                    passed_checks += 1
                else:
                    passed_checks += 0.3

        # Compare cron jobs
        target_crons = {(c["user"], c["command"]): c for c in target["cron_jobs"]}
        current_crons = {(c["user"], c["command"]): c for c in current["cron_jobs"]}
        for key in target_crons:
            total_checks += 1
            if key in current_crons:
                passed_checks += 1
        for key in current_crons:
            if key not in target_crons:
                total_checks += 1  # penalize extra crons

        # Compare file permissions
        target_fps = {f["path"]: f for f in target["file_permissions"]}
        current_fps = {f["path"]: f for f in current["file_permissions"]}
        for path, tfp in target_fps.items():
            total_checks += 1
            if path in current_fps:
                cfp = current_fps[path]
                if cfp["owner"] == tfp["owner"] and cfp["group"] == tfp["group"] and cfp["mode"] == tfp["mode"]:
                    passed_checks += 1
                else:
                    # Partial: some attributes match
                    matches = sum([
                        cfp["owner"] == tfp["owner"],
                        cfp["group"] == tfp["group"],
                        cfp["mode"] == tfp["mode"],
                    ])
                    passed_checks += matches / 3

        # Compare SSH config
        ssh_fields = ["permit_root_login", "password_authentication", "port", "max_auth_tries", "pubkey_authentication"]
        for field in ssh_fields:
            total_checks += 1
            if current["ssh_config"][field] == target["ssh_config"][field]:
                passed_checks += 1

        # Compare environment variables
        for key, tval in target["environment_variables"].items():
            total_checks += 1
            if current["environment_variables"].get(key) == tval:
                passed_checks += 1
        # Penalize extra env vars
        extra_env = set(current["environment_variables"].keys()) - set(target["environment_variables"].keys())
        for _ in extra_env:
            total_checks += 1

        # Compare sysctl
        for key, tval in target["sysctl_params"].items():
            total_checks += 1
            if current["sysctl_params"].get(key) == tval:
                passed_checks += 1

        # Compare packages
        target_pkgs = set(target["installed_packages"])
        current_pkgs = set(current["installed_packages"])
        for pkg in target_pkgs:
            total_checks += 1
            if pkg in current_pkgs:
                passed_checks += 1
        for pkg in current_pkgs - target_pkgs:
            total_checks += 1  # penalize extra packages

        # Compare logging
        log_fields = ["auth_log", "syslog", "access_log", "error_log", "audit_log"]
        for field in log_fields:
            total_checks += 1
            if current["logging_config"][field] == target["logging_config"][field]:
                passed_checks += 1

        if total_checks == 0:
            return 1.0
        return round(min(1.0, max(0.0, passed_checks / total_checks)), 4)

    def grade(self) -> dict[str, Any]:
        """Grade the current episode."""
        reward = self._compute_reward()
        return {
            "score": reward,
            "reward": reward,
            "steps_taken": self.steps_taken,
            "max_steps": self.max_steps,
            "task_id": self.task_id,
            "done": self.done,
        }
