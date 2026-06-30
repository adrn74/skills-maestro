#!/usr/bin/env python3
"""Resolve relevant skills with tiered output: essential (full read) vs context (metadata only)."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

from config import INDEX_PATH, MAESTRO_HOME, load_extra_skill_roots

_ROUTER_DIR = Path(__file__).resolve().parent


def _load_expand_intent():
    spec = importlib.util.spec_from_file_location(
        "expand_intent", _ROUTER_DIR / "expand-intent.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_expand = _load_expand_intent()
expand_intent = _expand.expand_intent
is_vague_query = _expand.is_vague_query

ESSENTIAL_MAX = 8
CONTEXT_MAX = 5

STOPWORDS = frozenset(
    """
    a an the and or but in on at to for of is are was were be been being
    with from by as it this that these those i you we they he she my your our
    their me him her us them do does did done have has had will would could
    should can may might must not no yes all any some each every both few
    more most other such than then so if when where how what which who whom
    why while also just only very too into over under about up down out off
    via per use using used make made get got set let run add new old
    """.split()
)

# French → English expansions for matching (query side only)
TOKEN_ALIASES: dict[str, list[str]] = {
    "trafic": ["traffic"],
    "analyser": ["analyzing", "analyze", "analysis"],
    "analyse": ["analyzing", "analyze", "analysis"],
    "securite": ["security"],
    "sécurité": ["security"],
    "incident": ["incidents"],
    "paquet": ["packet", "packets"],
    "paquets": ["packet", "packets"],
    "reseau": ["network"],
    "réseau": ["network"],
    "optimiser": ["optimization", "optimize"],
    "requete": ["query"],
    "requêtes": ["query", "queries"],
    "application": ["applications"],
    "mobile": ["mobile"],
    "generer": ["generate", "generation"],
    "génère": ["generate", "generation"],
    "genere": ["generate", "generation"],
}

CATEGORY_SIGNALS: dict[str, list[str]] = {
    "design": [
        "ui", "ux", "design", "interface", "dashboard", "landing", "polish",
        "écran", "page", "composant", "typography", "palette", "a11y", "mobile screen",
    ],
    "cursor": [
        "cursor", "rule", "hook", "babysit", "pull request", "bugbot",
        "canvas", "automation", "subagent", "statusline",
    ],
    "dev": [
        "postgres", "postgresql", "sql", "database", "performance", "load test",
        "scalability", "query optimization",
    ],
    "security": [
        "security", "sécurité", "audit", "pentest", "vuln", "forensic", "malware",
        "xss", "sqli", "owasp", "ioc", "ransomware", "siem", "threat",
        "hardening", "compliance", "kubernetes security", "cloud security",
    ],
}

SUBCATEGORY_SIGNALS: dict[str, list[str]] = {
    "network-security": ["wireshark", "packet", "network", "netflow", "dns", "tls", "firewall", "trafic"],
    "web-application-security": ["xss", "sqli", "web app", "web application", "owasp", "csrf"],
    "penetration-testing": ["pentest", "penetration", "exploit", "burp"],
    "digital-forensics": ["forensic", "forensics", "artifact", "volatility", "autopsy", "memory dump"],
    "malware-analysis": ["malware", "sandbox", "cuckoo", "ghidra", "reverse engineering"],
    "incident-response": ["incident response", " ir ", "triage", "playbook", "incident"],
    "cloud-security": ["aws", "azure", "gcp", "s3", "iam", "cloud"],
    "api-security": ["api security", "graphql", "rest api", "jwt", "oauth"],
    "identity-access-management": ["active directory", "entra", "ldap", "kerberos"],
    "container-security": ["kubernetes", "k8s", "docker", "container", "helm"],
    "threat-hunting": ["hunt", "hunting", "yara", "sigma"],
    "threat-intelligence": ["threat intel", "misp", "stix", "taxii", "ioc"],
    "database": ["postgres", "postgresql", "sql"],
    "pr-ci": ["babysit", "merge", "bugbot"],
    "polish": ["polish", "audit ui", "critique", "refine"],
    "generation": ["generate", "génère", "palette", "style", "recommend"],
}

VULN_TOKENS = frozenset(
    {"xss", "sqli", "csrf", "ssrf", "xxe", "jwt", "idor", "rce", "lfi", "ssti", "xpath"}
)

GENERIC_SLUG_TOKENS = frozenset(
    {"analyzing", "testing", "performing", "implementing", "auditing", "audit", "security", "api", "network"}
)

DOMAIN_BOOSTS = {
    "ui": ["impeccable", "ui-ux-pro-max", "frontend-design", "canvas"],
    "security": ["review-security", "code-review"],
    "pr": ["babysit", "split-to-prs", "review-bugbot", "review"],
    "data": ["postgres", "canvas"],
}


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9][a-z0-9_-]{1,}", text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def expand_query_tokens(tokens: list[str]) -> list[str]:
    expanded = list(tokens)
    for t in tokens:
        for alias in TOKEN_ALIASES.get(t, []):
            if alias not in expanded:
                expanded.append(alias)
    return expanded


def load_index() -> tuple[list[dict], dict]:
    if not INDEX_PATH.is_file():
        print(
            f"Index missing. Run: python3 {MAESTRO_HOME / 'build-index.py'}",
            file=sys.stderr,
        )
        sys.exit(2)
    data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return data["skills"], data.get("categories", {})


def _signal_in_query(signal: str, query: str) -> bool:
    signal = signal.lower()
    q = query.lower()
    if len(signal) <= 3:
        return re.search(rf"\b{re.escape(signal)}\b", q) is not None
    return signal in q


def detect_categories(query: str) -> list[str]:
    return [
        cat
        for cat, signals in CATEGORY_SIGNALS.items()
        if any(_signal_in_query(sig, query) for sig in signals)
    ]


def detect_subcategories(query: str) -> list[str]:
    return [
        sub
        for sub, signals in SUBCATEGORY_SIGNALS.items()
        if any(_signal_in_query(sig, query) for sig in signals)
    ]


def slug_token_hits(slug: str, query_tokens: list[str], *, specific_only: bool = False) -> int:
    parts = slug.lower().split("-")
    flat = slug.lower().replace("-", " ")
    hits = 0
    for token in query_tokens:
        if specific_only and token in GENERIC_SLUG_TOKENS:
            continue
        if token in parts or token in flat:
            hits += 1
    return hits


def vuln_slug_matches(slug: str, query_tokens: list[str]) -> bool:
    vulns = [t for t in query_tokens if t in VULN_TOKENS]
    if not vulns:
        return False
    flat = slug.lower().replace("-", " ")
    return any(v in flat for v in vulns)


def score_skill(
    skill: dict,
    query_tokens: list[str],
    query_raw: str,
    categories: list[str],
    subcategories: list[str],
) -> float:
    slug = skill["slug"].lower()
    desc = skill.get("description", "").lower()
    tags = " ".join(skill.get("tags", [])).lower()
    subcategory = skill.get("subcategory", "").lower()
    category = skill.get("category", "")
    haystack = f"{slug} {desc} {tags} {subcategory}"
    hay_tokens = set(tokenize(haystack))
    slug_hits = slug_token_hits(slug, query_tokens)

    score = 0.0

    # Strong slug alignment = highest precision signal
    score += slug_hits * 14.0

    if categories:
        if category in categories:
            score += 8.0
        elif len(categories) == 1:
            score -= 8.0

    if subcategories and subcategory in subcategories:
        score += 16.0
    elif subcategories:
        for sub in subcategories:
            overlap = sum(1 for p in sub.split("-") if len(p) >= 4 and p in haystack)
            score += overlap * 3.0

    for token in query_tokens:
        if token in hay_tokens:
            score += 3.0
        elif token in desc:
            score += 1.5

    q = query_raw.lower()
    if any(k in q for k in ("ui", "ux", "design", "interface", "écran", "page", "dashboard")):
        if slug in DOMAIN_BOOSTS["ui"]:
            score += 15.0
    if any(k in q for k in ("security", "audit", "vuln", "pentest", "forensic", "malware", "xss", "sqli")):
        if slug in DOMAIN_BOOSTS["security"]:
            score += 12.0
    if any(k in q for k in ("pull request", "merge", "bugbot", "babysit")) or re.search(r"\bpr\b", q):
        if slug in DOMAIN_BOOSTS["pr"]:
            score += 12.0
    if "postgres" in q or "postgresql" in q:
        if slug == "postgres":
            score += 20.0

    return score


def assign_tiers(
    scored: list[tuple[float, dict]],
    query_tokens: list[str],
    subcategories: list[str],
    essential_max: int = ESSENTIAL_MAX,
    context_max: int = CONTEXT_MAX,
) -> tuple[list[dict], list[dict]]:
    if not scored:
        return [], []

    top = scored[0][0]
    essential_floor = max(top * 0.55, top - 20.0, 8.0)
    context_floor = max(top * 0.40, 6.0)

    def make_entry(score: float, skill: dict, tier: str) -> dict:
        return {
            "slug": skill["slug"],
            "score": round(score, 1),
            "category": skill.get("category", ""),
            "subcategory": skill.get("subcategory", ""),
            "description": skill.get("description", ""),
            "path": skill["path"],
            "slug_hits": slug_token_hits(skill["slug"], query_tokens),
            "tier": tier,
        }

    essential: list[dict] = []
    essential_paths: set[str] = set()
    candidates: list[tuple[float, dict, int, bool]] = []

    for score, skill in scored:
        slug_hits = slug_token_hits(skill["slug"], query_tokens)
        sub_match = bool(subcategories and skill.get("subcategory") in subcategories)
        candidates.append((score, skill, slug_hits, sub_match))

    by_precision = sorted(
        candidates,
        key=lambda x: (-int(vuln_slug_matches(x[1]["slug"], query_tokens)), -x[2], -x[0]),
    )

    # Pass 0: vulnerability-specific slug match (xss, sqli, …)
    for score, skill, slug_hits, sub_match in by_precision:
        if len(essential) >= essential_max:
            break
        if vuln_slug_matches(skill["slug"], query_tokens) and score >= 8.0:
            essential.append(make_entry(score, skill, "essential"))
            essential_paths.add(skill["path"])

    # Pass 1: direct slug match in relevant subcategory (tool-level precision)
    for score, skill, slug_hits, sub_match in by_precision:
        if len(essential) >= essential_max:
            break
        if skill["path"] in essential_paths:
            continue
        specific_hits = slug_token_hits(skill["slug"], query_tokens, specific_only=True)
        if (specific_hits >= 1 or slug_hits >= 2) and sub_match and score >= max(top * 0.50, 12.0):
            essential.append(make_entry(score, skill, "essential"))
            essential_paths.add(skill["path"])

    # Pass 2: strong score + multiple slug hits or near-top
    for score, skill, slug_hits, sub_match in candidates:
        if len(essential) >= essential_max:
            break
        if skill["path"] in essential_paths:
            continue
        if score >= essential_floor and (slug_hits >= 2 or score >= top * 0.85):
            essential.append(make_entry(score, skill, "essential"))
            essential_paths.add(skill["path"])

    # Pass 3: fill remaining essential slots by score within floor
    for score, skill, slug_hits, sub_match in candidates:
        if len(essential) >= essential_max:
            break
        if skill["path"] in essential_paths:
            continue
        if score >= essential_floor and (slug_hits >= 1 or sub_match):
            essential.append(make_entry(score, skill, "essential"))
            essential_paths.add(skill["path"])

    context: list[dict] = []
    for score, skill, slug_hits, sub_match in candidates:
        if len(context) >= context_max:
            break
        if skill["path"] in essential_paths:
            continue
        if score >= context_floor and (slug_hits >= 1 or sub_match or score >= top * 0.50):
            context.append(make_entry(score, skill, "context"))

    return essential, context


def resolve(
    query: str,
    category: str | None = None,
    essential_max: int = ESSENTIAL_MAX,
    context_max: int = CONTEXT_MAX,
) -> dict:
    skills, category_tree = load_index()
    base_tokens = tokenize(query)
    query_tokens = expand_query_tokens(base_tokens)
    if not query_tokens:
        return {
            "query": query,
            "categories_detected": [],
            "subcategories_detected": [],
            "essential": [],
            "context": [],
            "token_budget": {"essential_read_full": 0, "context_metadata_only": 0},
        }

    categories = [category] if category else detect_categories(query)
    subcategories = detect_subcategories(query)

    scored: list[tuple[float, dict]] = []
    for skill in skills:
        if category and skill.get("category") != category:
            continue
        s = score_skill(skill, query_tokens, query, categories, subcategories)
        if s >= 6.0:
            scored.append((s, skill))

    scored.sort(key=lambda x: (-x[0], x[1]["slug"]))
    essential, context = assign_tiers(
        scored, query_tokens, subcategories, essential_max, context_max
    )

    return {
        "query": query,
        "categories_detected": categories,
        "subcategories_detected": subcategories,
        "essential": essential,
        "context": context,
        "count": len(essential) + len(context),
    }


def _lookup_fast_paths(slugs: list[str], skills: list[dict]) -> list[dict]:
    by_slug = {s["slug"]: s for s in skills}
    entries = []
    for slug in slugs:
        skill = by_slug.get(slug)
        if not skill:
            continue
        entries.append(
            {
                "slug": skill["slug"],
                "score": 100.0,
                "category": skill.get("category", ""),
                "subcategory": skill.get("subcategory", ""),
                "description": skill.get("description", ""),
                "path": skill["path"],
                "slug_hits": 0,
                "tier": "essential",
                "source": "fast_path",
            }
        )
    return entries


def merge_tiered_results(
    results: list[dict],
    fast_path_entries: list[dict],
    essential_max: int,
    context_max: int,
) -> tuple[list[dict], list[dict]]:
    essential: list[dict] = []
    context: list[dict] = []
    seen: set[str] = set()

    for entry in fast_path_entries:
        if entry["path"] not in seen and len(essential) < essential_max:
            essential.append(entry)
            seen.add(entry["path"])

    all_essential = sorted(
        (m for r in results for m in r.get("essential", [])),
        key=lambda x: (-x.get("score", 0), x.get("slug", "")),
    )
    for m in all_essential:
        if m["path"] not in seen and len(essential) < essential_max:
            essential.append(m)
            seen.add(m["path"])

    all_context = sorted(
        (m for r in results for m in r.get("context", [])),
        key=lambda x: (-x.get("score", 0), x.get("slug", "")),
    )
    for m in all_context:
        if m["path"] not in seen and len(context) < context_max:
            context.append(m)
            seen.add(m["path"])

    return essential, context


def resolve_auto(
    query: str,
    essential_max: int = ESSENTIAL_MAX,
    context_max: int = CONTEXT_MAX,
) -> dict:
    skills, category_tree = load_index()
    expansion = expand_intent(query)

    use_auto = expansion["is_vague"] and (
        expansion["sub_queries"] or expansion["fast_path_slugs"]
    )

    if not use_auto:
        direct = resolve(query, essential_max=essential_max, context_max=context_max)
        return {
            **direct,
            "mode": "direct",
            "expansion": expansion,
            "category_tree": category_tree,
            "token_budget": {
                "essential_max": essential_max,
                "context_max": context_max,
                "essential_read_full": len(direct["essential"]),
                "context_metadata_only": len(direct["context"]),
                "note": "essential = Read SKILL.md complet ; context = description index uniquement",
            },
        }

    sub_queries = expansion["sub_queries"] or [query]
    n = max(len(sub_queries), 1)
    per_e = max(2, essential_max // n)
    per_c = max(1, context_max // n)

    sub_results = [resolve(sq, essential_max=per_e, context_max=per_c) for sq in sub_queries]
    sub_results.append(resolve(query, essential_max=3, context_max=2))

    fast_entries = _lookup_fast_paths(expansion["fast_path_slugs"], skills)
    essential, context = merge_tiered_results(
        sub_results, fast_entries, essential_max, context_max
    )

    all_cats: list[str] = []
    all_subs: list[str] = []
    for r in sub_results:
        all_cats.extend(r.get("categories_detected", []))
        all_subs.extend(r.get("subcategories_detected", []))

    return {
        "mode": "auto",
        "query": query,
        "expansion": expansion,
        "categories_detected": list(dict.fromkeys(all_cats)),
        "subcategories_detected": list(dict.fromkeys(all_subs)),
        "category_tree": category_tree,
        "token_budget": {
            "essential_max": essential_max,
            "context_max": context_max,
            "essential_read_full": len(essential),
            "context_metadata_only": len(context),
            "note": "essential = Read SKILL.md complet ; context = description index uniquement",
        },
        "essential": essential,
        "context": context,
        "count": len(essential) + len(context),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve skills with precision tiers (essential full read + context metadata)"
    )
    parser.add_argument("query", nargs="*", help="Task description (natural language OK)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--no-auto",
        action="store_true",
        help="Disable intent expansion (literal keyword search only). Auto is ON by default.",
    )
    parser.add_argument(
        "--essential-max",
        type=int,
        default=ESSENTIAL_MAX,
        help=f"Max skills to read in full (default {ESSENTIAL_MAX})",
    )
    parser.add_argument(
        "--context-max",
        type=int,
        default=CONTEXT_MAX,
        help=f"Max skills as metadata-only context (default {CONTEXT_MAX})",
    )
    parser.add_argument(
        "--category",
        choices=["design", "cursor", "dev", "security"],
        help="Force search within one category (disables --auto)",
    )
    parser.add_argument("--list-categories", action="store_true", help="Show category tree and exit")
    args = parser.parse_args()

    if args.list_categories:
        _, tree = load_index()
        print(json.dumps(tree, indent=2, ensure_ascii=False))
        return 0

    if not args.query:
        parser.error("query is required unless --list-categories is used")

    query = " ".join(args.query)

    if args.category or args.no_auto:
        result = resolve(
            query,
            category=args.category,
            essential_max=args.essential_max,
            context_max=args.context_max,
        )
        result["mode"] = "direct"
        skills, tree = load_index()
        result["category_tree"] = tree
        result["token_budget"] = {
            "essential_max": args.essential_max,
            "context_max": args.context_max,
            "essential_read_full": len(result["essential"]),
            "context_metadata_only": len(result["context"]),
        }
    else:
        result = resolve_auto(
            query,
            essential_max=args.essential_max,
            context_max=args.context_max,
        )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if not result["essential"] and not result["context"]:
        print("No matching skills above threshold.")
        return 1

    if result.get("mode") == "auto":
        exp = result.get("expansion", {})
        intents = exp.get("matched_intents", [])
        subs = exp.get("sub_queries", [])
        print(f"Mode: auto (requête naturelle décomposée)")
        if intents:
            print(f"Intents: {', '.join(intents)}")
        if subs:
            print(f"Sous-requêtes ({len(subs)}):")
            for sq in subs[:6]:
                print(f"  · {sq}")
            if len(subs) > 6:
                print(f"  · … +{len(subs) - 6} autres")

    cats = result.get("categories_detected", [])
    subcats = result.get("subcategories_detected", [])
    if cats:
        print(f"Categories: {', '.join(cats)}")
    if subcats:
        print(f"Subcategories: {', '.join(subcats)}")

    print(f"\n★ ESSENTIAL — lire SKILL.md complet ({len(result['essential'])}/{args.essential_max}):")
    for m in result["essential"]:
        src = f" [{m.get('source', 'scored')}]" if m.get("source") else ""
        print(f"  {m['score']:5.1f}  [{m['category']}/{m['subcategory']}] {m['slug']}{src}")
        print(f"         {m['path']}")

    if result["context"]:
        print(f"\n○ CONTEXT — description index seulement ({len(result['context'])}/{args.context_max}):")
        for m in result["context"]:
            desc = m["description"][:90] + ("…" if len(m["description"]) > 90 else "")
            print(f"  {m['score']:5.1f}  {m['slug']} — {desc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
