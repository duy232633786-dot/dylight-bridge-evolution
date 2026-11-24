"""Kiểm độc lập các correction 2026-11-24 (dùng cho reviewer).

    python .tmp/lab-review/check_corrections_20261124.py [--diff]

Với mỗi correction: snapshot bytes == hash handoff gốc? live bytes == current_sha256?
In diff (đã bỏ khác biệt CR/LF) nếu có --diff.
"""
import difflib
import glob
import hashlib
import json
import sys

IDS = ["COR-BRD-025-001", "COR-BRD-035-001", "COR-BRD-050-001", "COR-BRD-050-002", "COR-BRD-050-003",
       "COR-BRD-052-001", "COR-BRD-052-002", "COR-BRD-052-003", "COR-BRD-052-004", "COR-BRD-052-005"]


def sha(b):
    return hashlib.sha256(b).hexdigest()


show_diff = "--diff" in sys.argv
for cid in IDS:
    c = json.load(open(f"multiagent/corrections/{cid}.json", encoding="utf-8"))
    art = c["corrected_artifact"]
    h = json.load(open(c["original_handoff_path"], encoding="utf-8"))
    recorded = [a["sha256"] for a in h["artifacts"] if a["path"] == art["path"]][0]
    snap = open(c["snapshot"]["path"], "rb").read()
    live = open(art["path"], "rb").read()
    print(f"== {cid} task={c['task_id']} artifact={art['path']} author={c['agent_id']} handoff_author={h['agent_id']}")
    print(f"   snapshot==handoff_recorded: {sha(snap) == recorded == art['previous_sha256']}")
    print(f"   live==correction_current:  {sha(live) == art['current_sha256']}")
    print(f"   verification_commands: {c['verification_commands']}")
    a = snap.decode("utf-8", "replace").replace("\r\n", "\n").splitlines()
    b = live.decode("utf-8", "replace").replace("\r\n", "\n").splitlines()
    d = list(difflib.unified_diff(a, b, "snapshot", "live", lineterm="", n=1))
    added = sum(1 for x in d if x.startswith("+") and not x.startswith("+++"))
    removed = sum(1 for x in d if x.startswith("-") and not x.startswith("---"))
    print(f"   diff: +{added} -{removed} lines")
    if show_diff:
        print("\n".join(d[:400]))
