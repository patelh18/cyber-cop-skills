# Cyber-Cop skills

Claude skills, agents and tools for finding and handling CVEs in a codebase day to day.

| Skill | What it does |
|---|---|
| [dependency-file-discovery](skills/dependency-file-discovery/SKILL.md) | Detects the stack and lists the manifests, lockfiles and container files to scan for CVEs, as `deps-files.json` (schema v1). Other scanner skills consume it. |
| [cve-dependency-scan](skills/cve-dependency-scan/SKILL.md) | Checks the exact versions of the project's **direct** dependencies (npm, PyPI, RubyGems, Composer, Dockerfile installs) and the **PHP runtime** it pins against CVEs published on [cve.now](https://cve.now) and [cve.org](https://www.cve.org) for today or a date range, and saves the IDs that need addressing to `.cyber-cop/cve-ids.direct.txt`. |
| [cve-subdependency-scan](skills/cve-subdependency-scan/SKILL.md) | Builds the full dependency tree from lockfiles (or resolves it with `--resolve`), checks the **transitive** (sub) dependencies against CVEs published on [cve.now](https://cve.now) and [cve.org](https://www.cve.org) for today or a date range, shows the chain that pulls each one in, and saves the IDs to `.cyber-cop/cve-ids.transitive.txt`. |
| [cve-reproduce](skills/cve-reproduce/SKILL.md) | Confirms each CVE in `.cyber-cop/cve-ids.*.txt` is really in the codebase: finds where the package is imported and writes a **presence test** in the project's own framework (pytest/unittest, jest/vitest/mocha/node:test, RSpec/Minitest, go test, PHPUnit or plain `php`) that fails while the vulnerable version is resolved and passes once fixed. Defensive: it reads versions, it never runs an exploit. |
| [cve-migration-plan](skills/cve-migration-plan/SKILL.md) | Plans the upgrade from the current to the nearest fixed version: package-manager strategy (upgrade, refresh, override/resolution, pin), the code and APIs that use the dependency, breaking changes to review, and the regression tests that gate it. Records a person's approval. |
| [cve-fix](skills/cve-fix/SKILL.md) | Applies an **approved** plan, trying its strategies in order, and verifies with the presence test plus regression tests against a pre-change baseline. Restores every file if the fix fails or regresses anything. |
| [cve-remediate](skills/cve-remediate/SKILL.md) | Orchestrates the lifecycle (scan → reproduce → plan → **approval checkpoint** → fix → rescan), shows where every CVE stands with `status.py`, and hands per-CVE stages to the plugin's subagents. |

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

## Remediation lifecycle

```
scan ──> reproduce ──> plan ──> approve ──> fix + verify ──> rescan
         (presence     (target,  (a person,   (presence test
          test fails)   tests)    or a patch   passes, no
                                  policy)      regressions)
```

Every CVE gets a case folder, `.cyber-cop/cases/<CVE>/`, that each stage reads
and adds to (`case.json`, `reproduce.json`, `plan.json` + `migration-plan.md`,
`fix.json` + `fix-report.md`). Work can stop at any stage and resume later, and
`skills/cve-remediate/scripts/status.py` shows what each case needs next.

Why separate skills plus an orchestrator: each stage is useful on its own ("just
reproduce this CVE", "plan the lodash upgrade"), the orchestrator stays small,
and the hand-off is a file a person can read, not a conversation. The approval
checkpoint sits between plan and fix because that is the first step that
changes the code. The plugin also ships three subagents (`agents/`):
`cve-reproducer` and `cve-migration-planner` run one per CVE in parallel;
`cve-fixer` runs one at a time because fixes share lockfiles.

`skills/cve-remediate/tests/test_php_e2e.py` runs the whole chain (scan →
reproduce → plan → approve → fix → rescan) on a PHP fixture app for the real
CVE-2026-109619, offline, against recorded cve.now / cve.org responses.

Ask Claude things like "take care of today's CVEs", "reproduce CVE-2021-23337",
"plan the fix for the qs CVE", or "what CVE work is pending?".

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
- The case library lives in `skills/cve-reproduce/scripts/cyber_case.py`;
  `cve-migration-plan` and `cve-fix` keep identical copies (tests check it).
  Install the four lifecycle skills together.
