"""FastAPI server wrapping SysConfigEnv for HuggingFace Spaces."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from env import SysConfigEnv

app = FastAPI(title="SysConfig Environment", version="1.0.0")
env = SysConfigEnv()

# Serve static files (frontend assets)
STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ResetRequest(BaseModel):
    task_id: str = "basic_webserver"


class StepRequest(BaseModel):
    action: str


@app.get("/", response_class=HTMLResponse)
def root():
    """Serve the frontend demo page."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>SysConfig</h1><p>Visit <a href='/docs'>/docs</a></p>")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": "sysconfig"}


@app.post("/reset")
def reset(req: ResetRequest = None) -> dict[str, Any]:
    task_id = req.task_id if req else "basic_webserver"
    try:
        obs = env.reset(task_id)
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


def main():
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run("server.app:app", host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
