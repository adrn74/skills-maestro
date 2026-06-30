# Skills Maestro

Orchestrateur open source pour [Cursor](https://cursor.com) : route automatiquement vers les **bons agent skills** parmi des centaines d'installés, sans exploser le budget tokens.

Dis « fait un audit sécurité réseau » ou « analyse le code avec tes skills » — Maestro fait le reste.

## Installation (une commande)

```bash
curl -fsSL https://raw.githubusercontent.com/adrn74/skills-maestro/main/install.sh | bash
```

C'est tout. Automatiquement :

- installe les scripts dans `~/.cursor/skills-maestro/`
- active la règle Cursor `auto-skills-orchestrator.mdc`
- indexe tous tes skills déjà présents
- prêt à l'emploi dans une **nouvelle conversation**

**Prérequis** : [Cursor](https://cursor.com), Python 3.9+, `git` ou `curl`+`tar`.

### Installation depuis le clone

```bash
git clone https://github.com/adrn74/skills-maestro.git
cd skills-maestro && ./install.sh
```

### Variables optionnelles

```bash
SKILLS_MAESTRO_REPO=https://github.com/adrn74/skills-maestro.git curl -fsSL https://raw.githubusercontent.com/adrn74/skills-maestro/main/install.sh | bash
SKILLS_MAESTRO_HOME=~/.cursor/skills-maestro   # chemin d'install
```

## Utilisation

Aucune config obligatoire. Parle normalement à Cursor :

- « Fait un audit sécurité réseau »
- « Analyse le code avec tes skills »
- « C'est performant ? »
- « Redesign le dashboard »

L'agent annonce les skills utilisés en tête de réponse.

### Test manuel

```bash
python3 ~/.cursor/skills-maestro/resolve-skills.py "audit sécurité réseau"
```

### Après installation de nouveaux skills

```bash
python3 ~/.cursor/skills-maestro/build-index.py
```

### Personnalisation (optionnelle)

Édite `~/.cursor/skills-maestro/config/project-context.json` pour ajouter le contexte de ton stack — **pas requis** pour démarrer.

## Fonctionnalités

| | |
|---|---|
| Langage naturel | Pas besoin de connaître les slugs |
| Mode auto | Décompose « audit réseau » → firewall, wireshark, IDS… |
| Budget tokens | Max 8 SKILL.md complets + 5 descriptions |
| Vitesse | ~200 ms sur 800+ skills |
| Catégories | design, cursor, dev, security |

## Architecture

```
Demande utilisateur
    → expand-intent (intentions)
    → resolve-skills (score + paliers)
    → essential (≤8) + context (≤5)
    → réponse + Skills utilisés
```

## Licence

MIT — [LICENSE](LICENSE)

---

## English

**One-command install:**

```bash
curl -fsSL https://raw.githubusercontent.com/adrn74/skills-maestro/main/install.sh | bash
```

Open a new Cursor chat. Ask anything in plain language. No config required.
