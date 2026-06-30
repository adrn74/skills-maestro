"""Shared paths for Skills Maestro."""

from __future__ import annotations

import json
import os
from pathlib import Path

MAESTRO_HOME = Path(
    os.environ.get("SKILLS_MAESTRO_HOME", Path.home() / ".cursor" / "skills-maestro")
)
CONFIG_DIR = MAESTRO_HOME / "config"
INDEX_PATH = MAESTRO_HOME / "skills-index.json"
PROJECT_CONTEXT_PATH = CONFIG_DIR / "project-context.json"
SKILL_ROOTS_PATH = CONFIG_DIR / "skill-roots.json"


def load_project_context_queries() -> list[str]:
    if not PROJECT_CONTEXT_PATH.is_file():
        return []
    try:
        data = json.loads(PROJECT_CONTEXT_PATH.read_text(encoding="utf-8"))
        return list(data.get("context_queries", []))
    except (json.JSONDecodeError, OSError):
        return []


def load_extra_skill_roots() -> list[tuple[Path, str]]:
    if not SKILL_ROOTS_PATH.is_file():
        return []
    try:
        data = json.loads(SKILL_ROOTS_PATH.read_text(encoding="utf-8"))
        roots = []
        for entry in data.get("roots", []):
            path = Path(entry["path"]).expanduser()
            label = entry.get("label", path.name)
            roots.append((path, label))
        return roots
    except (json.JSONDecodeError, OSError, KeyError):
        return []
