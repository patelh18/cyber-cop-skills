# Cyber-Cop skills

Claude skills, agents and tools for finding and handling CVEs in a codebase day to day.

| Skill | What it does |
|---|---|
| [dependency-file-discovery](skills/dependency-file-discovery/SKILL.md) | Detects the stack and lists the manifests, lockfiles and container files to scan for CVEs, as `deps-files.json` (schema v1). Other scanner skills consume it. |
| [cve-dependency-scan](skills/cve-dependency-scan/SKILL.md) | Checks the exact versions of the project's **direct** dependencies against CVEs published on [cve.now](https://cve.now) and [cve.org](https://www.cve.org) for today or a date range, and saves the IDs that need addressing to `.cyber-cop/cve-ids.direct.txt`. |
| [cve-subdependency-scan](skills/cve-subdependency-scan/SKILL.md) | Builds the full dependency tree from lockfiles (or resolves it with `--resolve`), checks the **transitive** (sub) dependencies against CVEs published on [cve.now](https://cve.now) and [cve.org](https://www.cve.org) for today or a date range, shows the chain that pulls each one in, and saves the IDs to `.cyber-cop/cve-ids.transitive.txt`. |

## Install

As a Claude Code plugin:

```
/plugin marketplace add patelh18/cyber-cop-skills
/plugin install cyber-cop@cyber-cop
```

Or copy folders from `skills/` into `~/.claude/skills/` (personal) or
`.claude/skills/` (one project). Copy `dependency-file-discovery` alongside the
scanners so they share the same file list.

Then ask Claude things like "check today's CVEs against this repo" or "did any
CVE from the last 7 days hit our dependencies?". The scanners also run on their
own, e.g. in CI or cron, and exit `1` when there is something to address:

```bash
python3 skills/cve-dependency-scan/scripts/cve_scan.py /path/to/project --days 1
python3 skills/cve-subdependency-scan/scripts/subdep_scan.py /path/to/project --days 1
```

## Conventions for skills in this repo

- One folder per skill: `SKILL.md`, `scripts/` (standard-library Python, no
  installs), `references/`, `tests/` (offline; run
  `python3 -m unittest discover -s skills/<name>/tests`).
- Outputs go in the scanned project's `.cyber-cop/` folder. CVE scanners write
  `cve-ids.<scope>.txt` (one ID per line, `#` comments) and
  `cve-report.<scope>.json`, and exit `0` nothing found, `1` findings, `2` source
  unreachable.
- CVE source clients live in `skills/cve-dependency-scan/scripts/cve_sources.py`;
  other skills keep an identical copy so each folder works on its own.
