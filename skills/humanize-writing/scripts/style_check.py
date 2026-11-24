#!/usr/bin/env python3
"""Flag the stylistic habits that make prose read as machine-written.

Reads Markdown / plain text (or .docx) and scores only the prose: paragraphs,
list items, quotes and table cells. Code, links and headings are ignored.

Given one file it lists the findings with their block numbers. Given two
(BEFORE AFTER) it also prints a before/after table so a rewrite can be judged
on numbers, not on feel.

Usage:
  style_check.py FILE [--json]
  style_check.py BEFORE AFTER [--json]

Exit codes: 0 report printed, 2 bad input. The script never fails a rewrite on
its own; the metrics are guidance for the editor (see SKILL.md, step 5).
Standard library only (Python 3.8+).
"""
import argparse
import json
import math
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from structure_diff import INLINE_CODE, LINK, AUTOLINK, load  # noqa: E402

# Phrases that turn up far more in model output than in people's writing.
# Each maps to a short hint. Matching is case-insensitive on word boundaries.
STOCK_PHRASES = {
    r"delve(s|d)? into": "say what you actually looked at",
    r"(rich |vibrant |intricate )?tapestry": "drop the metaphor",
    r"in today'?s (fast-paced|digital|ever-changing|rapidly evolving) (world|landscape|age)": "cut the scene-setting",
    r"(it'?s|it is) (important|worth|crucial) (to note|noting|to remember|to mention) that": "just state the point",
    r"(plays?|playing) a (crucial|pivotal|vital|key|significant) role": "say what it does",
    r"navigat(e|es|ing) the (complexities|intricacies|landscape|challenges)": "name the actual difficulty",
    r"(ever-evolving|ever-changing|rapidly evolving) landscape": "name the field and what changed",
    r"in the realm of": "use 'in'",
    r"a testament to": "say what it shows",
    r"(serves|serve|serving) as a": "use 'is'",
    r"unlock(s|ing)? the (full )?(potential|power)": "say what improves",
    r"(embark|embarks|embarking) on (a|this|your) journey": "say what starts",
    r"harness(es|ing)? the power of": "use 'use'",
    r"(seamless(ly)?|robust|cutting-edge|game-?changer|groundbreaking|transformative)": "replace with a specific property",
    r"(leverage|leverages|leveraging|utili[sz]e|utili[sz]es|utili[sz]ing)": "use 'use'",
    r"(furthermore|moreover|additionally|consequently|nonetheless)\b,?": "often unnecessary; try no connector",
    r"in conclusion|in summary|to sum up|all in all|overall,": "the reader knows it's the end",
    r"(ultimately|essentially|fundamentally|notably|importantly),": "usually filler as a sentence opener",
    r"(whether you'?re|whether you are) an? [\w -]+ or an? ": "speak to the actual reader",
    r"not (just|only) (about )?[^.;]{1,40}?,? but (also )?": "state the main claim directly",
    r"(it'?s|this is) not [^.;]{1,40}?[;,—-]+ (it'?s|this is)": "contrast framing; state the claim",
    r"(a|the) (myriad|plethora|multitude) of": "give the number or say 'many'",
    r"(stands|stand) out as": "use 'is'",
    r"(foster|fosters|fostering|bolster|bolsters|bolstering|underscore|underscores|underscoring)": "use a plainer verb",
    r"(meticulous(ly)?|commendable|invaluable|paramount|nuanced|multifaceted|holistic)": "replace with a concrete detail",
    r"let'?s (dive|delve|take a (closer )?look)": "just start",
    r"(i hope this (helps|email finds you)|feel free to|don'?t hesitate to)": "assistant boilerplate",
    r"(at the end of the day|when it comes to|in order to)": "shorter: cut or use 'to'",
}

ING_TAIL = re.compile(r",\s+(highlighting|underscoring|emphasizing|showcasing|ensuring|reflecting|"
                      r"demonstrating|illustrating|signaling|paving|making it|allowing for|"
                      r"contributing to|fostering)\b", re.I)
TRICOLON = re.compile(r"\b[\w'-]+(?: [\w'-]+){0,3}, [\w'-]+(?: [\w'-]+){0,3},? (?:and|or) [\w'-]+", re.I)
EM_DASH = re.compile(r"—|(?<=\w) -- (?=\w)|(?<=\w) - (?=\w)")
SENT_SPLIT = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[A-Z0-9\"'(])")
WORD = re.compile(r"[A-Za-z0-9'][A-Za-z0-9'\-]*")
COMPILED = [(re.compile(r"\b" + p + r"(?!\w)", re.I), hint) for p, hint in STOCK_PHRASES.items()]

PROSE_KINDS = ("paragraph", "item", "quote", "table")


def clean(text):
    text = INLINE_CODE.sub(" code ", text)
    text = LINK.sub(lambda m: m.group(0).split("](")[0].lstrip("!["), text)
    text = AUTOLINK.sub(" link ", text)
    text = re.sub(r"[*_]{1,3}", "", text)
    return text


def sentences(text):
    return [s.strip() for s in SENT_SPLIT.split(text) if WORD.search(s)]


