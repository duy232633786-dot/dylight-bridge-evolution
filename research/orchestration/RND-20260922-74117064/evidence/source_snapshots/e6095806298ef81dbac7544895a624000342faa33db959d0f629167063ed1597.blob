"""DYLIGHT Bridge Evolution — tối ưu sơ bộ cầu Super-T giản đơn.

Contract trung tâm: ``evaluate_candidate(design_state) -> EvaluationResult``.
Các catalog/schema được tìm từ source checkout khi phát triển và từ package
resources khi cài wheel. Thư mục artifact có thể cấu hình bằng biến môi trường
``DYLIGHT_ARTIFACTS_DIR`` để không ghi vào ``site-packages``.
"""
from importlib.resources import files
import os
from pathlib import Path

__version__ = "0.8.0"

REPO_ROOT = Path(__file__).resolve().parent.parent
_SOURCE_LAYOUT = (REPO_ROOT / "contracts").is_dir()

if _SOURCE_LAYOUT:
    CONTRACTS_DIR = REPO_ROOT / "contracts"
    CATALOGS_DIR = REPO_ROOT / "catalogs"
    GRAMMAR_DIR = REPO_ROOT / "bridge_grammar"
    KNOWLEDGE_CARDS_DIR = REPO_ROOT / "knowledge" / "cards"
    KNOWLEDGE_AUDITS_DIR = REPO_ROOT / "knowledge" / "audits"
    _default_artifacts = REPO_ROOT / "artifacts"
else:  # wheel/install layout — các package dữ liệu được ánh xạ trong pyproject.toml
    CONTRACTS_DIR = Path(str(files("dylight_contracts")))
    CATALOGS_DIR = Path(str(files("dylight_catalogs")))
    GRAMMAR_DIR = Path(str(files("dylight_grammar")))
    KNOWLEDGE_CARDS_DIR = Path(str(files("dylight_knowledge_cards")))
    KNOWLEDGE_AUDITS_DIR = Path(str(files("dylight_knowledge_audits")))
    _default_artifacts = Path.cwd() / "artifacts"

ARTIFACTS_DIR = Path(os.environ.get("DYLIGHT_ARTIFACTS_DIR", _default_artifacts)).resolve()
