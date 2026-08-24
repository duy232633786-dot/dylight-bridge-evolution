"""Kiểm: mọi artifact ĐÃ HASH trong handoff có tái dựng được bytes gốc không?

Bài học đã trả giá
------------------
Handoff `BRD-009.claude.r001.json` hash
``experiments/results/grammar_ab_20260821T061537.020446Z/summary.md``. File đó
nằm dưới một thư mục bị `.gitignore` loại trừ, nên khi cần tái dựng đúng bytes
đã ký thì **không tái dựng được**. Chuỗi kiểm toán đứt ở chỗ không ai nhìn thấy.

Quy tắc rút ra: **không hash artifact chưa được version-control.**

Bộ kiểm này biến quy tắc đó thành một con số đo được, và dùng cơ chế BÁNH CÓC:
số artifact không tái dựng được chỉ được phép GIẢM. Sửa xong một artifact thì
phải hạ ``BASELINE_UNRECOVERABLE``; quên hạ cũng báo đỏ, nên baseline không mục
ruỗng theo thời gian.

Ba nguồn tái dựng được chấp nhận, theo thứ tự:
  1. ``git show HEAD:<path>`` cho ra đúng SHA-256 đã ký;
  2. ``multiagent/snapshots/sha256/<sha>.blob`` chứa đúng bytes (cơ chế snapshot
     của MARP-1.0 dành cho vòng REVISE và correct-provenance);
  3. không có nguồn nào ⇒ artifact KHÔNG tái dựng được.

Chạy
----
    PYTHONIOENCODING=utf-8 python docs/check_handoff_provenance.py
    python docs/check_handoff_provenance.py --report   # chỉ in, luôn thoát 0
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HANDOFFS = REPO_ROOT / "multiagent" / "handoffs"
SNAPSHOTS = REPO_ROOT / "multiagent" / "snapshots" / "sha256"

#: Số artifact đã hash mà HÔM NAY chưa tái dựng được bytes gốc.
#: Đo ngày 2026-08-21 trong BRD-001: 12/15 artifact của 11 handoff
#: (3 artifact còn lại cứu được nhờ snapshot content-addressed của MARP-1.0;
#: 0/15 tái dựng được từ HEAD).
#: CHỈ ĐƯỢC GIẢM. Xem docs/baseline_version_control_plan.md §5 cho thứ tự dọn.
BASELINE_UNRECOVERABLE = 12

#: Số artifact đã hash mà working tree còn CRLF, trong khi `.gitattributes` ép
#: `eol=lf` — bytes commit sẽ KHÁC bytes đã ký. Đo ngày 2026-08-21: 4 file, tất
#: cả đều nằm ngoài write_scope của BRD-001 (`tests/`, `experiments/results/`).
#: CHỈ ĐƯỢC GIẢM, cùng cơ chế bánh cóc với BASELINE_UNRECOVERABLE.
BASELINE_CRLF = 4


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True)


def collect_hashed_artifacts() -> dict[str, dict]:
    """{path: {"shas": set, "handoffs": set}} — gom mọi artifact đã ký hash."""
    items: dict[str, dict] = {}
    if not HANDOFFS.is_dir():
        return items
    for path in sorted(HANDOFFS.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            handoff = json.load(f)
        for art in handoff.get("artifacts", []):
            entry = items.setdefault(art["path"], {"shas": set(), "handoffs": set()})
            entry["shas"].add(art["sha256"])
            entry["handoffs"].add(path.name)
    return items


def classify(rel_path: str, shas: set[str]) -> dict:
    """Trạng thái tái dựng của một artifact đã hash."""
    abs_path = REPO_ROOT / rel_path
    live = _sha256_bytes(abs_path.read_bytes()) if abs_path.is_file() else None
    head_proc = _git("show", f"HEAD:{rel_path}")
    head = _sha256_bytes(head_proc.stdout) if head_proc.returncode == 0 else None
    snapshot = any((SNAPSHOTS / f"{s}.blob").is_file()
                   and _sha256_bytes((SNAPSHOTS / f"{s}.blob").read_bytes()) == s
                   for s in shas)
    ignored = _git("check-ignore", "-q", rel_path).returncode == 0
    # .gitattributes ép `eol=lf`. File working-tree còn CRLF thì bytes commit sẽ
    # KHÁC bytes vừa ký — cùng một lớp lỗi provenance, chỉ ẩn hơn.
    crlf = abs_path.is_file() and b"\r\n" in abs_path.read_bytes()

    if head is not None and head in shas:
        source = "HEAD"
    elif snapshot:
        source = "SNAPSHOT"
    else:
        source = None
    return {
        "path": rel_path,
        "live_matches": live in shas if live is not None else False,
        "exists": abs_path.is_file(),
        "in_head": head is not None,
        "head_matches": head is not None and head in shas,
        "snapshot": snapshot,
        "gitignored": ignored,
        "crlf": crlf,
        "source": source,
    }


def run_report() -> tuple[list[dict], list[dict]]:
    """(toàn bộ, nhóm không tái dựng được)."""
    rows = [classify(p, meta["shas"]) for p, meta in sorted(collect_hashed_artifacts().items())]
    return rows, [r for r in rows if r["source"] is None]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true",
                        help="chi in bao cao, luon thoat 0")
    args = parser.parse_args()

    rows, unrecoverable = run_report()
    crlf_rows = [r for r in rows if r["crlf"]]
    print(f"Artifact da hash trong handoff: {len(rows)}")
    print(f"  tai dung duoc tu HEAD     : {sum(1 for r in rows if r['source'] == 'HEAD')}")
    print(f"  tai dung duoc tu SNAPSHOT : {sum(1 for r in rows if r['source'] == 'SNAPSHOT')}")
    print(f"  KHONG tai dung duoc       : {len(unrecoverable)} (baseline {BASELINE_UNRECOVERABLE})")
    for r in unrecoverable:
        flags = []
        if r["gitignored"]:
            flags.append("BI GITIGNORE")
        if not r["exists"]:
            flags.append("MAT FILE")
        elif not r["live_matches"]:
            flags.append("BYTES LIVE DA DOI")
        if not r["in_head"]:
            flags.append("CHUA COMMIT")
        elif not r["head_matches"]:
            flags.append("HEAD KHAC BYTES DA KY")
        if not r["snapshot"]:
            flags.append("KHONG CO SNAPSHOT")
        print(f"    - {r['path']}  [{', '.join(flags) or 'khong ro'}]")

    print(f"  CRLF trong working tree (.gitattributes ep eol=lf): "
          f"{len(crlf_rows)} (baseline {BASELINE_CRLF})")
    for r in crlf_rows:
        print(f"    - {r['path']}")

    if args.report:
        return 0

    failed = False
    for actual, baseline, name, why in (
        (len(unrecoverable), BASELINE_UNRECOVERABLE, "BASELINE_UNRECOVERABLE",
         "khong duoc hash artifact chua duoc version-control"),
        (len(crlf_rows), BASELINE_CRLF, "BASELINE_CRLF",
         "artifact da ky con CRLF thi bytes commit se KHAC bytes da ky"),
    ):
        if actual > baseline:
            print(f"\nLECH: {name} TANG ({actual} > {baseline}) — {why}.")
            failed = True
        elif actual < baseline:
            print(f"\nLECH: da cai thien ({actual} < {baseline}) nhung {name} chua "
                  f"duoc ha. Ha xuong {actual} de banh coc khong quay lai.")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
