# Skills Maestro

Open-source orchestrator for [Cursor](https://cursor.com): automatically routes to the **right agent skills** among hundreds installed, without blowing the token budget.

Say “run a network security audit” or “analyze the code with your skills” — Maestro handles the rest.

## One-command install

```bash
curl -fsSL https://raw.githubusercontent.com/adrn74/skills-maestro/main/install.sh | bash
```

That's it. Automatically:

- installs scripts into `~/.cursor/skills-maestro/`
- enables the Cursor rule `auto-skills-orchestrator.mdc`
- indexes all skills already on your machine
- ready to use in a **new chat**

**Requirements**: [Cursor](https://cursor.com), Python 3.9+, `git` or `curl`+`tar`.

### Install from clone

```bash
git clone https://github.com/adrn74/skills-maestro.git
cd skills-maestro && ./install.sh
```

### Optional environment variables

```bash
SKILLS_MAESTRO_REPO=https://github.com/adrn74/skills-maestro.git curl -fsSL https://raw.githubusercontent.com/adrn74/skills-maestro/main/install.sh | bash
SKILLS_MAESTRO_HOME=~/.cursor/skills-maestro   # install path
```

## Usage

No required configuration. Talk to Cursor normally:

- “Run a network security audit”
- “Analyze the code with your skills”
- “Is this performant?”
- “Redesign the dashboard”

The agent announces which skills were used at the top of each response.

### Manual test

```bash
python3 ~/.cursor/skills-maestro/resolve-skills.py "network security audit"
```

### After installing new skills

```bash
python3 ~/.cursor/skills-maestro/build-index.py
```

### Customization (optional)

Edit `~/.cursor/skills-maestro/config/project-context.json` to add your stack context — **not required** to get started.

## Features

| | |
|---|---|
| Natural language | No need to know skill slugs |
| Auto mode | Expands “network audit” → firewall, wireshark, IDS… |
| Token budget | Max 8 full SKILL.md files + 5 descriptions |
| Speed | ~200 ms across 800+ skills |
| Categories | design, cursor, dev, security |

## Architecture

```
User request
    → expand-intent (intents)
    → resolve-skills (scoring + tiers)
    → essential (≤8) + context (≤5)
    → response + Skills used
```

## License

MIT — [LICENSE](LICENSE)
