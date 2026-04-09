"""Inference script with structured [START]/[STEP]/[END] logging using OpenAI Client.

Uses tool/function calling for robust structured output across models.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback

import requests
from openai import OpenAI

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:7860")
MODEL_NAME = os.environ.get("MODEL_NAME", "gemma-4-31b-it")
HF_TOKEN = os.environ.get("HF_TOKEN", "")

DEFAULT_TASKS = ["basic_webserver", "multi_service", "security_hardening"]
RUN_SINGLE = os.environ.get("RUN_TASK", "")

REQUEST_TIMEOUT = 30  # seconds for HTTP requests


class EnvRequestError(RuntimeError):
    """Raised when the env API returns an error we want to surface cleanly."""


def _safe_json(response: requests.Response) -> dict:
    """Parse JSON responses defensively so bad payloads don't crash inference."""
    try:
        payload = response.json()
    except ValueError as exc:
        snippet = response.text[:300].strip()
        raise EnvRequestError(
            f"Non-JSON response from {response.request.method} {response.url}: "
            f"status={response.status_code}, body={snippet or '<empty>'}"
        ) from exc

    if not isinstance(payload, dict):
        raise EnvRequestError(
            f"Unexpected JSON payload from {response.request.method} {response.url}: "
            f"expected object, got {type(payload).__name__}"
        )
    return payload

SYSTEM_PROMPT = (
    "You are an expert Linux sysadmin. You configure servers by calling the provided tools. "
    "Read the current server state and task description carefully, then call the appropriate tool. "
    "Call exactly one tool per turn. Work through ALL requirements systematically. "
    "Compare the current state against EVERY requirement in the task description. "
    "Do NOT repeat an action you already took. If a requirement is already satisfied in the current state, skip it and move to the next unsatisfied requirement."
)

# --- Tool definitions (one per command) ---
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "useradd",
            "description": "Create a new system user",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Username to create"},
                    "groups": {"type": "string", "description": "Comma-separated group list (e.g. 'www-data,appgroup')"},
                    "shell": {"type": "string", "description": "Login shell path"},
                    "no_login": {"type": "boolean", "description": "If true, set shell to /usr/sbin/nologin"},
                },
                "required": ["username"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "userdel",
            "description": "Delete a user",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                },
                "required": ["username"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "usermod",
            "description": "Modify an existing user's groups, shell, or login status",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Username to modify"},
                    "groups": {"type": "string", "description": "New comma-separated group list (replaces existing groups)"},
                    "shell": {"type": "string", "description": "New login shell path"},
                    "no_login": {"type": "boolean", "description": "If true, set shell to /usr/sbin/nologin"},
                },
                "required": ["username"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "chmod",
            "description": "Change file permissions",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "description": "Permission mode, e.g. '0755', '0600'"},
                    "path": {"type": "string", "description": "File/directory path"},
                },
                "required": ["mode", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "chown",
            "description": "Change file ownership",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "owner:group (e.g. 'www-data:www-data')"},
                    "path": {"type": "string", "description": "File/directory path"},
                },
                "required": ["owner", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "firewall",
            "description": "Manage firewall rules: allow, deny, or remove a port rule",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["allow", "deny", "remove"]},
                    "port": {"type": "integer", "description": "Port number"},
                    "protocol": {"type": "string", "enum": ["tcp", "udp"], "description": "Protocol (default tcp)"},
                    "source": {"type": "string", "description": "Source IP/range, e.g. '127.0.0.1' or 'any'"},
                },
                "required": ["action", "port"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "service",
            "description": "Manage system services",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["enable", "disable", "start", "stop", "restart"]},
                    "name": {"type": "string", "description": "Service name"},
                },
                "required": ["action", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cron",
            "description": "Add or remove cron jobs",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["add", "remove"]},
                    "user": {"type": "string", "description": "Cron job owner"},
                    "schedule": {"type": "string", "description": "Cron schedule (5 fields) for add, omit for remove-all"},
                    "command": {"type": "string", "description": "Command to run (for add) or substring to match (for remove)"},
                },
                "required": ["action", "user"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sshd",
            "description": "Configure SSH daemon settings",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "SSH config key (e.g. permit_root_login, password_authentication, max_auth_tries, port, pubkey_authentication)"},
                    "value": {"type": "string", "description": "Value to set"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "env",
            "description": "Set or unset environment variables",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["set", "unset"]},
                    "key": {"type": "string"},
                    "value": {"type": "string", "description": "Value (required for set, omit for unset)"},
                },
                "required": ["action", "key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sysctl",
            "description": "Set kernel parameters",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Parameter name (e.g. net.ipv4.ip_forward)"},
                    "value": {"type": "string", "description": "Parameter value"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apt",
            "description": "Install or remove packages",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["install", "remove"]},
                    "package": {"type": "string"},
                },
                "required": ["action", "package"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log",
            "description": "Enable or disable logging types",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["enable", "disable"]},
                    "log_type": {"type": "string", "description": "Log type: auth, syslog, access, error, audit"},
                },
                "required": ["action", "log_type"],
            },
        },
    },
]


