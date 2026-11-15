"""Vercel entrypoint fallback for projects configured with the FastAPI preset.

Serves the standalone school attendance portal and simulated API endpoints
when deployed in a serverless environment without Docker.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="School Attendance Portal")

FRONTEND_HTML = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
ROOT_HTML = Path(__file__).resolve().parent.parent / "index.html"


def get_html_content() -> str:
    for p in (FRONTEND_HTML, ROOT_HTML):
        if p.exists():
            return p.read_text(encoding="utf-8")
    return "<h1>School Attendance Portal</h1><p>Frontend file not found.</p>"


@app.get("/", response_class=HTMLResponse)
@app.get("/frontend", response_class=HTMLResponse)
@app.get("/frontend/", response_class=HTMLResponse)
def serve_portal():
    return HTMLResponse(content=get_html_content(), status_code=200)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "version": "v1.0.0-vercel"}


@app.get("/readyz")
def readyz():
    return {"status": "ready", "database": "browser-simulated"}
