"""Run: python3 -m unittest discover -s skills/dependency-file-discovery/tests"""
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "discover_deps.py")
FIXTURE = os.path.join(HERE, "fixtures", "mono")


def run(*args):
    out = subprocess.run([sys.executable, SCRIPT, FIXTURE, *args],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


class DiscoverTest(unittest.TestCase):
    def setUp(self):
        self.r = run()
        self.files = {f["path"]: f for f in self.r["files"]}

    def test_schema_keys(self):
        for k in ("schema_version", "generated_at", "root", "ecosystems",
                  "summary", "files", "projects", "warnings"):
            self.assertIn(k, self.r)
        self.assertEqual(self.r["schema_version"], "1")

    def test_skips_node_modules(self):
        self.assertFalse(any("node_modules" in p for p in self.files))

    def test_pairs_lockfiles(self):
        self.assertEqual(self.files["web/package.json"]["paired_with"], "web/yarn.lock")
        self.assertEqual(self.files["web/package.json"]["package_manager"], "yarn")
        self.assertEqual(self.files["svc/Gemfile.lock"]["covers"], ["direct", "transitive"])
        self.assertEqual(self.files["infra/pyproject.toml"]["package_manager"], "poetry")

    def test_docker(self):
        self.assertEqual(self.files["api/Dockerfile"]["base_images"],
                         ["python:3.12-slim", "nginx:1.25"])
        self.assertEqual(self.files["docker-compose.yml"]["base_images"], ["postgres:16"])

    def test_go_mod_indirect_counts_as_transitive(self):
        self.assertEqual(self.files["svc/go.mod"]["covers"], ["direct", "transitive"])

    def test_warns_unlocked_manifest(self):
        self.assertTrue(any(w.startswith("api: PyPI") for w in self.r["warnings"]))

    def test_include_dev_dirs(self):
        r = run("--include-dev-dirs")
        self.assertTrue(any("node_modules" in f["path"] for f in r["files"]))


if __name__ == "__main__":
    unittest.main()
