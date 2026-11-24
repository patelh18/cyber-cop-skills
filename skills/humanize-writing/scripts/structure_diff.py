#!/usr/bin/env python3
"""Check that a rewritten document kept the original's structure and facts.

Compares two versions of a document (Markdown / plain text, or .docx) and
reports every structural or factual difference. Wording inside paragraphs,
list items and table cells may change; nothing else may.

What must match exactly:
  - block sequence: headings (level + text), paragraphs, list items (marker
    type + nesting), block quotes, tables (rows x columns), rules, code blocks
  - code blocks and inline code, byte for byte
  - link and image targets, in order
  - numbers, dates, percentages, versions, CVE/ID-like tokens (as a multiset)
  - citations and footnote markers ([1], [^note], (Smith, 2020))
  - emphasis span counts (bold / italic) per block, as a loose check

Usage:
  structure_diff.py ORIGINAL REWRITTEN [--allow-heading-edits] [--json]

Exit codes: 0 structure preserved, 1 differences found, 2 bad input.
Standard library only (Python 3.8+).
"""
import argparse
import json
import re
import sys
import zipfile
from collections import Counter
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------- Markdown

FENCE = re.compile(r"^(\s{0,3})(`{3,}|~{3,})(.*)$")
HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
SETEXT = re.compile(r"^\s{0,3}(=+|-+)\s*$")
HR = re.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$")
BULLET = re.compile(r"^(\s*)([-*+])\s+(\[[ xX]\]\s+)?(.*)$")
ORDERED = re.compile(r"^(\s*)(\d{1,9})([.)])\s+(.*)$")
QUOTE = re.compile(r"^\s{0,3}>\s?(.*)$")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
INDENT_CODE = re.compile(r"^( {4}|\t)")

INLINE_CODE = re.compile(r"(`+)(.+?)\1")
LINK = re.compile(r"!?\[(?:[^\]\\]|\\.)*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REF_DEF = re.compile(r"^\s{0,3}\[([^\]]+)\]:\s*(\S+)")
AUTOLINK = re.compile(r"<(https?://[^>]+)>|(?<![(<\w])(https?://[^\s)>\]]+)")
FOOTNOTE = re.compile(r"\[\^[^\]]+\]")
NUM_CITE = re.compile(r"\[\d+(?:\s*[,–-]\s*\d+)*\]")
AUTHOR_CITE = re.compile(r"\([A-Z][A-Za-z'\-]+(?: et al\.)?(?:,| and| &)[^()]*?\d{4}[a-z]?\)")
NUMBER = re.compile(
    r"(?<![\w.])("
    r"[A-Z]{2,}-\d[\w-]*"                         # CVE-2021-23337, RFC-7231, JIRA-12
    r"|v?\d+(?:\.\d+){2,}[\w.-]*"                   # versions 1.2.3, v8.4.27
    r"|\d{4}-\d{2}-\d{2}"                           # ISO dates
    r"|[$€£]?\d[\d,]*(?:\.\d+)?(?:%|[kKmMbB]\b)?"  # 1,200  3.5%  $40  10k
    r")"
)
BOLD = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
ITALIC = re.compile(r"(?<![*_\w])([*_])(?=\S)(.+?)(?<=\S)\1(?![*_\w])")


def _cells(row):
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", row)]