def analyse(blocks):
    prose = [(i, clean(b["text"])) for i, b in enumerate(blocks, 1)
             if b["kind"] in PROSE_KINDS and b.get("text", "").strip()]
    findings = []
    words = 0
    lengths = []
    openers = Counter()
    para_openers = Counter()
    em = tri = ing = phrases = 0
    for idx, text in prose:
        words += len(WORD.findall(text))
        sents = sentences(text)
        if blocks[idx - 1]["kind"] == "paragraph":
            lengths += [len(WORD.findall(s)) for s in sents]
            if sents:
                first = WORD.findall(sents[0])[:1]
                if first:
                    para_openers[first[0].lower()] += 1
        for s in sents:
            w = WORD.findall(s)[:2]
            if w:
                openers[" ".join(w).lower()] += 1
        for rx, hint in COMPILED:
            for m in rx.finditer(text):
                phrases += 1
                findings.append({"block": idx, "type": "stock-phrase",
                                 "text": m.group(0), "hint": hint})
        for m in EM_DASH.finditer(text):
            em += 1
        for m in ING_TAIL.finditer(text):
            ing += 1
            findings.append({"block": idx, "type": "ing-tail", "text": m.group(0).strip(", "),
                             "hint": "trailing participle commentary; make it its own claim or cut it"})
        for m in TRICOLON.finditer(text):
            tri += 1
            findings.append({"block": idx, "type": "triplet", "text": m.group(0),
                             "hint": "check the list really has three items; two or four is fine too"})
    mean = sum(lengths) / len(lengths) if lengths else 0.0
    sd = math.sqrt(sum((x - mean) ** 2 for x in lengths) / len(lengths)) if lengths else 0.0
    per100 = (lambda n: round(100.0 * n / words, 2) if words else 0.0)
    repeated = {k: v for k, v in openers.items() if v >= 3}
    rep_para = {k: v for k, v in para_openers.items() if v >= 3}
    metrics = {
        "words": words,
        "sentences": len(lengths),
        "sentence_len_mean": round(mean, 1),
        "sentence_len_sd": round(sd, 1),
        # coefficient of variation: people's prose usually lands around 0.5-0.8,
        # uniform machine prose often under 0.4
        "sentence_len_cv": round(sd / mean, 2) if mean else 0.0,
        "short_sentences_pct": round(100.0 * sum(1 for x in lengths if x <= 8) / len(lengths), 1) if lengths else 0.0,
        "long_sentences_pct": round(100.0 * sum(1 for x in lengths if x >= 30) / len(lengths), 1) if lengths else 0.0,
        "stock_phrases": phrases,
        "stock_phrases_per_100w": per100(phrases),
        "em_dashes_per_100w": per100(em),
        "triplets_per_100w": per100(tri),
        "ing_tails": ing,
        "repeated_sentence_openers": repeated,
        "repeated_paragraph_openers": rep_para,
    }
    return metrics, findings


# metric -> (direction, target) used to mark the before/after table
TARGETS = {
    "sentence_len_cv": ("up", 0.45),
    "stock_phrases_per_100w": ("down", 0.3),
    "em_dashes_per_100w": ("down", 0.5),
    "triplets_per_100w": ("down", 0.8),
    "ing_tails": ("down", 0),
}


def verdict(metric, value):
    if metric not in TARGETS:
        return ""
    d, t = TARGETS[metric]
    ok = value >= t if d == "up" else value <= t
    return "ok" if ok else ("aim >= %s" % t if d == "up" else "aim <= %s" % t)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="+", metavar="FILE")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if len(args.files) > 2:
        ap.error("give one file, or BEFORE and AFTER")
    try:
        results = [analyse(load(p)) for p in args.files]
    except (OSError, ValueError) as e:
        print("cannot read input: %s" % e, file=sys.stderr)
        return 2
    if args.json:
        out = {"files": [{"path": p, "metrics": m, "findings": f}
                         for p, (m, f) in zip(args.files, results)]}
        print(json.dumps(out, indent=2))
        return 0
    m, f = results[-1]
    label = "AFTER" if len(results) == 2 else os.path.basename(args.files[0])
    if len(results) == 2:
        b = results[0][0]
        print("%-28s %10s %10s  %s" % ("metric", "before", "after", ""))
        for k in m:
            if isinstance(m[k], dict):
                continue
            print("%-28s %10s %10s  %s" % (k, b[k], m[k], verdict(k, m[k])))
        print()
    else:
        for k, v in m.items():
            if not isinstance(v, dict):
                print("%-28s %10s  %s" % (k, v, verdict(k, v)))
        print()
    if m["repeated_sentence_openers"]:
        print("Repeated sentence openers: %s" % ", ".join(
            "%r x%d" % kv for kv in sorted(m["repeated_sentence_openers"].items(), key=lambda kv: -kv[1])))
    if m["repeated_paragraph_openers"]:
        print("Repeated paragraph openers: %s" % ", ".join(
            "%r x%d" % kv for kv in m["repeated_paragraph_openers"].items()))
    if f:
        print("Findings in %s (%d):" % (label, len(f)))
        for x in f:
            print("  block %-4d %-13s %-40r %s" % (x["block"], x["type"], x["text"][:40], x["hint"]))
    else:
        print("No phrase-level findings in %s." % label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
