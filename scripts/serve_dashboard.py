#!/usr/bin/env python3
"""DYLIGHT Bridge Research Lab — Visual Dashboard Server.

Serves the frontend dashboard and provides live JSON APIs for multi-agent tasks,
handoffs, reviews, physics screening, and parametric geometry calculation.
"""

from __future__ import annotations

from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import os
from pathlib import Path
import sys
import urllib.parse
import webbrowser

REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"
MULTIAGENT_DIR = REPO_ROOT / "multiagent"


def get_live_data() -> dict:
    tasks = {}
    for p in sorted((MULTIAGENT_DIR / "tasks").glob("*.json")):
        try:
            tasks[p.stem] = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass

    handoffs = []
    for p in sorted((MULTIAGENT_DIR / "handoffs").glob("*.json")):
        if p.name == ".gitkeep":
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            data["filename"] = p.name
            handoffs.append(data)
        except Exception:
            pass

    reviews = []
    for p in sorted((MULTIAGENT_DIR / "reviews").glob("*.json")):
        if p.name == ".gitkeep":
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            data["filename"] = p.name
            reviews.append(data)
        except Exception:
            pass

    runs = {}
    for p in sorted((MULTIAGENT_DIR / "runs").glob("*/run.json")):
        try:
            runs[p.parent.name] = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass

    briefs = {}
    for p in sorted((MULTIAGENT_DIR / "intake").glob("*.json")):
        try:
            briefs[p.stem] = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Read unverified claims
    claims_text = ""
    claims_file = REPO_ROOT / "research" / "materials" / "unverified_claims_register.md"
    if claims_file.is_file():
        claims_text = claims_file.read_text(encoding="utf-8")

    return {
        "tasks": tasks,
        "handoffs": handoffs,
        "reviews": reviews,
        "runs": runs,
        "briefs": briefs,
        "claims_register_md": claims_text,
        "providers": {
            "codex": {"status": "ONLINE", "role": "Independent Reviewer & Structural Analyst", "version": "0.148.0"},
            "claude": {"status": "ONLINE", "role": "Materials Researcher & Shape Inventor", "version": "2.1.237"},
            "antigravity": {"status": "ACTIVE", "role": "Lab Orchestrator & Research Architect", "version": "Antigravity 2.0"},
            "opencode": {"status": "STANDBY", "role": "Independent Reproducer", "version": "1.18.19"},
        }
    }


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/live-data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            data = get_live_data()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            return
        elif parsed.path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return
        super().do_GET()

    def log_message(self, format, *args):
        pass


def run_server(port: int = 8765, open_browser: bool = False):
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, DashboardHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"===========================================================")
    print(f"  DYLIGHT Bridge Research Lab — Visual Dashboard Server   ")
    print(f"  Running at: {url}")
    print(f"===========================================================")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard server.")
        httpd.server_close()


if __name__ == "__main__":
    port = 8765
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_server(port)
