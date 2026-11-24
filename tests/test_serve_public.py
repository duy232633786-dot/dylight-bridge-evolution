"""Lớp phòng thủ của bản web công khai (scripts/serve_public.py)."""
from __future__ import annotations

import http.client
import importlib
import json
import sys
import threading
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture(scope="module")
def server():
    sys.path.insert(0, str(SCRIPTS))
    pub = importlib.import_module("serve_public")
    httpd = pub.PublicServer(("127.0.0.1", 0), pub.PublicLabHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield pub, httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def _req(port, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    conn.request(method, path, body=body, headers=headers or {})
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp, data


def test_security_headers_and_static_page(server):
    _, port = server
    resp, _ = _req(port, "GET", "/lab.html")
    assert resp.status == 200
    csp = resp.getheader("Content-Security-Policy")
    assert "script-src 'self'" in csp and "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]
    assert "object-src 'none'" in csp
    assert resp.getheader("X-Content-Type-Options") == "nosniff"


def test_no_directory_listing_or_traversal(server):
    _, port = server
    assert _req(port, "GET", "/vendor/")[0].status == 404
    assert _req(port, "GET", "/../pyproject.toml")[0].status == 404
    assert _req(port, "GET", "/api/design-loop/runs/..%2f..%2fpyproject.toml")[0].status == 404


def test_runs_are_not_persisted_or_listed(server):
    pub, port = server
    body = json.dumps({"seed_file": "GC-01_standard_pass.json", "budget": 10})
    resp, data = _req(port, "POST", "/api/design-loop", body)
    assert resp.status == 200
    assert json.loads(data)["saved_as"] is None
    assert not any(pub._RUNS_DIR.iterdir())
    resp, data = _req(port, "GET", "/api/design-loop/runs")
    assert json.loads(data) == {"dir": None, "runs": []}


def test_limits(server):
    pub, port = server
    resp, _ = _req(port, "POST", "/api/evaluate", b"a" * (pub.MAX_BODY_BYTES + 1))
    assert resp.status == 413
    body = json.dumps({"seed_file": "GC-01_standard_pass.json", "budget": 400})
    resp, data = _req(port, "POST", "/api/design-loop", body)
    assert resp.status == 400
    assert _req(port, "PUT", "/api/evaluate")[0].status == 405


def test_rate_limit_per_ip(server):
    pub, _ = server
    ip = "203.0.113.9"
    results = [pub._rate_ok(ip, now=1000.0) for _ in range(pub.RATE_PER_MIN + 1)]
    assert results[:-1] == [True] * pub.RATE_PER_MIN and results[-1] is False
    assert pub._rate_ok(ip, now=1061.0) is True
