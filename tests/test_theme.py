"""Cấu hình màu Obsidian: merge an toàn, idempotent và chống ghi đè."""
from __future__ import annotations

import json

from bridge_evolution.cli import main as cli_main
from bridge_evolution.knowledge.theme import (
    DYLIGHT_COLOR_GROUPS,
    SNIPPET_FILE,
    SNIPPET_NAME,
    configure_obsidian_colors,
)


def _vault(tmp_path):
    vault = tmp_path / "vault"
    config = vault / ".obsidian"
    config.mkdir(parents=True)
    return vault, config


def test_theme_preserves_user_settings_and_adds_dylight_groups(tmp_path):
    vault, config = _vault(tmp_path)
    (config / "appearance.json").write_text(json.dumps({
        "theme": "obsidian", "enabledCssSnippets": ["mine"],
    }), encoding="utf-8")
    user_group = {"query": "tag:#mine", "color": {"a": 1, "rgb": 123}}
    (config / "graph.json").write_text(json.dumps({
        "showTags": False, "lineSizeMultiplier": 2.5,
        "colorGroups": [user_group],
    }), encoding="utf-8")

    result = configure_obsidian_colors(vault)

    appearance = json.loads((config / "appearance.json").read_text(encoding="utf-8"))
    graph = json.loads((config / "graph.json").read_text(encoding="utf-8"))
    assert result["conflicts"] == []
    assert set(result["written"]) == {
        "appearance.json", "graph.json", f"snippets/{SNIPPET_FILE}"}
    assert appearance["theme"] == "obsidian"
    assert appearance["enabledCssSnippets"] == ["mine", SNIPPET_NAME]
    assert graph["lineSizeMultiplier"] == 2.5
    assert graph["showTags"] is True
    assert graph["showAttachments"] is True
    assert graph["showOrphans"] is False
    assert graph["colorGroups"][:len(DYLIGHT_COLOR_GROUPS)] == DYLIGHT_COLOR_GROUPS
    assert graph["colorGroups"][-1] == user_group
    assert (config / "snippets" / SNIPPET_FILE).is_file()


def test_theme_is_idempotent(tmp_path):
    vault, _ = _vault(tmp_path)
    configure_obsidian_colors(vault)

    second = configure_obsidian_colors(vault)

    assert second["written"] == []
    assert len(second["unchanged"]) == 3
    assert second["manifest_changed"] is False
    assert second["conflicts"] == []


def test_theme_accepts_obsidian_json_reformatting(tmp_path):
    vault, config = _vault(tmp_path)
    configure_obsidian_colors(vault)
    for name in ("appearance.json", "graph.json"):
        path = config / name
        obj = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8")

    result = configure_obsidian_colors(vault, dry_run=True)

    assert result["planned_writes"] == []
    assert set(result["unchanged"]) == {
        "appearance.json", "graph.json", f"snippets/{SNIPPET_FILE}"}


def test_user_edited_css_is_a_conflict_and_blocks_all_writes(tmp_path):
    vault, config = _vault(tmp_path)
    configure_obsidian_colors(vault)
    snippet = config / "snippets" / SNIPPET_FILE
    edited = snippet.read_text(encoding="utf-8") + "\n/* user edit */\n"
    snippet.write_text(edited, encoding="utf-8")
    (config / "graph.json").write_text("{}", encoding="utf-8")

    result = configure_obsidian_colors(vault)

    assert result["conflicts"] == [f"snippets/{SNIPPET_FILE}"]
    assert result["written"] == []
    assert snippet.read_text(encoding="utf-8") == edited
    assert (config / "graph.json").read_text(encoding="utf-8") == "{}"


def test_theme_dry_run_creates_nothing(tmp_path):
    vault, config = _vault(tmp_path)

    result = configure_obsidian_colors(vault, dry_run=True)

    assert len(result["planned_writes"]) == 3
    assert result["written"] == []
    assert not (config / "snippets").exists()


def test_cli_theme(tmp_path, capsys):
    vault, _ = _vault(tmp_path)

    exit_code = cli_main(["knowledge-theme", "--vault", str(vault)])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["status"] == "SUCCESS"
    assert output["color_groups"] == len(DYLIGHT_COLOR_GROUPS)
