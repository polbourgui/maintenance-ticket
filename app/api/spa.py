"""Serves the built single-page application (frontend/dist) from FastAPI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_spa(app: FastAPI, dist: Path, *, api_prefix: str) -> None:
    dist = dist.resolve()
    index = dist / "index.html"
    if not index.is_file():
        raise RuntimeError(f"frontend_dist={dist} does not contain index.html (run npm run build)")
    if (dist / "assets").is_dir():
        # Hashed file names: safe to cache for a long time.
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith(api_prefix.strip("/")):
            raise HTTPException(status_code=404)
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(dist):
            return FileResponse(candidate)
        # Client-side routing: every other path renders the app shell.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
