---
title: SysConfig Environment
emoji: "🖥️"
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
---

# SysConfig

SysConfig is an OpenEnv-compatible Linux server configuration environment built for agent evaluation. An agent receives the current machine state, reasons about what is missing or insecure, and applies shell-like actions to bring the system into the target configuration.

The project was prepared for "The Recursive" in the Meta PyTorch Hackathon x Scaler School of Technology and is designed to test infrastructure reasoning, system administration knowledge, and multi-step planning.

## What It Includes

- Three progressively harder tasks: `basic_webserver`, `multi_service`, and `security_hardening`
- A FastAPI environment server with reset, step, state, grade, and task discovery endpoints
- An OpenAI-compatible `inference.py` runner for evaluator-driven submissions
- A lightweight static frontend for inspecting the environment in a browser
- Docker packaging for Hugging Face Spaces and OpenEnv-style deployment

## Task Overview

| Task | Difficulty | Focus |
| --- | --- | --- |
| `basic_webserver` | Easy | Users, firewall, nginx, ownership, logging |
| `multi_service` | Medium | Multi-service isolation, permissions, env vars |
| `security_hardening` | Hard | Auditing and fixing production security issues |

## Project Structure

```text
.
├── server/            # Canonical FastAPI app entrypoint
├── static/            # Simple frontend
├── env.py             # Core environment simulation
├── tasks.py           # Task definitions and targets
├── models.py          # State/data models
├── inference.py       # OpenAI-compatible evaluation runner
├── openenv.yaml       # OpenEnv metadata
├── Dockerfile         # HF Space / container deployment
└── app.py             # Compatibility wrapper around server.app
```

## API Endpoints

- `GET /health` — health check
- `GET /tasks` — available tasks
- `POST /reset` — reset environment for a task
- `POST /step` — apply one configuration action
- `GET /state` — inspect current environment state
- `GET /grade` — score progress against the target state

## Local Development

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the server

```bash
python app.py
```

The app will be available at [http://localhost:7860](http://localhost:7860).

### 3. Run the inference client

```bash
export API_BASE_URL="https://your-litellm-proxy/v1"
export API_KEY="your-proxy-key"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export ENV_API_BASE_URL="http://localhost:7860"
python inference.py
```

## Environment Variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `API_BASE_URL` | OpenAI-compatible LLM proxy endpoint | `https://api.openai.com/v1` |
| `API_KEY` | LLM proxy API key | falls back to `OPENAI_API_KEY` |
| `MODEL_NAME` | Model name used by `inference.py` | `gemma-4-31b-it` |
| `ENV_API_BASE_URL` | Local SysConfig server URL | `http://localhost:7860` |
| `OPENAI_BASE_URL` | Legacy fallback LLM endpoint | unset |
| `OPENAI_API_KEY` | Legacy fallback LLM key | `HF_TOKEN` fallback |
| `HF_TOKEN` | Final fallback key source | unset |

## Docker

```bash
docker build -t sysconfig-env .
docker run -p 7860:7860 sysconfig-env
```

## Validation Notes

- The evaluator expects LLM traffic to go through the injected `API_BASE_URL` and `API_KEY`
- The local environment server should stay on `ENV_API_BASE_URL`
- `openenv-core>=0.2.0` is declared for multi-mode deployment validation

## Why This Repo Looks The Way It Does

The repository is kept intentionally small and flat around the environment logic so the core evaluation pieces are easy to inspect:

- `env.py` contains behavior
- `tasks.py` contains scenarios
- `inference.py` contains submission-time agent logic
- `server/` contains the deployable API surface

That makes the code easier to review quickly on GitHub and easier to package for a hackathon submission.
