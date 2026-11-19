#!/usr/bin/env python3
"""Discover dependency files in a codebase that should be scanned for CVEs.

Walks a repository, detects its stack, and emits a stable JSON document
(schema_version "1") listing every manifest, lockfile, and container file,
grouped into projects. Standard library only.

Usage:
    python3 discover_deps.py [ROOT] [--output FILE] [--include-dev-dirs]
                             [--exclude DIR ...] [--max-depth N] [--pretty]
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
from datetime import datetime, timezone

SCHEMA_VERSION = "1"

# Directories that hold installed/vendored/generated code, never source
# manifests we own. Skipped unless --include-dev-dirs is passed.
DEFAULT_EXCLUDES = {
    ".git", ".hg", ".svn", "node_modules", "bower_components", "jspm_packages",
    "vendor", "venv", ".venv", "env", ".env", "virtualenv", "__pycache__",
    ".tox", ".nox", ".mypy_cache", ".pytest_cache", "site-packages",
    "dist", "build", "target", ".gradle", ".idea", ".vscode", ".next",
    ".nuxt", ".cache", ".terraform", "Pods", ".bundle", "_build", "deps",
    ".dart_tool", ".pub-cache", "coverage", ".yarn",
}

# Each rule: (glob pattern on basename, ecosystem, kind, format, package_manager)
# ecosystem uses OSV ecosystem names so downstream CVE lookups can reuse them.
# kind: manifest  -> declares direct dependencies
#       lockfile  -> pins the full resolved tree (direct + transitive)
#       container -> container image / OS packages (base image + installs)
RULES = [
    # JavaScript / TypeScript
    ("package.json", "npm", "manifest", "package.json", "npm"),
    ("package-lock.json", "npm", "lockfile", "package-lock.json", "npm"),
    ("npm-shrinkwrap.json", "npm", "lockfile", "npm-shrinkwrap.json", "npm"),
    ("yarn.lock", "npm", "lockfile", "yarn.lock", "yarn"),
    ("pnpm-lock.yaml", "npm", "lockfile", "pnpm-lock.yaml", "pnpm"),
    ("bun.lock", "npm", "lockfile", "bun.lock", "bun"),
    ("bun.lockb", "npm", "lockfile", "bun.lockb", "bun"),
    ("deno.json", "npm", "manifest", "deno.json", "deno"),
    ("deno.lock", "npm", "lockfile", "deno.lock", "deno"),
    # Python
    ("requirements*.txt", "PyPI", "manifest", "requirements.txt", "pip"),
    ("requirements*.in", "PyPI", "manifest", "requirements.in", "pip-tools"),
    ("constraints*.txt", "PyPI", "manifest", "constraints.txt", "pip"),
    ("pyproject.toml", "PyPI", "manifest", "pyproject.toml", None),  # refined
    ("setup.py", "PyPI", "manifest", "setup.py", "setuptools"),
    ("setup.cfg", "PyPI", "manifest", "setup.cfg", "setuptools"),
    ("Pipfile", "PyPI", "manifest", "Pipfile", "pipenv"),
    ("Pipfile.lock", "PyPI", "lockfile", "Pipfile.lock", "pipenv"),
    ("poetry.lock", "PyPI", "lockfile", "poetry.lock", "poetry"),
    ("uv.lock", "PyPI", "lockfile", "uv.lock", "uv"),
    ("pdm.lock", "PyPI", "lockfile", "pdm.lock", "pdm"),
    ("environment.yml", "PyPI", "manifest", "environment.yml", "conda"),
    ("environment.yaml", "PyPI", "manifest", "environment.yml", "conda"),
    # Ruby
    ("Gemfile", "RubyGems", "manifest", "Gemfile", "bundler"),
    ("gems.rb", "RubyGems", "manifest", "Gemfile", "bundler"),
    ("*.gemspec", "RubyGems", "manifest", "gemspec", "bundler"),
    ("Gemfile.lock", "RubyGems", "lockfile", "Gemfile.lock", "bundler"),
    ("gems.locked", "RubyGems", "lockfile", "Gemfile.lock", "bundler"),
    # Go
    ("go.mod", "Go", "manifest", "go.mod", "go"),
    ("go.sum", "Go", "lockfile", "go.sum", "go"),
    ("go.work", "Go", "manifest", "go.work", "go"),
    # Java / JVM
    ("pom.xml", "Maven", "manifest", "pom.xml", "maven"),
    ("build.gradle", "Maven", "manifest", "build.gradle", "gradle"),
    ("build.gradle.kts", "Maven", "manifest", "build.gradle.kts", "gradle"),
    ("gradle.lockfile", "Maven", "lockfile", "gradle.lockfile", "gradle"),
    ("libs.versions.toml", "Maven", "manifest", "libs.versions.toml", "gradle"),
    ("build.sbt", "Maven", "manifest", "build.sbt", "sbt"),
    # Rust
    ("Cargo.toml", "crates.io", "manifest", "Cargo.toml", "cargo"),
    ("Cargo.lock", "crates.io", "lockfile", "Cargo.lock", "cargo"),
    # PHP
    ("composer.json", "Packagist", "manifest", "composer.json", "composer"),
    ("composer.lock", "Packagist", "lockfile", "composer.lock", "composer"),
    # .NET
    ("*.csproj", "NuGet", "manifest", "csproj", "nuget"),
    ("*.fsproj", "NuGet", "manifest", "fsproj", "nuget"),
    ("*.vbproj", "NuGet", "manifest", "vbproj", "nuget"),
    ("packages.config", "NuGet", "manifest", "packages.config", "nuget"),
    ("Directory.Packages.props", "NuGet", "manifest", "Directory.Packages.props", "nuget"),
    ("packages.lock.json", "NuGet", "lockfile", "packages.lock.json", "nuget"),
    # Dart / Flutter
    ("pubspec.yaml", "Pub", "manifest", "pubspec.yaml", "pub"),
    ("pubspec.lock", "Pub", "lockfile", "pubspec.lock", "pub"),
    # Elixir
    ("mix.exs", "Hex", "manifest", "mix.exs", "mix"),
    ("mix.lock", "Hex", "lockfile", "mix.lock", "mix"),
    # Swift / iOS
    ("Package.swift", "SwiftURL", "manifest", "Package.swift", "swiftpm"),
    ("Package.resolved", "SwiftURL", "lockfile", "Package.resolved", "swiftpm"),
    ("Podfile", "CocoaPods", "manifest", "Podfile", "cocoapods"),
    ("Podfile.lock", "CocoaPods", "lockfile", "Podfile.lock", "cocoapods"),
    # Containers
    ("Dockerfile", "Docker", "container", "Dockerfile", "docker"),
    ("Dockerfile.*", "Docker", "container", "Dockerfile", "docker"),
    ("*.Dockerfile", "Docker", "container", "Dockerfile", "docker"),
    ("Containerfile", "Docker", "container", "Dockerfile", "docker"),
    ("docker-compose*.yml", "Docker", "container", "docker-compose", "docker-compose"),
    ("docker-compose*.yaml", "Docker", "container", "docker-compose", "docker-compose"),
    ("compose.yml", "Docker", "container", "docker-compose", "docker-compose"),
    ("compose.yaml", "Docker", "container", "docker-compose", "docker-compose"),
]

# Which lockfile pairs with which manifest within the same directory.
LOCK_PAIRS = {
    "package.json": ["package-lock.json", "npm-shrinkwrap.json", "yarn.lock",
                     "pnpm-lock.yaml", "bun.lock", "bun.lockb"],
    "deno.json": ["deno.lock"],
    "Pipfile": ["Pipfile.lock"],
    "pyproject.toml": ["poetry.lock", "uv.lock", "pdm.lock"],
    "Gemfile": ["Gemfile.lock"],
    "gems.rb": ["gems.locked"],
    "go.mod": ["go.sum"],
    "build.gradle": ["gradle.lockfile"],
    "build.gradle.kts": ["gradle.lockfile"],
    "Cargo.toml": ["Cargo.lock"],
    "composer.json": ["composer.lock"],
    "pubspec.yaml": ["pubspec.lock"],
    "mix.exs": ["mix.lock"],
    "Package.swift": ["Package.resolved"],
    "Podfile": ["Podfile.lock"],
}

# How to produce a full dependency tree when only a manifest exists.
RESOLVE_HINTS = {
    "npm": "npm install --package-lock-only (or yarn install --mode=update-lockfile)",
    "PyPI": "pip-compile / uv pip compile, or pip install --dry-run --report",
    "RubyGems": "bundle lock",
    "Go": "go mod tidy && go list -m all",
    "Maven": "mvn dependency:tree or gradle dependencies --write-locks",
    "crates.io": "cargo generate-lockfile",
    "Packagist": "composer update --lock",
    "NuGet": "dotnet restore --use-lock-file",
    "Pub": "dart pub get",
    "Hex": "mix deps.get",
    "SwiftURL": "swift package resolve",
    "CocoaPods": "pod install",
}


def match_rule(name: str):
    for pattern, eco, kind, fmt, pm in RULES:
        if fnmatch.fnmatchcase(name, pattern):
            return eco, kind, fmt, pm
    return None


def refine_pyproject(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read(200_000)
    except OSError:
        return "pip"
    if "[tool.poetry" in text:
        return "poetry"
    if "[tool.pdm" in text:
        return "pdm"
    if "[tool.uv" in text:
        return "uv"
    if "[tool.hatch" in text:
        return "hatch"
    return "pip"


def requirements_fully_pinned(path: str) -> bool:
    """True if every requirement line is pinned with ==/=== (lock-like)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return False
    reqs = 0
    for raw in lines:
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        reqs += 1
        if "==" not in line:
            return False
    return reqs > 0


