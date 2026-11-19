# deps-files.json, schema version 1

```jsonc
{
  "schema_version": "1",
  "generated_at": "2026-11-19T02:54:45Z",      // UTC, ISO 8601
  "root": "/abs/path/to/repo",
  "ecosystems": ["Docker", "PyPI", "npm"],      // sorted, unique
  "summary": { "files": 10, "manifests": 5, "lockfiles": 3, "containers": 2, "projects": 7 },
  "files": [ /* FileEntry, sorted by path */ ],
  "projects": [ /* Project, sorted by project_dir then ecosystem */ ],
  "warnings": [ "api: PyPI manifest(s) api/requirements.txt have no lockfile; ..." ]
}
```

## FileEntry

| field | type | meaning |
|---|---|---|
| `path` | string | Path relative to `root`, forward slashes. |
| `ecosystem` | string | OSV ecosystem: `npm`, `PyPI`, `RubyGems`, `Go`, `Maven`, `crates.io`, `Packagist`, `NuGet`, `Pub`, `Hex`, `SwiftURL`, `CocoaPods`, `Docker`. |
| `kind` | `manifest` \| `lockfile` \| `container` | Manifest declares direct deps; lockfile pins the resolved tree; container is a Dockerfile/compose file. |
| `format` | string | Parser to use, e.g. `package.json`, `yarn.lock`, `requirements.txt`, `pyproject.toml`, `Gemfile.lock`, `go.mod`, `Dockerfile`, `docker-compose`, `csproj`, `gemspec`. Variants share a format (`requirements-dev.txt` -> `requirements.txt`, `Dockerfile.prod` -> `Dockerfile`). |
| `package_manager` | string | e.g. `npm`, `yarn`, `pnpm`, `pip`, `poetry`, `uv`, `bundler`, `go`, `gradle`, `docker`. A manifest takes its lockfile's manager when paired. |
| `project_dir` | string | Directory containing the file, relative to root (`.` for root). |
| `covers` | string[] | `["direct"]` or `["direct","transitive"]`. |
| `paired_with` | string \| null | The matching lockfile (for a manifest) or manifest (for a lockfile) in the same directory. |
| `pinned` | bool, optional | `requirements*.txt` only: every requirement is pinned with `==` (lock-like). |
| `base_images` | string[], optional | `Dockerfile`: every `FROM` image. `docker-compose`: every `image:`. |

## Project

One per (`project_dir`, `ecosystem`).

| field | type | meaning |
|---|---|---|
| `project_dir` | string | As above. |
| `ecosystem` | string | As above. |
| `package_manager` | string | Lockfile's manager if present, else the first manifest's. |
| `manifests` / `lockfiles` / `containers` | string[] | Paths by kind. |
| `transitive_resolvable` | bool | True when a file in the project lists the full tree (lockfile, `go.mod` with indirect requires, or a pinned requirements file). Always false for `Docker`. |

## Consumer recipes

```python
import json
d = json.load(open("deps-files.json"))
direct = [f for f in d["files"] if f["kind"] in ("manifest", "container")]
transitive = [f for f in d["files"] if "transitive" in f["covers"] or f.get("pinned")]
unresolved = [p for p in d["projects"] if p["ecosystem"] != "Docker" and not p["transitive_resolvable"]]
```