def tool_call_to_command(name: str, args: dict) -> str:
    """Convert a tool call into the shell-like command string the env expects."""
    if name == "useradd":
        cmd = f"useradd {args['username']}"
        if args.get("groups"):
            cmd += f" --groups {args['groups']}"
        if args.get("shell"):
            cmd += f" --shell {args['shell']}"
        if args.get("no_login"):
            cmd += " --no-login"
        return cmd
    elif name == "userdel":
        return f"userdel {args['username']}"
    elif name == "usermod":
        cmd = f"usermod {args['username']}"
        if args.get("groups"):
            cmd += f" --groups {args['groups']}"
        if args.get("shell"):
            cmd += f" --shell {args['shell']}"
        if args.get("no_login"):
            cmd += " --no-login"
        return cmd
    elif name == "chmod":
        return f"chmod {args['mode']} {args['path']}"
    elif name == "chown":
        return f"chown {args['owner']} {args['path']}"
    elif name == "firewall":
        proto = args.get("protocol", "tcp")
        cmd = f"firewall {args['action']} {args['port']}/{proto}"
        if args.get("source") and args["source"] != "any":
            cmd += f" --from {args['source']}"
        return cmd
    elif name == "service":
        return f"service {args['action']} {args['name']}"
    elif name == "cron":
        cmd = f"cron {args['action']} {args['user']}"
        if args.get("schedule"):
            cmd += f" {args['schedule']}"
        if args.get("command"):
            cmd += f" {args['command']}"
        return cmd
    elif name == "sshd":
        return f"sshd set {args['key']} {args['value']}"
    elif name == "env":
        if args["action"] == "set":
            return f"env set {args['key']} {args.get('value', '')}"
        return f"env unset {args['key']}"
    elif name == "sysctl":
        return f"sysctl set {args['key']} {args['value']}"
    elif name == "apt":
        return f"apt {args['action']} {args['package']}"
    elif name == "log":
        return f"log {args['action']} {args['log_type']}"
    return ""


