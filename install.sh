#!/usr/bin/env bash
# Cursor Skills Maestro — one-command installer
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/adriengirin/cursor-skills-maestro/main/install.sh | bash
#   ./install.sh   (from a cloned repo)
set -euo pipefail

SKILLS_MAESTRO_REPO="${SKILLS_MAESTRO_REPO:-https://github.com/adriengirin/cursor-skills-maestro.git}"
SKILLS_MAESTRO_BRANCH="${SKILLS_MAESTRO_BRANCH:-main}"
MAESTRO_HOME="${SKILLS_MAESTRO_HOME:-$HOME/.cursor/skills-maestro}"
RULES_DIR="${CURSOR_RULES_DIR:-$HOME/.cursor/rules}"
TMP_DIR=""

cleanup() {
  if [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR"
  fi
}
trap cleanup EXIT

info()  { printf '\033[36m→\033[0m %s\n' "$*"; }
ok()    { printf '\033[32m✓\033[0m %s\n' "$*"; }
warn()  { printf '\033[33m!\033[0m %s\n' "$*" >&2; }
die()   { printf '\033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

resolve_repo_root() {
  # Running from cloned repo (./install.sh)
  if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "$script_dir/maestro/resolve-skills.py" ]]; then
      echo "$script_dir"
      return 0
    fi
  fi
  # Fallback: cwd
  if [[ -f "./maestro/resolve-skills.py" ]]; then
    echo "$(pwd)"
    return 0
  fi
  return 1
}

fetch_repo() {
  TMP_DIR="$(mktemp -d 2>/dev/null || mktemp -d -t skills-maestro)"
  info "Downloading Skills Maestro from $SKILLS_MAESTRO_REPO …"

  if command -v git >/dev/null 2>&1; then
    git clone --depth 1 --branch "$SKILLS_MAESTRO_BRANCH" "$SKILLS_MAESTRO_REPO" "$TMP_DIR" \
      >/dev/null 2>&1 || die "git clone failed. Check SKILLS_MAESTRO_REPO / network."
    echo "$TMP_DIR"
    return 0
  fi

  if command -v curl >/dev/null 2>&1 && command -v tar >/dev/null 2>&1; then
    local tarball_url
    tarball_url="https://github.com/$(echo "$SKILLS_MAESTRO_REPO" | sed -E 's#.*github.com[:/]([^/]+/[^/.]+)(\.git)?#\1#')/archive/refs/heads/${SKILLS_MAESTRO_BRANCH}.tar.gz"
    curl -fsSL "$tarball_url" | tar -xz -C "$TMP_DIR" --strip-components=1 \
      || die "Download failed. Install git or check SKILLS_MAESTRO_REPO."
    echo "$TMP_DIR"
    return 0
  fi

  die "Need git or curl+tar to install remotely."
}

preflight() {
  command -v python3 >/dev/null 2>&1 || die "python3 is required (3.9+)."
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
    || die "Python 3.9+ required."
  mkdir -p "$HOME/.cursor" "$MAESTRO_HOME" "$MAESTRO_HOME/config" "$RULES_DIR"
}

install_files() {
  local repo_root="$1"
  cp "$repo_root/maestro/"*.py "$MAESTRO_HOME/"
  chmod +x "$MAESTRO_HOME/"*.py 2>/dev/null || true
  cp "$repo_root/rules/auto-skills-orchestrator.mdc" "$RULES_DIR/"

  if [[ ! -f "$MAESTRO_HOME/config/project-context.json" ]]; then
    cp "$repo_root/config/project-context.example.json" "$MAESTRO_HOME/config/project-context.json"
  fi

  # Optional extra skill roots — only create if missing
  if [[ ! -f "$MAESTRO_HOME/config/skill-roots.json" ]] \
     && [[ -d "$HOME/.agents/skills" || -d ".agents/skills" ]]; then
    : # defaults in build-index.py already cover ~/.agents/skills
  fi
}

count_skills() {
  local n=0
  for root in "$HOME/.cursor/skills" "$HOME/.cursor/skills-cursor" "$HOME/.agents/skills"; do
    [[ -d "$root" ]] || continue
    n=$((n + $(find "$root" -maxdepth 2 -name 'SKILL.md' 2>/dev/null | wc -l | tr -d ' ')))
  done
  echo "$n"
}

smoke_test() {
  local out
  out="$(python3 "$MAESTRO_HOME/resolve-skills.py" "audit sécurité" --json 2>/dev/null || true)"
  echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('essential') is not None" \
    2>/dev/null || warn "Smoke test skipped (no skills indexed yet?)"
}

main() {
  printf '\n\033[1mCursor Skills Maestro\033[0m — install\n\n'

  preflight

  local repo_root
  if repo_root="$(resolve_repo_root)"; then
    info "Installing from local repo …"
  else
    repo_root="$(fetch_repo)"
  fi

  install_files "$repo_root"

  info "Indexing installed skills …"
  python3 "$MAESTRO_HOME/build-index.py"

  local skill_count indexed
  skill_count="$(count_skills)"
  indexed="$(python3 -c "import json; print(json.load(open('$MAESTRO_HOME/skills-index.json'))['count'])" 2>/dev/null || echo 0)"

  smoke_test

  printf '\n'
  ok "Installed to $MAESTRO_HOME"
  ok "Cursor rule → $RULES_DIR/auto-skills-orchestrator.mdc"
  ok "Indexed $indexed skills (found $skill_count SKILL.md on disk)"

  if [[ "$skill_count" -eq 0 ]]; then
    warn "No skills detected yet. Install skills (npx skills add …) then run:"
    warn "  python3 $MAESTRO_HOME/build-index.py"
  fi

  printf '\n'
  info "Open a new Cursor chat — Maestro is active. Try:"
  printf '  "Fait un audit sécurité réseau"\n'
  printf '  "Analyse le code avec tes skills"\n\n'
}

main "$@"
