#!/usr/bin/env python3
"""DYLIGHT Lab — chế độ CÔNG KHAI (đưa lên Internet).

Bọc ``serve_lab.py`` (không sửa file đó) và thêm các lớp phòng thủ cần khi
máy chủ không còn chỉ nghe trên 127.0.0.1:

* Không ghi file nào của người dùng ra đĩa và không cho xem run của người khác
  (tránh đầy đĩa và tránh dữ liệu người này hiện ra trên trình duyệt người kia).
* Giới hạn kích thước body, số phép tính chạy đồng thời và số yêu cầu mỗi IP.
* Hạ trần ngân sách/vòng lặp so với bản cục bộ.
* Ẩn đường dẫn máy chủ và nội dung lỗi nội bộ.
* Tắt liệt kê thư mục; chỉ phục vụ file tĩnh của ``dashboard/``.
* Header bảo mật: CSP chặt, nosniff, Referrer-Policy, Permissions-Policy.

Chạy::

    HOST=0.0.0.0 PORT=7860 python scripts/serve_public.py

Biến môi trường (đều tùy chọn):
    HOST, PORT                    địa chỉ nghe (mặc định 0.0.0.0:7860)
    DYLIGHT_MAX_CONCURRENT        số phép tính chạy cùng lúc (mặc định 2)
    DYLIGHT_RATE_PER_MIN          số POST mỗi IP mỗi phút (mặc định 20)
    DYLIGHT_TRUST_PROXY           "1" nếu đứng sau proxy tin cậy gắn X-Forwarded-For
    DYLIGHT_FRAME_ANCESTORS       nguồn được phép nhúng trang bằng iframe
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import sys
import tempfile
import threading
import time
from collections import deque
from http.server import ThreadingHTTPServer
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Thư mục artifact ghi được phải được chọn TRƯỚC khi import package.
os.environ.setdefault("DYLIGHT_ARTIFACTS_DIR", str(Path(tempfile.gettempdir()) / "dylight-public"))

import serve_lab as lab  # noqa: E402

MAX_BODY_BYTES = 64 * 1024
MAX_CONCURRENT = max(1, int(os.environ.get("DYLIGHT_MAX_CONCURRENT", "2")))
RATE_PER_MIN = max(1, int(os.environ.get("DYLIGHT_RATE_PER_MIN", "20")))
TRUST_PROXY = os.environ.get("DYLIGHT_TRUST_PROXY", "0") == "1"
FRAME_ANCESTORS = os.environ.get(
    "DYLIGHT_FRAME_ANCESTORS", "'self' https://huggingface.co https://*.hf.space"
)
REQUEST_TIMEOUT_S = 20

# Trần thấp hơn bản cục bộ (400): đủ cho thử nghiệm, không cho một yêu cầu chiếm CPU lâu.
lab.MAX_BUDGET = 150
lab.MAX_CREATIVE_ITERATIONS = 150

def _inline_script_hashes(dashboard: Path) -> list[str]:
    """SHA-256 của từng <script> nhúng sẵn trong dashboard/*.html (tính lúc khởi động).

    Chỉ đúng các script có sẵn trong repo được chạy; script do kẻ tấn công chèn
    vào trang (XSS) có hash khác nên vẫn bị CSP chặn.
    """
    pattern = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S | re.I)
    hashes: set[str] = set()
    for page in sorted(dashboard.glob("*.html")):
        text = page.read_bytes().decode("utf-8", errors="replace")  # giữ nguyên CRLF như trình duyệt nhận
        for body in pattern.findall(text):
            digest = hashlib.sha256(body.encode("utf-8")).digest()
            hashes.add("'sha256-" + base64.b64encode(digest).decode("ascii") + "'")
    return sorted(hashes)


# three.js của trình xem 3D tải từ cdnjs: chỉ cho đúng đường dẫn thư viện đó.
_SCRIPT_SRC = " ".join(["'self'", "https://cdnjs.cloudflare.com/ajax/libs/three.js/",
                        *_inline_script_hashes(lab.DASHBOARD_DIR)])

CSP = "; ".join([
    "default-src 'self'",
    f"script-src {_SCRIPT_SRC}",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-src 'self'",
    f"frame-ancestors {FRAME_ANCESTORS}",
])
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


# ------------------------------------------------------------------ route công khai
_ORIGINAL_DESIGN_LOOP = lab.POST_ROUTES["/api/design-loop"]
_RUNS_DIR = Path(tempfile.mkdtemp(prefix="dylight-runs-"))
lab.LAB_RUNS_DIR = _RUNS_DIR


def _design_loop_no_persist(payload: dict) -> dict:
    """Chạy vòng lặp thiết kế nhưng KHÔNG giữ file trên đĩa của máy chủ."""
    out = _ORIGINAL_DESIGN_LOOP(payload)
    name = out.get("saved_as")
    if isinstance(name, str):
        target = (_RUNS_DIR / name).resolve()
        if target.parent == _RUNS_DIR.resolve():
            target.unlink(missing_ok=True)
    out["saved_as"] = None
    out["note"] = "Bản web công khai không lưu run trên máy chủ; hãy tải report về nếu cần."
    return out


# Gán MỘT LẦN lúc khởi động (sửa tại chỗ), không tráo theo từng yêu cầu → không đua luồng.
lab.GET_ROUTES["/api/design-loop/runs"] = lambda params: {"dir": None, "runs": []}
lab.GET_ROUTES["/api/obsidian"] = lambda params: {
    "available": False, "message": "Không có trên bản web công khai."}
lab.POST_ROUTES["/api/design-loop"] = _design_loop_no_persist

_compute_slots = threading.BoundedSemaphore(MAX_CONCURRENT)
_rate_lock = threading.Lock()
_rate_hits: dict[str, deque] = {}


def _rate_ok(ip: str, now: float | None = None) -> bool:
    now = time.monotonic() if now is None else now
    with _rate_lock:
        hits = _rate_hits.setdefault(ip, deque())
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= RATE_PER_MIN:
            return False
        hits.append(now)
        if len(_rate_hits) > 10_000:  # không để bảng IP phình vô hạn
            for key in [k for k, v in _rate_hits.items() if not v][:5_000]:
                del _rate_hits[key]
        return True


class PublicLabHandler(lab.LabHandler):
    timeout = REQUEST_TIMEOUT_S          # chặn kết nối treo (slowloris)
    server_version = "DYLIGHT-Lab"
    sys_version = ""

    def _client_ip(self) -> str:
        if TRUST_PROXY:
            fwd = self.headers.get("X-Forwarded-For", "")
            if fwd:
                # Lấy mục CUỐI: do proxy gần nhất (tin cậy) ghi vào. Mục đầu do
                # máy khách tự gửi nên giả được, không dùng để giới hạn.
                return fwd.split(",")[-1].strip() or self.client_address[0]
        return self.client_address[0]

    def _json(self, status: int, payload) -> None:
        if status == 500:  # chỉ ẩn lỗi nội bộ; 503 "đang bận" giữ nguyên thông báo
            payload = {"error": "Lỗi nội bộ máy chủ."}
        super()._json(status, payload)

    def list_directory(self, path):  # không liệt kê thư mục
        self.send_error(404)
        return None

    def end_headers(self):
        for key, value in SECURITY_HEADERS.items():
            self.send_header(key, value)
        super().end_headers()

    def do_POST(self):  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY_BYTES:
            self._json(413, {"error": f"Body quá lớn (tối đa {MAX_BODY_BYTES // 1024} KB)."})
            self.close_connection = True
            return
        if not _rate_ok(self._client_ip()):
            self._json(429, {"error": "Quá nhiều yêu cầu, thử lại sau một phút."})
            return
        if not _compute_slots.acquire(blocking=False):
            self._json(503, {"error": "Máy chủ đang bận, thử lại sau vài giây."})
            return
        try:
            super().do_POST()
        finally:
            _compute_slots.release()

    def do_PUT(self):  # noqa: N802
        self._json(405, {"error": "Phương thức không được hỗ trợ."})

    do_DELETE = do_PATCH = do_OPTIONS = do_PUT


class PublicServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 64


def run_public(host: str, port: int) -> None:
    httpd = PublicServer((host, port), PublicLabHandler)
    print(f"DYLIGHT Lab (công khai) — http://{host}:{port}/lab.html", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


if __name__ == "__main__":
    run_public(os.environ.get("HOST", "0.0.0.0"), int(os.environ.get("PORT", "7860")))