def parse_markdown(text):
    """Return (blocks, prose_lines). Each block is a dict with a 'kind'."""
    lines = text.splitlines()
    blocks = []
    i = 0
    para = []

    def flush():
        if para:
            blocks.append({"kind": "paragraph", "text": " ".join(s.strip() for s in para)})
            para.clear()

    while i < len(lines):
        line = lines[i]
        m = FENCE.match(line)
        if m:
            flush()
            fence = m.group(2)
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence[0] * len(fence)):
                body.append(lines[i])
                i += 1
            blocks.append({"kind": "code", "info": m.group(3).strip(), "text": "\n".join(body)})
            i += 1
            continue
        if not line.strip():
            flush()
            i += 1
            continue
        if REF_DEF.match(line):
            flush()
            r = REF_DEF.match(line)
            blocks.append({"kind": "refdef", "label": r.group(1), "text": r.group(2)})
            i += 1
            continue
        m = HEADING.match(line)
        if m:
            flush()
            blocks.append({"kind": "heading", "level": len(m.group(1)), "text": m.group(2)})
            i += 1
            continue
        if para and SETEXT.match(line) and not BULLET.match(line):
            level = 1 if line.strip().startswith("=") else 2
            heading_text = " ".join(s.strip() for s in para)
            para.clear()
            blocks.append({"kind": "heading", "level": level, "text": heading_text})
            i += 1
            continue
        if HR.match(line):
            flush()
            blocks.append({"kind": "rule", "text": ""})
            i += 1
            continue
        if TABLE_ROW.match(line) and i + 1 < len(lines) and TABLE_SEP.match(lines[i + 1]):
            flush()
            header = _cells(line)
            rows = [header]
            i += 2
            while i < len(lines) and TABLE_ROW.match(lines[i]):
                rows.append(_cells(lines[i]))
                i += 1
            blocks.append({"kind": "table", "shape": [len(r) for r in rows],
                           "text": " | ".join(" | ".join(r) for r in rows)})
            continue
        m = BULLET.match(line) or ORDERED.match(line)
        if m:
            flush()
            indent = len(m.group(1).expandtabs(4))
            if m.re is BULLET:
                marker = "task" if m.group(3) else "bullet"
                body = m.group(4)
            else:
                marker = "ordered" + m.group(3)
                body = m.group(4)
            item = [body]
            i += 1
            # lazy continuation lines belong to the item
            while i < len(lines) and lines[i].strip() and not (
                    BULLET.match(lines[i]) or ORDERED.match(lines[i]) or HEADING.match(lines[i])
                    or FENCE.match(lines[i]) or QUOTE.match(lines[i])):
                item.append(lines[i].strip())
                i += 1
            blocks.append({"kind": "item", "marker": marker, "depth": indent // 2,
                           "text": " ".join(item)})
            continue
        m = QUOTE.match(line)
        if m:
            flush()
            body = []
            while i < len(lines) and QUOTE.match(lines[i]):
                body.append(QUOTE.match(lines[i]).group(1))
                i += 1
            blocks.append({"kind": "quote", "text": " ".join(b.strip() for b in body)})
            continue
        if not para and INDENT_CODE.match(line) and (not blocks or blocks[-1]["kind"] != "item"):
            body = []
            while i < len(lines) and (INDENT_CODE.match(lines[i]) or not lines[i].strip()):
                body.append(lines[i])
                i += 1
            blocks.append({"kind": "code", "info": "indented", "text": "\n".join(body).rstrip()})
            continue
        para.append(line)
        i += 1
    flush()
    return blocks


# -------------------------------------------------------------------- docx

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _ptext(p):
    out = []
    for node in p.iter():
        if node.tag == W + "t" and node.text:
            out.append(node.text)
        elif node.tag == W + "tab":
            out.append("\t")
        elif node.tag in (W + "br", W + "cr"):
            out.append("\n")
    return "".join(out)


