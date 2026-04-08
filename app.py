"""FastAPI server wrapping SysConfigEnv for HuggingFace Spaces."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from env import SysConfigEnv

app = FastAPI(title="SysConfig Environment", version="1.0.0")
env = SysConfigEnv()


class ResetRequest(BaseModel):
    task_id: str = "basic_webserver"


class StepRequest(BaseModel):
    action: str


@app.get("/")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": "sysconfig"}


@app.post("/reset")
def reset(req: ResetRequest) -> dict[str, Any]:
    try:
        obs = env.reset(req.task_id)
        return obs
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/step")
def step(req: StepRequest) -> dict[str, Any]:
    result = env.step(req.action)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/state")
def state() -> dict[str, Any]:
    return env.get_state()


@app.get("/grade")
def grade() -> dict[str, Any]:
    return env.grade()


@app.get("/tasks")
def list_tasks() -> dict[str, Any]:
    return {
        "tasks": [
            {"id": "basic_webserver", "name": "Basic Web Server Setup", "difficulty": "easy"},
            {"id": "multi_service", "name": "Multi-Service Configuration", "difficulty": "medium"},
            {"id": "security_hardening", "name": "Security Hardening", "difficulty": "hard"},
        ]
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
