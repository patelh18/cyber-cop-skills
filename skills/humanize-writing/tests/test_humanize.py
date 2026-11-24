"""Run: python3 -m unittest discover -s skills/humanize-writing/tests"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
FIX = os.path.join(HERE, "fixtures")
BEFORE = os.path.join(FIX, "before.md")
AFTER = os.path.join(FIX, "after.md")
sys.path.insert(0, SCRIPTS)

import structure_diff  # noqa: E402
import style_check  # noqa: E402


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def diff_text(orig, new, **kw):
    return structure_diff.compare(structure_diff.parse_markdown(orig),
                                  structure_diff.parse_markdown(new), **kw)


class StructureDiffTest(unittest.TestCase):
    def setUp(self):
        self.orig = read(BEFORE)
        self.good = read(AFTER)

    def mutate(self, old, new):
        self.assertIn(old, self.good)
        return diff_text(self.orig, self.good.replace(old, new, 1))

    def types(self, problems):
        return {p["type"] for p in problems}

    def test_good_rewrite_passes(self):
        self.assertEqual(diff_text(self.orig, self.good), [])

    def test_cli_exit_codes(self):
        ok = subprocess.run([sys.executable, os.path.join(SCRIPTS, "structure_diff.py"),
                             BEFORE, AFTER, "--json"], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertTrue(json.loads(ok.stdout)["ok"])
        bad = subprocess.run([sys.executable, os.path.join(SCRIPTS, "structure_diff.py"),
                              BEFORE, BEFORE + ".missing"], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)

    def test_merged_paragraphs_fail(self):
        p = self.mutate("Responses got faster.\n\nThe numbers", "Responses got faster. The numbers")
        self.assertEqual(self.types(p), {"structure"})

    def test_heading_text_locked_by_default(self):
        p = self.mutate("## Next steps", "## What comes next")
        self.assertEqual(self.types(p), {"structure"})
        self.assertEqual(diff_text(self.orig, self.good.replace("## Next steps", "## What comes next"),
                                   allow_heading_edits=True), [])

    def test_heading_level_always_locked(self):
        p = diff_text(self.orig, self.good.replace("## Next steps", "### Next steps"),
                      allow_heading_edits=True)
        self.assertEqual(self.types(p), {"structure"})

    def test_list_type_change_fails(self):
        p = self.mutate("1. Extend", "- Extend")
        self.assertEqual(self.types(p), {"structure"})

    def test_dropped_list_item_fails(self):
        p = self.mutate("2. Bring mean time to patch under 48 hours.\n", "")
        self.assertEqual(self.types(p), {"structure"})

    def test_table_shape_fails(self):
        p = self.mutate("| SRE |", "| SRE | extra |")
        self.assertEqual(self.types(p), {"structure"})

    def test_table_cell_wording_may_change(self):
        self.assertEqual(self.mutate("Tracked per service", "Tracked service by service"), [])

    def test_code_block_locked(self):
        p = self.mutate("--days 90", "--days 30")
        self.assertEqual(self.types(p), {"structure"})

    def test_number_changed_fails(self):
        p = self.mutate("in 3 days", "in three days")
        self.assertEqual(self.types(p), {"numbers"})
        self.assertIn("'3'", p[0]["detail"])

    def test_date_changed_fails(self):
        p = self.mutate("2027-01-15", "mid-January 2027")
        self.assertEqual(self.types(p), {"numbers"})

    def test_cve_id_changed_fails(self):
        p = self.mutate("CVE-2026-109619", "CVE-2026-109618")
        self.assertIn("numbers", self.types(p))

    def test_link_changed_fails(self):
        p = self.mutate("report.pdf)", "report)")
        self.assertEqual(self.types(p), {"links"})

    def test_citation_dropped_fails(self):
        p = self.mutate("details [1].", "details.")
        self.assertEqual(self.types(p), {"citations"})

    def test_inline_code_changed_fails(self):
        p = self.mutate("`status.py`", "the status script")
        self.assertEqual(self.types(p), {"inline_code"})

    def test_bold_removed_fails(self):
        p = self.mutate("**CVE-2026-109619**", "CVE-2026-109619")
        self.assertEqual(self.types(p), {"emphasis"})

    def test_reference_definition_locked(self):
        p = self.mutate("[1]: https://example.com/methodology", "[1]: https://example.com/m")
        self.assertEqual(self.types(p), {"structure"})

    def test_setext_and_nested_lists(self):
        doc = "Title\n=====\n\n- a 1\n  - b 2\n- c 3\n\n> quoted 4\n\n---\n\ntext 5\n"
        kinds = [(b["kind"], b.get("depth")) for b in structure_diff.parse_markdown(doc)]
        self.assertEqual(kinds, [("heading", None), ("item", 0), ("item", 1), ("item", 0),
                                 ("quote", None), ("rule", None), ("paragraph", None)])
        self.assertEqual(diff_text(doc, doc.replace("text 5", "other words 5")), [])
        self.assertEqual(self.types(diff_text(doc, doc.replace("  - b 2", "- b 2"))), {"structure"})


def make_docx(paragraphs):
    """paragraphs: list of (style or None, text, bold:bool, numbered:bool)."""
    W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = []
    for style, text, bold, numbered in paragraphs:
        ppr = ""
        if style or numbered:
            ppr = "<w:pPr>%s%s</w:pPr>" % (
                '<w:pStyle w:val="%s"/>' % style if style else "",
                '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>' if numbered else "")
        rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
        body.append('<w:p>%s<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r></w:p>' % (ppr, rpr, text))
    body.append("<w:tbl><w:tr><w:tc><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc>"
                "<w:tc><w:p><w:r><w:t>B 7</w:t></w:r></w:p></w:tc></w:tr></w:tbl>")
    xml = '<?xml version="1.0"?><w:document %s><w:body>%s</w:body></w:document>' % (W, "".join(body))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


class DocxTest(unittest.TestCase):
    def run_pair(self, a, b):
        d = tempfile.mkdtemp()
        pa, pb = os.path.join(d, "a.docx"), os.path.join(d, "b.docx")
        with open(pa, "wb") as f:
            f.write(make_docx(a))
        with open(pb, "wb") as f:
            f.write(make_docx(b))
        return structure_diff.compare(structure_diff.load(pa), structure_diff.load(pb))

    BASE = [("Heading1", "Results", False, False),
            (None, "We found 12 issues, highlighting gaps.", False, False),
            (None, "Fix them by Friday.", True, True)]

    def test_reworded_docx_passes(self):
        new = list(self.BASE)
        new[1] = (None, "We found 12 issues. That shows the gaps.", False, False)
        self.assertEqual(self.run_pair(self.BASE, new), [])

    def test_docx_style_and_numbers_checked(self):
        new = list(self.BASE)
        new[1] = (None, "We found a dozen issues.", False, False)
        self.assertEqual({p["type"] for p in self.run_pair(self.BASE, new)}, {"numbers"})
        new = list(self.BASE)
        new[2] = (None, "Fix them by Friday.", True, False)
        self.assertEqual({p["type"] for p in self.run_pair(self.BASE, new)}, {"structure"})
        new = list(self.BASE)
        new[2] = (None, "Fix them by Friday.", False, True)
        self.assertEqual({p["type"] for p in self.run_pair(self.BASE, new)}, {"emphasis"})


class StyleCheckTest(unittest.TestCase):
    def test_before_is_flagged_after_is_cleaner(self):
        mb, fb = style_check.analyse(structure_diff.load(BEFORE))
        ma, fa = style_check.analyse(structure_diff.load(AFTER))
        self.assertGreaterEqual(mb["stock_phrases"], 8)
        self.assertEqual(ma["stock_phrases"], 0)
        self.assertGreater(mb["em_dashes_per_100w"], ma["em_dashes_per_100w"])
        self.assertEqual(mb["ing_tails"], 2)
        self.assertEqual(ma["ing_tails"], 0)
        self.assertGreater(ma["sentence_len_cv"], mb["sentence_len_cv"])
        found = {f["text"].lower() for f in fb}
        self.assertTrue(any("delved into" in t for t in found))
        self.assertTrue(any("plays a crucial role" in t for t in found))

    def test_ignores_code_and_headings(self):
        doc = "# Leverage robust tapestry\n\n```\nleverage = robust\n```\n\nPlain words here.\n"
        m, f = style_check.analyse(structure_diff.parse_markdown(doc))
        self.assertEqual(m["stock_phrases"], 0)

    def test_cli_before_after(self):
        out = subprocess.run([sys.executable, os.path.join(SCRIPTS, "style_check.py"), BEFORE, AFTER],
                             capture_output=True, text=True, check=True).stdout
        self.assertIn("before", out)
        self.assertIn("stock_phrases_per_100w", out)


if __name__ == "__main__":
    unittest.main()
