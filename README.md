---
title: SysConfig Environment
emoji: 🖥️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
---

# SysConfig - Linux Server Configuration Agent Environment

An OpenEnv-compatible environment that challenges AI agents to correctly configure simulated Linux servers through shell-like commands. Tests infrastructure reasoning, system administration knowledge, and multi-step planning.

## Tasks

| Task                 | Difficulty | Description                                                 | Max Steps |
| -------------------- | ---------- | ----------------------------------------------------------- | --------- |
| `basic_webserver`    | Easy       | Set up nginx with proper users, firewall, and permissions   | 15        |
| `multi_service`      | Medium     | Configure nginx + PostgreSQL + Redis stack with isolation   | 35        |
| `security_hardening` | Hard       | Audit and fix 10+ security issues on a misconfigured server | 50        |

## Action Space

Shell-like text commands:

```
useradd <username> [--groups <g1,g2>] [--shell <shell>] [--no-login]
userdel <username>
chmod <mode> <path>
chown <user>:<group> <path>
firewall allow|deny|remove <port>/<protocol> [--from <source>]
service enable|disable|start|stop|restart <service_name>
cron add|remove <user> <schedule> <command>
sshd set <key> <value>
env set|unset <key> [<value>]
sysctl set <key> <value>
apt install|remove <package>
log enable|disable <log_type>
```

## Observation Space

JSON object with full server state: users, firewall rules, services, cron jobs, file permissions, SSH config, environment variables, sysctl params, installed packages, and logging config.

## Scoring

Partial-credit grading (0.0-1.0) comparing current state vs. target across all dimensions. Penalties for extra/unwanted configuration.

## API Endpoints

- `POST /reset` - Reset environment with `{"task_id": "basic_webserver"}`
- `POST /step` - Execute action with `{"action": "service enable nginx"}`
- `GET /state` - Get current server state
- `GET /grade` - Get current score
- `GET /tasks` - List available tasks

## Local Development

```bash
pip install -r requirements.txt
python app.py
```

## Docker

```bash
docker build -t sysconfig-env .
docker run -p 7860:7860 sysconfig-env
```

## Running Inference

```bash
export OPENAI_BASE_URL="https://your-endpoint/v1"
export OPENAI_API_KEY="your-key"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export API_BASE_URL="http://localhost:7860"
python inference.py
```

## Environment Variables

| Variable          | Description          | Default                     |
| ----------------- | -------------------- | --------------------------- |
| `OPENAI_BASE_URL` | LLM API endpoint     | `https://api.openai.com/v1` |
| `OPENAI_API_KEY`  | API key              | `HF_TOKEN` value            |
| `MODEL_NAME`      | Model to use         | `Qwen/Qwen2.5-72B-Instruct` |
| `API_BASE_URL`    | SysConfig server URL | `http://localhost:7860`     |
| `HF_TOKEN`        | HuggingFace token    | -                           |