def get_client() -> OpenAI:
    base_url = os.environ.get(
        "OPENAI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    api_key = os.environ.get("OPENAI_API_KEY", "")
    return OpenAI(base_url=base_url, api_key=api_key)


def wait_for_server(max_wait: int = 120) -> bool:
    """Wait for the env server to become reachable. Returns True if healthy."""
    print(f"Waiting for environment server at {API_BASE_URL} ...", flush=True)
    start = time.time()
    while time.time() - start < max_wait:
        try:
            resp = requests.get(f"{API_BASE_URL}/health", timeout=5)
            if resp.status_code == 200:
                print(f"  Server is ready (took {time.time() - start:.1f}s)", flush=True)
                return True
        except requests.exceptions.ConnectionError:
            pass
        except requests.exceptions.Timeout:
            pass
        except Exception:
            pass
        time.sleep(2)
    print(f"  WARNING: Server not reachable after {max_wait}s", flush=True)
    return False


def _request_with_retry(method: str, url: str, max_retries: int = 3, **kwargs) -> requests.Response:
    """Make an HTTP request with retry logic and timeouts."""
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    last_exc = None
    for attempt in range(max_retries):
        resp = None
        try:
            resp = requests.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as e:
            # 4xx errors are not retryable (except 429)
            if resp.status_code == 429:
                wait = min(30, 5 * (attempt + 1))
                print(f"  Rate limited (429), retrying in {wait}s...", flush=True)
                time.sleep(wait)
                last_exc = e
                continue
            elif 400 <= resp.status_code < 500:
                body = resp.text[:300].strip() if resp is not None else ""
                raise EnvRequestError(
                    f"{method} {url} failed with status={resp.status_code}. "
                    f"Body: {body or '<empty>'}"
                ) from e
            body = resp.text[:300].strip() if resp is not None else ""
            last_exc = EnvRequestError(
                f"{method} {url} failed with status={resp.status_code}. "
                f"Body: {body or '<empty>'}"
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_exc = e
        except requests.exceptions.RequestException as e:
            last_exc = e
        wait = min(30, 3 * (attempt + 1))
        print(f"  Request failed (attempt {attempt + 1}/{max_retries}): {last_exc}, retrying in {wait}s...", flush=True)
        time.sleep(wait)
    raise EnvRequestError(f"{method} {url} failed after {max_retries} attempts: {last_exc}") from last_exc


def discover_tasks() -> list[str]:
    """Fetch available task ids from the env server, with a safe fallback."""
    if RUN_SINGLE:
        return [RUN_SINGLE]

    try:
        resp = _request_with_retry("GET", f"{API_BASE_URL}/tasks", max_retries=2)
        payload = _safe_json(resp)
        tasks = payload.get("tasks", [])
        task_ids = [
            task.get("id")
            for task in tasks
            if isinstance(task, dict) and isinstance(task.get("id"), str) and task.get("id")
        ]
        if task_ids:
            print(f"Discovered tasks from environment: {task_ids}", flush=True)
            return task_ids
        print("  WARNING: /tasks returned no usable ids, using built-in defaults.", flush=True)
    except Exception as e:
        print(f"  WARNING: Could not discover tasks from environment: {e}", flush=True)

    return list(DEFAULT_TASKS)


def env_reset(task_id: str) -> dict:
    resp = _request_with_retry("POST", f"{API_BASE_URL}/reset", json={"task_id": task_id})
    return _safe_json(resp)


def env_step(action: str) -> dict:
    resp = _request_with_retry("POST", f"{API_BASE_URL}/step", json={"action": action})
    return _safe_json(resp)


def env_grade() -> dict:
    resp = _request_with_retry("GET", f"{API_BASE_URL}/grade")
    return _safe_json(resp)


def format_state_for_llm(obs: dict) -> str:
    task = obs.get("task", {})
    state = obs.get("server_state", {})
    steps = obs.get("steps_taken", 0)
    max_steps = obs.get("max_steps", 0)
    return (
        f"Task: {task.get('description', '')}\n"
        f"Step {steps}/{max_steps}. Current server state:\n"
        f"{json.dumps(state, indent=2)}\n\n"
        "Call the appropriate tool for the next configuration step."
    )


def llm_call_with_retry(client: OpenAI, messages: list, max_retries: int = 4) -> tuple[str, str]:
    """Call LLM with tool calling. Returns (command_string, tool_name) or ('', '') on failure."""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=TOOLS,
                tool_choice="required",
                max_tokens=300,
                temperature=0.0,
            )
            time.sleep(4.5)  # rate limit spacing

            msg = response.choices[0].message
            if msg.tool_calls:
                tc = msg.tool_calls[0]
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                cmd = tool_call_to_command(name, args)
                return cmd, name
            return "", ""
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                wait = min(65, 20 * (attempt + 1))
                print(f"  Rate limited, waiting {wait}s...", flush=True)
                time.sleep(wait)
            else:
                print(f"  LLM error: {e}", flush=True)
                return "", ""
    return "", ""


def run_task(client: OpenAI, task_id: str) -> dict:
    """Run a single task and return the result."""
    print(f"\n[START] task={task_id}", flush=True)

    try:
        obs = env_reset(task_id)
    except Exception as e:
        print(f"[END] task={task_id} score=0.0 (reset failed: {e})", flush=True)
        return {"task_id": task_id, "score": 0.0, "steps_taken": 0}

    max_steps = obs.get("max_steps", 15)
    action_history: list[str] = []
    failed_actions: list[str] = []
    repeat_count = 0

    for step_num in range(1, max_steps + 1):
        state_text = format_state_for_llm(obs)
        if action_history:
            history_str = "\n".join(f"  - {a}" for a in action_history)
            state_text += f"\n\nActions already taken (do NOT repeat these):\n{history_str}"
        if failed_actions:
            failed_str = "\n".join(f"  - {a}" for a in failed_actions)
            state_text += f"\n\nFailed actions (these did NOT work, try a different approach):\n{failed_str}"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": state_text},
        ]

        action, tool_name = llm_call_with_retry(client, messages)

        if not action:
            print(f"[STEP] step={step_num} action=<empty> reward=0.0", flush=True)
            continue

        # Detect repeated actions — stop early if stuck
        if action in action_history:
            repeat_count += 1
            if repeat_count >= 3:
                print(f"[STEP] step={step_num} action={action!r} STUCK (repeated 3x), stopping early", flush=True)
                break
        else:
            repeat_count = 0

        action_history.append(action)

        try:
            result = env_step(action)
        except Exception as e:
            print(f"[STEP] step={step_num} action={action!r} ERROR: {e}", flush=True)
            failed_actions.append(f"{action} (network error)")
            continue

        reward = result.get("reward", 0.0)
        done = result.get("done", False)
        info = result.get("info", {})
        action_result = info.get("action_result", {})
        success = action_result.get("success", False)

        if not success:
            msg = action_result.get("message", "failed")
            failed_actions.append(f"{action} ({msg})")

        print(
            f"[STEP] step={step_num} action={action!r} "
            f"reward={reward} success={success}",
            flush=True,
        )

        obs = result.get("observation", obs)

        if done or reward >= 0.99:
            break

    try:
        grade = env_grade()
        final_score = grade.get("score", 0.0)
    except Exception as e:
        print(f"  Grading failed: {e}", flush=True)
        final_score = 0.0
        grade = {}

    print(f"[END] task={task_id} score={final_score}", flush=True)

    return {
        "task_id": task_id,
        "score": final_score,
        "steps_taken": grade.get("steps_taken", 0),
    }


def main():
    # Wait for the env server to be ready before starting
    server_ok = wait_for_server(max_wait=120)
    if not server_ok:
        print("ERROR: Environment server not reachable. Exiting.", flush=True)
        # Still try to proceed — the evaluator might bring it up later
        # Don't sys.exit here; let it fail gracefully per-task instead

    client = get_client()
    results = []
    tasks = discover_tasks()
    print(f"Running tasks: {tasks}", flush=True)

    for task_id in tasks:
        try:
            result = run_task(client, task_id)
        except Exception as e:
            print(f"[END] task={task_id} score=0.0 (unhandled error: {e})", flush=True)
            traceback.print_exc()
            result = {"task_id": task_id, "score": 0.0, "steps_taken": 0}
        results.append(result)

    print("\n=== Final Results ===")
    for r in results:
        print(f"  {r['task_id']}: score={r['score']:.4f} steps={r['steps_taken']}")

    avg_score = sum(r["score"] for r in results) / len(results) if results else 0
    print(f"  Average Score: {avg_score:.4f}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FATAL ERROR: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
