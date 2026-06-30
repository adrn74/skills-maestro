#!/usr/bin/env python3
"""Intent expansion: translate vague user requests into precise skill searches."""

from __future__ import annotations

import re
import unicodedata

# Ordered rules — multiple can match; sub-queries are unioned.
INTENT_RULES: list[dict] = [
    {
        "id": "network-security-audit",
        "match_any": [
            "audit securite reseau",
            "audit reseau",
            "securite reseau",
            "audit réseau",
            "sécurité réseau",
            "network security audit",
            "network audit",
        ],
        "sub_queries": [
            "network security firewall segmentation IDS",
            "wireshark network traffic analysis intrusion detection",
            "network vulnerability scanning nmap",
        ],
        "fast_path_slugs": ["review-security"],
    },
    {
        "id": "web-security-audit",
        "match_any": [
            "audit securite",
            "audit de securite",
            "audit sécurité",
            "security audit",
            "audite la securite",
            "audite la sécurité",
            "audit applicatif",
            "audit application",
        ],
        "sub_queries": [
            "web application security OWASP vulnerability assessment",
            "API security authentication authorization JWT OAuth",
            "security headers CSP HSTS audit",
        ],
        "fast_path_slugs": ["review-security"],
    },
    {
        "id": "code-analysis",
        "match_any": [
            "analyse le code",
            "analyse ce code",
            "analyse le projet",
            "analyze the code",
            "analyze code",
            "review code",
            "audite le code",
            "regarde le code",
            "avec tes skills",
            "utilise tes skills",
            "using your skills",
        ],
        "sub_queries": [
            "code review security performance correctness edge cases",
            "static application security testing OWASP",
        ],
        "fast_path_slugs": ["code-review", "review-security"],
    },
    {
        "id": "performance",
        "match_any": [
            "performant",
            "performance",
            "optimis",
            "optimise",
            "lent",
            "lenteur",
            "rapide",
            "slow",
            "bottleneck",
            "scalab",
        ],
        "sub_queries": [
            "postgres query optimization database performance",
            "application performance profiling bottlenecks",
            "load testing scalability web API",
        ],
        "fast_path_slugs": ["performance-engineer", "postgres", "load-testing"],
    },
    {
        "id": "mobile-security",
        "match_any": [
            "mobile security",
            "securite mobile",
            "sécurité mobile",
            "app mobile",
            "expo security",
            "react native security",
        ],
        "sub_queries": [
            "mobile application security testing OWASP MASVS",
            "API mobile authentication token security",
            "ios android app security objection frida",
        ],
        "fast_path_slugs": ["review-security"],
    },
    {
        "id": "ui-design",
        "match_any": [
            "plus joli",
            "plus beau",
            "design",
            "interface",
            "ui ",
            " ux",
            "ecran",
            "écran",
            "dashboard",
            "landing",
        ],
        "sub_queries": [
            "UI UX design polish accessibility dashboard",
        ],
        "fast_path_slugs": ["impeccable", "ui-ux-pro-max"],
    },
    {
        "id": "pr-ci",
        "match_any": [
            "babysit",
            "merge",
            "pull request",
            " ma pr",
            "bugbot",
            "ci fail",
        ],
        "sub_queries": [],
        "fast_path_slugs": ["babysit", "review-bugbot"],
    },
]

from config import load_project_context_queries

VAGUE_MARKERS = frozenset(
    {
        "audit",
        "analyse",
        "analyze",
        "securite",
        "security",
        "performant",
        "performance",
        "review",
        "check",
        "skills",
        "skill",
        "dis",
        "dit",
        "fait",
        "fais",
        "utilise",
        "using",
        "tout",
        "cest",
        "cela",
    }
)


def normalize_query(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text


def tokenize_simple(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]{2,}", normalize_query(text))


def is_vague_query(query: str) -> bool:
    nq = normalize_query(query)
    tokens = tokenize_simple(nq)
    if len(tokens) > 18:
        return False
    return any(m in nq for m in VAGUE_MARKERS) or len(tokens) <= 8


def expand_intent(query: str) -> dict:
    nq = normalize_query(query)
    sub_queries: list[str] = []
    fast_paths: list[str] = []
    matched: list[str] = []

    for rule in INTENT_RULES:
        if any(phrase in nq or normalize_query(phrase) in nq for phrase in rule["match_any"]):
            matched.append(rule["id"])
            sub_queries.extend(rule["sub_queries"])
            fast_paths.extend(rule.get("fast_path_slugs", []))

    # Compound: audit + réseau without full phrase
    if "audit" in nq and ("reseau" in nq or "network" in nq):
        if "network-security-audit" not in matched:
            matched.append("network-security-audit")
            sub_queries.extend(INTENT_RULES[0]["sub_queries"])
            fast_paths.extend(INTENT_RULES[0].get("fast_path_slugs", []))

    # Compound: code + performance
    if ("code" in nq or "projet" in nq) and any(
        w in nq for w in ("performant", "performance", "lent", "optimis")
    ):
        for rule in INTENT_RULES:
            if rule["id"] in ("code-analysis", "performance") and rule["id"] not in matched:
                matched.append(rule["id"])
                sub_queries.extend(rule["sub_queries"])
                fast_paths.extend(rule.get("fast_path_slugs", []))

    # Fallbacks
    if not sub_queries:
        if any(w in nq for w in ("audit", "securite", "security", "vuln")):
            matched.append("fallback-security")
            sub_queries = [
                "web application OWASP security vulnerability audit",
                "API security broken access control authentication",
            ]
            fast_paths.append("review-security")
        elif any(w in nq for w in ("analyse", "analyze", "review", "audite", "regarde")):
            matched.append("fallback-code")
            sub_queries = ["code review security performance correctness"]
            fast_paths.extend(["code-review", "review-security"])

    # Optional project-specific context queries (config/project-context.json)
    if matched and any(
        m in matched
        for m in (
            "network-security-audit",
            "web-security-audit",
            "code-analysis",
            "fallback-security",
            "fallback-code",
            "mobile-security",
        )
    ):
        sub_queries.extend(load_project_context_queries())

    sub_queries = list(dict.fromkeys(sub_queries))
    fast_paths = list(dict.fromkeys(fast_paths))

    return {
        "original_query": query,
        "normalized": nq,
        "is_vague": is_vague_query(query) or bool(matched),
        "matched_intents": matched,
        "sub_queries": sub_queries,
        "fast_path_slugs": fast_paths,
    }
