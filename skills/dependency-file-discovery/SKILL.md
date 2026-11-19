---
name: dependency-file-discovery
description: Detect a codebase's stack and list every dependency file (manifests, lockfiles, Dockerfiles/compose) that must be scanned against newly published CVEs. Use before any CVE or dependency vulnerability scan, or when asked which files declare a project's dependencies. Emits stable JSON (schema v1) for other Cyber-Cop skills.
---

# Dependency file discovery

Finds the files a CVE scanner needs to read, so downstream skills never have to
guess the stack. It is the first step of the Cyber-Cop pipeline:

```
dependency-file-discovery  ->  deps-files.json
        |-> CVE dependency scanner      (direct deps: kind=manifest/container)
        '-> sub-dependency CVE scanner  (transitive deps: covers contains "transitive")
```

## How to run

Run the bundled script (Python 3.8+, standard library only) from the repo you
want to scan:

```bash
python3 <skill_dir>/scripts/discover_deps.py <repo_root> --output deps-files.json
```

- Without `--output` it prints JSON to stdout (add `--pretty` to indent).
- Installed/vendored/build directories (`node_modules`, `vendor`, `venv`,
  `.venv`, `dist`, `build`, `target`, `.git`, ...) are skipped. Pass
  `--include-dev-dirs` to include them, `--exclude NAME` to skip more,
  `--max-depth N` to limit recursion.
- Exit code 0 on success, 2 if the root is not a directory.

## What to do with the result

1. Read `summary`, `ecosystems` and `warnings` and tell the user the detected
   stack in one or two sentences (e.g. "npm (yarn) in web/, Python (poetry) in
   infra/, two Dockerfiles").
2. Surface every warning. A manifest without a lockfile means sub-dependencies
   cannot be matched exactly; the warning includes the command that produces a
   lockfile. Do not run it without the user's say-so, since it may change files.
3. Hand `deps-files.json` (or its path) to the scanning skill:
   - **Direct-dependency scan**: files with `kind` = `manifest`, plus
     `container` files (scan `base_images` and `RUN apt/apk/pip/npm install`).
   - **Sub-dependency scan**: files whose `covers` includes `"transitive"`
     (lockfiles, `go.mod` with `// indirect`, fully pinned `requirements.txt`
     marked `pinned: true`). For projects with `transitive_resolvable: false`,
     resolve the tree first or report the gap.
4. Use `ecosystem` verbatim when querying CVE/OSV data; values follow OSV
   ecosystem names.

## Output contract

The JSON shape is stable for `schema_version: "1"`; fields may be added but
existing fields will not be renamed or removed without bumping the version.
Full field reference and examples: [references/output-schema.md](references/output-schema.md).

Supported file types: npm/yarn/pnpm/bun/deno, pip/pip-tools/pipenv/poetry/uv/
pdm/conda/setuptools, Bundler, Go modules, Maven/Gradle/sbt, Cargo, Composer,
NuGet, Pub, Hex (mix), SwiftPM, CocoaPods, Dockerfile/Containerfile and
docker-compose. To add one, append a row to `RULES` (and `LOCK_PAIRS` /
`RESOLVE_HINTS` if it has a lockfile) in `scripts/discover_deps.py` and add a
fixture to `tests/`.

## Tests

```bash
python3 -m unittest discover -s <skill_dir>/tests
```