def parse_docx(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        rels = {}
        if "word/_rels/document.xml.rels" in z.namelist():
            for rel in ET.fromstring(z.read("word/_rels/document.xml.rels")):
                rels[rel.get("Id")] = rel.get("Target")
    body = root.find(W + "body")
    blocks = []

    def para_block(p):
        ppr = p.find(W + "pPr")
        style, numbered, level = "", False, 0
        if ppr is not None:
            ps = ppr.find(W + "pStyle")
            style = ps.get(W + "val") if ps is not None else ""
            num = ppr.find(W + "numPr")
            if num is not None:
                numbered = True
                ilvl = num.find(W + "ilvl")
                level = int(ilvl.get(W + "val")) if ilvl is not None else 0
        text = _ptext(p)
        links = [rels.get(h.get(R + "id"), h.get(W + "anchor") or "")
                 for h in p.iter(W + "hyperlink")]
        bold = sum(1 for r in p.iter(W + "r") if r.find(W + "rPr/" + W + "b") is not None)
        italic = sum(1 for r in p.iter(W + "r") if r.find(W + "rPr/" + W + "i") is not None)
        hm = re.match(r"(?i)heading\s*(\d)|title", style or "")
        if hm:
            kind, lvl = "heading", int(hm.group(1) or 0)
        elif numbered or (style or "").lower().startswith("list"):
            kind, lvl = "item", level
        elif not text.strip():
            kind, lvl = "empty", 0
        else:
            kind, lvl = "paragraph", 0
        b = {"kind": kind, "style": style, "text": text, "links": links,
             "fmt": {"bold_runs": bool(bold), "italic_runs": bool(italic)}}
        if kind == "heading":
            b["level"] = lvl
        if kind == "item":
            b["depth"], b["marker"] = lvl, "list"
        return b

    for child in body:
        if child.tag == W + "p":
            blocks.append(para_block(child))
        elif child.tag == W + "tbl":
            rows = child.findall(W + "tr")
            shape = [len(r.findall(W + "tc")) for r in rows]
            text = " | ".join(_ptext(p) for p in child.iter(W + "p"))
            links = [rels.get(h.get(R + "id"), "") for h in child.iter(W + "hyperlink")]
            blocks.append({"kind": "table", "shape": shape, "text": text, "links": links})
    return blocks


# ---------------------------------------------------------------- compare

def facts(text, strip_code=True):
    """Tokens that must survive a rewrite unchanged (as multisets)."""
    code = [m.group(2) for m in INLINE_CODE.finditer(text)]
    if strip_code:
        text = INLINE_CODE.sub(" ", text)
    links = [m.group(1) for m in LINK.finditer(text)]
    bare = re.sub(LINK, " ", text)
    links += [a or b for a, b in AUTOLINK.findall(bare)]
    no_links = AUTOLINK.sub(" ", bare)
    cites = FOOTNOTE.findall(no_links) + NUM_CITE.findall(no_links) + AUTHOR_CITE.findall(no_links)
    no_cites = NUM_CITE.sub(" ", FOOTNOTE.sub(" ", no_links))
    nums = [n.rstrip(".,").replace(",", "") for n in NUMBER.findall(no_cites)]
    return {"inline_code": code, "links": links, "citations": cites, "numbers": nums}


def emphasis(text):
    t = INLINE_CODE.sub(" ", text)
    return {"bold": len(BOLD.findall(t)), "italic": len(ITALIC.findall(BOLD.sub(" ", t)))}


def describe(b):
    k = b["kind"]
    if k == "heading":
        return "H%d %r" % (b["level"], b["text"][:60])
    if k == "item":
        return "%s item (depth %d) %r" % (b["marker"], b["depth"], b["text"][:40])
    if k == "table":
        return "table %dx%s" % (len(b["shape"]), "/".join(map(str, sorted(set(b["shape"])))))
    if k == "code":
        return "code block (%s)" % (b.get("info") or "plain")
    return "%s %r" % (k, b.get("text", "")[:40])


def signature(b, allow_heading_edits):
    k = b["kind"]
    if k == "heading":
        return (k, b["level"]) if allow_heading_edits else (k, b["level"], b["text"].strip())
    if k == "item":
        return (k, b["marker"], b["depth"])
    if k == "table":
        return (k, tuple(b["shape"]))
    if k in ("code", "refdef"):
        return (k, b.get("info", b.get("label")), b["text"])
    if "style" in b:
        return (k, b["style"])
    return (k,)


def compare(orig, new, allow_heading_edits=False):
    problems = []
    so = [signature(b, allow_heading_edits) for b in orig]
    sn = [signature(b, allow_heading_edits) for b in new]
    if so != sn:
        # find first divergence for a precise message
        n = min(len(so), len(sn))
        idx = next((i for i in range(n) if so[i] != sn[i]), n)
        if idx < n:
            problems.append({"type": "structure", "block": idx + 1,
                             "detail": "block %d was %s, now %s" % (
                                 idx + 1, describe(orig[idx]), describe(new[idx]))})
        else:
            problems.append({"type": "structure", "block": idx + 1,
                             "detail": "block count changed: %d -> %d (first extra/missing: %s)" % (
                                 len(so), len(sn),
                                 describe((orig if len(so) > len(sn) else new)[idx]))})
        return problems  # block-by-block facts are meaningless once misaligned

    for i, (a, b) in enumerate(zip(orig, new), 1):
        if a["kind"] in ("code", "refdef", "rule", "empty"):
            continue
        fa, fb = facts(a["text"]), facts(b["text"])
        if "links" in a:  # docx hyperlinks
            fa["links"] = fa["links"] + a["links"]
            fb["links"] = fb["links"] + b.get("links", [])
        for key in ("inline_code", "links", "citations"):
            if fa[key] != fb[key]:
                problems.append({"type": key, "block": i, "detail": "%s: %s -> %s" % (
                    describe(a), fa[key], fb[key])})
        if Counter(fa["numbers"]) != Counter(fb["numbers"]):
            lost = list((Counter(fa["numbers"]) - Counter(fb["numbers"])).elements())
            added = list((Counter(fb["numbers"]) - Counter(fa["numbers"])).elements())
            problems.append({"type": "numbers", "block": i, "detail": "%s: lost %s, added %s" % (
                describe(a), lost, added)})
        if "fmt" in a:
            if a["fmt"] != b.get("fmt"):
                problems.append({"type": "emphasis", "block": i,
                                 "detail": "%s: bold/italic runs %s -> %s" % (
                                     describe(a), a["fmt"], b.get("fmt"))})
        else:
            ea, eb = emphasis(a["text"]), emphasis(b["text"])
            if ea != eb:
                problems.append({"type": "emphasis", "block": i, "detail": "%s: %s -> %s" % (
                    describe(a), ea, eb)})
    return problems


def load(path):
    if path.lower().endswith(".docx"):
        return parse_docx(path)
    with open(path, encoding="utf-8") as f:
        return parse_markdown(f.read())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("original")
    ap.add_argument("rewritten")
    ap.add_argument("--allow-heading-edits", action="store_true",
                    help="let heading wording change (level and position still must match)")
    ap.add_argument("--json", action="store_true", help="print a JSON report")
    args = ap.parse_args(argv)
    if args.original.lower().endswith(".docx") != args.rewritten.lower().endswith(".docx"):
        print("both files must be the same format", file=sys.stderr)
        return 2
    try:
        orig, new = load(args.original), load(args.rewritten)
    except (OSError, zipfile.BadZipFile, KeyError, ET.ParseError) as e:
        print("cannot read input: %s" % e, file=sys.stderr)
        return 2
    problems = compare(orig, new, args.allow_heading_edits)
    kinds = Counter(b["kind"] for b in orig)
    if args.json:
        print(json.dumps({"ok": not problems, "blocks": len(orig), "block_kinds": kinds,
                          "problems": problems}, indent=2))
    else:
        summary = ", ".join("%d %s" % (v, k) for k, v in sorted(kinds.items()))
        if not problems:
            print("OK: structure and facts preserved (%d blocks: %s)" % (len(orig), summary))
        else:
            print("FAIL: %d difference(s)" % len(problems))
            for p in problems:
                print("  [%s] %s" % (p["type"], p["detail"]))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