def go_mod_lists_indirect(path: str) -> bool:
    """Go >= 1.17 go.mod files list the full module graph (// indirect)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return "// indirect" in fh.read()
    except OSError:
        return False


def compose_images(path: str) -> list[str]:
    images = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                line = raw.strip()
                if line.startswith("image:"):
                    img = line.split(":", 1)[1].strip().strip("'\"")
                    if img:
                        images.append(img)
    except OSError:
        pass
    return images


def dockerfile_base_images(path: str) -> list[str]:
    images = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                parts = raw.strip().split()
                if len(parts) >= 2 and parts[0].upper() == "FROM":
                    args = [p for p in parts[1:] if not p.startswith("--")]
                    if args:
                        images.append(args[0])
    except OSError:
        pass
    return images


def walk(root: str, excludes: set[str], max_depth: int | None):
    root_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in excludes)
        if max_depth is not None and dirpath.count(os.sep) - root_depth >= max_depth:
            dirnames[:] = []
        for name in sorted(filenames):
            yield dirpath, name


def discover(root: str, excludes: set[str], max_depth: int | None) -> dict:
    root = os.path.abspath(root)
    files = []
    for dirpath, name in walk(root, excludes, max_depth):
        rule = match_rule(name)
        if not rule:
            continue
        eco, kind, fmt, pm = rule
        abspath = os.path.join(dirpath, name)
        rel = os.path.relpath(abspath, root).replace(os.sep, "/")
        project_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        entry = {
            "path": rel,
            "ecosystem": eco,
            "kind": kind,
            "format": fmt,
            "package_manager": pm,
            "project_dir": project_dir,
            "covers": ["direct", "transitive"] if kind == "lockfile" else ["direct"],
            "paired_with": None,
        }
        if fmt == "pyproject.toml":
            entry["package_manager"] = refine_pyproject(abspath)
        if fmt == "requirements.txt" and requirements_fully_pinned(abspath):
            entry["pinned"] = True
        if fmt == "go.mod" and go_mod_lists_indirect(abspath):
            entry["covers"] = ["direct", "transitive"]
        if fmt == "Dockerfile":
            entry["base_images"] = dockerfile_base_images(abspath)
        if fmt == "docker-compose":
            entry["base_images"] = compose_images(abspath)
        files.append(entry)

    # Pair manifests with lockfiles in the same directory.
    by_dir: dict[str, dict[str, dict]] = {}
    for f in files:
        by_dir.setdefault(f["project_dir"], {})[f["path"].rsplit("/", 1)[-1]] = f
    for d, names in by_dir.items():
        for manifest, locks in LOCK_PAIRS.items():
            if manifest not in names:
                continue
            for lock in locks:
                if lock in names:
                    names[manifest]["paired_with"] = names[lock]["path"]
                    names[lock]["paired_with"] = names[manifest]["path"]
                    # lockfile tells us the real package manager
                    names[manifest]["package_manager"] = names[lock]["package_manager"]
                    break

    # Group into projects (project_dir + ecosystem).
    projects: dict[tuple[str, str], dict] = {}
    for f in files:
        key = (f["project_dir"], f["ecosystem"])
        p = projects.setdefault(key, {
            "project_dir": f["project_dir"],
            "ecosystem": f["ecosystem"],
            "package_manager": None,
            "manifests": [],
            "lockfiles": [],
            "containers": [],
            "transitive_resolvable": False,
        })
        bucket = {"manifest": "manifests", "lockfile": "lockfiles",
                  "container": "containers"}[f["kind"]]
        p[bucket].append(f["path"])
        if "transitive" in f["covers"] or f.get("pinned"):
            p["transitive_resolvable"] = True
        if f["kind"] == "lockfile" or p["package_manager"] is None:
            p["package_manager"] = f["package_manager"]

    warnings = []
    for p in projects.values():
        if p["ecosystem"] == "Docker":
            p["transitive_resolvable"] = False
            continue
        if p["manifests"] and not p["transitive_resolvable"]:
            warnings.append(
                f"{p['project_dir']}: {p['ecosystem']} manifest(s) "
                f"{', '.join(p['manifests'])} have no lockfile; sub-dependencies "
                "must be resolved before transitive CVE matching "
                f"(try: {RESOLVE_HINTS.get(p['ecosystem'], 'the package manager lock command')}).")
        if p["lockfiles"] and not p["manifests"]:
            warnings.append(
                f"{p['project_dir']}: {p['ecosystem']} lockfile(s) without a "
                "manifest; direct vs transitive split may be unknown.")
    if not files:
        warnings.append("No dependency files found under root.")

    ecosystems = sorted({f["ecosystem"] for f in files})
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "root": root,
        "ecosystems": ecosystems,
        "summary": {
            "files": len(files),
            "manifests": sum(f["kind"] == "manifest" for f in files),
            "lockfiles": sum(f["kind"] == "lockfile" for f in files),
            "containers": sum(f["kind"] == "container" for f in files),
            "projects": len(projects),
        },
        "files": sorted(files, key=lambda f: f["path"]),
        "projects": sorted(projects.values(),
                           key=lambda p: (p["project_dir"], p["ecosystem"])),
        "warnings": warnings,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".", help="repository root (default: .)")
    ap.add_argument("-o", "--output", help="write JSON here instead of stdout")
    ap.add_argument("--exclude", action="append", default=[],
                    help="extra directory name to skip (repeatable)")
    ap.add_argument("--include-dev-dirs", action="store_true",
                    help="do not skip node_modules, vendor, venv, build dirs, etc.")
    ap.add_argument("--max-depth", type=int, default=None,
                    help="maximum directory depth to descend")
    ap.add_argument("--pretty", action="store_true", help="indent JSON output")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.root):
        print(f"error: {args.root} is not a directory", file=sys.stderr)
        return 2
    excludes = set() if args.include_dev_dirs else set(DEFAULT_EXCLUDES)
    excludes |= set(args.exclude)
    result = discover(args.root, excludes, args.max_depth)
    text = json.dumps(result, indent=2 if (args.pretty or args.output) else None)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"wrote {args.output}: {result['summary']['files']} files, "
              f"{result['summary']['projects']} projects, "
              f"ecosystems={','.join(result['ecosystems']) or 'none'}",
              file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
