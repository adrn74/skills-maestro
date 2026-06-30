#!/usr/bin/env python3
"""Build a searchable index of all installed Cursor agent skills."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from config import INDEX_PATH, load_extra_skill_roots

SKILL_ROOTS: list[tuple[Path, str]] = [
    (Path.home() / ".cursor/skills", "cursor-skills"),
    (Path.home() / ".cursor/skills-cursor", "cursor-tools"),
    (Path.home() / ".agents/skills", "agents"),
] + load_extra_skill_roots()

DESIGN_SLUGS = frozenset(
    {
        "impeccable",
        "ui-ux-pro-max",
        "frontend-design",
        "taste-skill",
        "emilkowalski-skill",
        "claude-council",
    }
)

DEV_SLUGS = frozenset(
    {
        "postgres",
        "performance-engineer",
        "load-testing",
        "scalability-playbook",
        "code-review",
    }
)

CURSOR_SUBCATEGORIES: dict[str, str] = {
    "babysit": "pr-ci",
    "split-to-prs": "pr-ci",
    "review": "review",
    "review-bugbot": "review",
    "review-security": "review",
    "canvas": "canvas",
    "automate": "automation",
    "create-rule": "authoring",
    "create-skill": "authoring",
    "create-hook": "authoring",
    "create-subagent": "authoring",
    "update-cursor-settings": "config",
    "update-cli-config": "config",
    "statusline": "config",
    "loop": "automation",
    "sdk": "sdk",
    "shell": "shell",
    "migrate-to-skills": "authoring",
    "find-skills": "authoring",
}

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
NAME_RE = re.compile(r"^name:\s*['\"]?(.+?)['\"]?\s*$", re.MULTILINE)
DESC_RE = re.compile(
    r"^description:\s*>?-?\s*\n?(.*?)(?=^[a-zA-Z_][\w-]*:|\Z)",
    re.MULTILINE | re.DOTALL,
)
DOMAIN_RE = re.compile(r"^domain:\s*(.+?)\s*$", re.MULTILINE)
SUBDOMAIN_RE = re.compile(r"^subdomain:\s*(.+?)\s*$", re.MULTILINE)
TAGS_RE = re.compile(r"^tags:\s*\n((?:\s*-\s*.+\n)+)", re.MULTILINE)


def parse_frontmatter(text: str) -> dict:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    block = match.group(1)

    name = NAME_RE.search(block)
    desc = DESC_RE.search(block)
    domain = DOMAIN_RE.search(block)
    subdomain = SUBDOMAIN_RE.search(block)
    tags_match = TAGS_RE.search(block)
    tags: list[str] = []
    if tags_match:
        tags = [
            t.strip().strip("'\"")
            for t in re.findall(r"^\s*-\s*(.+?)\s*$", tags_match.group(1), re.MULTILINE)
        ]

    description = ""
    if desc:
        description = re.sub(r"\s+", " ", desc.group(1).strip())

    return {
        "name": name.group(1).strip() if name else "",
        "description": description,
        "domain": domain.group(1).strip() if domain else "",
        "subdomain": subdomain.group(1).strip() if subdomain else "",
        "tags": tags,
    }


def assign_category(slug: str, meta: dict, source: str) -> str:
    if meta.get("domain") == "cybersecurity":
        return "security"
    if slug in DEV_SLUGS:
        return "dev"
    if slug in DESIGN_SLUGS or source == "cursor-skills":
        return "design"
    if source == "cursor-tools":
        return "cursor"
    if source == "agents":
        return "security" if meta.get("domain") else "other"
    return meta.get("domain") or "other"


def assign_subcategory(slug: str, category: str, meta: dict) -> str:
    if category == "security":
        return meta.get("subdomain") or slug.split("-")[0]
    if category == "cursor":
        return CURSOR_SUBCATEGORIES.get(slug, "general")
    if category == "design":
        if slug == "ui-ux-pro-max":
            return "generation"
        if slug == "impeccable":
            return "polish"
        return "frontend"
    if category == "dev":
        if slug == "postgres":
            return "database"
        return "performance"
    return ""


def assign_action(slug: str) -> str:
    verbs = (
        "analyzing",
        "testing",
        "performing",
        "implementing",
        "auditing",
        "building",
        "detecting",
        "exploiting",
        "securing",
        "scanning",
        "hunting",
        "conducting",
        "configuring",
        "triaging",
        "creating",
        "deploying",
    )
    prefix = slug.split("-")[0]
    return prefix if prefix in verbs else ""


def build_category_tree(entries: list[dict]) -> dict:
    tree: dict[str, dict[str, int]] = {}
    for e in entries:
        cat = e["category"]
        sub = e.get("subcategory") or "(general)"
        tree.setdefault(cat, Counter())[sub] += 1
    return {cat: dict(sorted(subs.items(), key=lambda x: (-x[1], x[0]))) for cat, subs in sorted(tree.items())}


def collect_skills() -> list[dict]:
    entries: list[dict] = []
    seen_paths: set[str] = set()

    for root, source in SKILL_ROOTS:
        if not root.is_dir():
            continue
        for skill_md in root.glob("*/SKILL.md"):
            resolved = str(skill_md.resolve())
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)

            try:
                text = skill_md.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                print(f"warn: skip {skill_md}: {exc}", file=sys.stderr)
                continue

            meta = parse_frontmatter(text)
            slug = meta.get("name") or skill_md.parent.name
            category = assign_category(slug, meta, source)
            subcategory = assign_subcategory(slug, category, meta)

            entries.append(
                {
                    "slug": slug,
                    "name": slug,
                    "description": meta.get("description", ""),
                    "domain": meta.get("domain", ""),
                    "subdomain": meta.get("subdomain", ""),
                    "tags": meta.get("tags", []),
                    "category": category,
                    "subcategory": subcategory,
                    "action": assign_action(slug),
                    "path": resolved,
                    "source": source,
                }
            )

    entries.sort(key=lambda e: e["slug"])
    return entries


def main() -> int:
    out_dir = INDEX_PATH.parent
    entries = collect_skills()
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(entries),
        "categories": build_category_tree(entries),
        "skills": entries,
    }
    out_path = out_dir / "skills-index.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Indexed {len(entries)} skills → {out_path}")
    for cat, subs in payload["categories"].items():
        print(f"  {cat}: {sum(subs.values())} skills, {len(subs)} subcategories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
