"""Khóa contract cài đặt cho các backend nghiên cứu tùy chọn."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OPTIONAL = {"pymoo", "shapely", "sectionproperties", "ifcopenshell"}


def _dependency_names(specs: list[str]) -> set[str]:
    names = set()
    for spec in specs:
        match = re.match(r"[A-Za-z0-9._-]+", spec)
        assert match, f"dependency spec không đọc được: {spec}"
        names.add(match.group(0).lower().replace("_", "-"))
    return names


def test_optional_dependency_groups_and_dev_are_complete():
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    extras = project["optional-dependencies"]

    assert _dependency_names(extras["optimization"]) == {"pymoo"}
    assert _dependency_names(extras["section-fea"]) == {
        "shapely", "sectionproperties"}
    assert _dependency_names(extras["ifc"]) == {"ifcopenshell", "shapely"}
    assert OPTIONAL <= _dependency_names(extras["all"])
    assert OPTIONAL <= _dependency_names(extras["dev"])


def test_bim_package_is_in_wheel_package_manifest():
    with (ROOT / "pyproject.toml").open("rb") as stream:
        config = tomllib.load(stream)
    assert "bridge_evolution.bim" in config["tool"]["setuptools"]["packages"]


def test_audit_lock_pins_direct_optional_backends():
    pins = {}
    for line in (ROOT / "requirements-dev.lock").read_text(encoding="utf-8").splitlines():
        if "==" in line and not line.lstrip().startswith("#"):
            name, version = line.split("==", 1)
            pins[name.lower().replace("_", "-")] = version
    assert {name: pins.get(name) for name in sorted(OPTIONAL)} == {
        "ifcopenshell": "0.8.5",
        "pymoo": "0.6.2",
        "sectionproperties": "3.10.2",
        "shapely": "2.1.2",
    }
