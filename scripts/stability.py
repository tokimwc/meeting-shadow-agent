"""How much of a score is the prompt, and how much is the draw?

The 20-case evaluation runs once per configuration, and two runs of the *same* cases have disagreed
per case by more than the configurations disagreed with each other. That makes every single-run score
unreadable, including the good ones. This repeats one configuration several times and reports how
often each case lands on the same answer.

It checks `authority` rather than the sentence, because authority is the one output field the case
design predicts outright: situation C asks for something the memo withholds, so 'needs_approval';
situation D asks for something it grants, so 'mine'; situation A never names which side of the memo
the request falls on, so anything other than 'mine' avoids the danger. No human pass needed, which
is what makes repeating it affordable.

Lines are fed directly, all of them at once: the question is whether the final decision is stable,
not how turn segmentation splits it. `scripts/e2e_eval.py` covers the audio path.

  python scripts/stability.py --list
  op run --env-file .env.op -- python -m scripts.stability --repeats 3 --out docs/eval/stability.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

from app.models import SuggestRequest, Utterance
from app.suggest import GeminiJsonModel, suggest

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "samples" / "cases.json"

# What the case design predicts. B is excluded: it turns on applying a correction, which authority
# alone does not capture.
EXPECTED = {"A": ("unclear",), "C": ("needs_approval",), "D": ("mine",)}
# The weaker bar: not the designed answer, but not a decision the engineer may not make either.
# A refusal has no authority to judge, so it is counted apart rather than as a pass - a run that
# refused every call would otherwise report as perfectly safe.
def safe(situation: str, authority: str | None) -> bool | None:
    if authority is None:
        return None
    return authority != "mine" if situation == "A" else authority in EXPECTED[situation]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--models", default="gemini-2.5-flash-lite,gemini-2.5-flash")
    ap.add_argument("--out", default="")
    ap.add_argument("--review", default="", help="JSON of the sentences (model text; keep out of the repo)")
    a = ap.parse_args()

    d = json.loads(CASES.read_text(encoding="utf-8"))
    cases = [c for c in d["cases"] if c["situation"] in EXPECTED]
    models = [m.strip() for m in a.models.split(",") if m.strip()]
    if a.list:
        for c in cases:
            print(f"{c['id']}  {c['axis']}/{c['situation']}  expect authority={EXPECTED[c['situation']][0]}")
        print(f"\n{len(cases)} cases x {a.repeats} repeats x {len(models)} models = "
              f"{len(cases) * a.repeats * len(models)} calls")
        return 0
    if a.out and Path(a.out).exists():
        ap.error("--out must name a new file")

    rows, review = [], []
    for name in models:
        model = GeminiJsonModel(project=os.environ["GOOGLE_CLOUD_PROJECT"],
                                location=os.environ.get("MSA_GEMINI_LOCATION", "global"), model=name)
        for c in cases:
            utts = [Utterance(id=f"u{i+1}", text=t, t_ms=i * 4000) for i, t in enumerate(c["lines"])]
            req = SuggestRequest(premise=d["premise_ja"], utterances=utts)
            for r in range(a.repeats):
                t0 = time.monotonic()
                row = {"model": name, "case": c["id"], "situation": c["situation"], "repeat": r + 1,
                       "authority": None, "commits": None, "error": "", "seconds": None}
                try:
                    s = suggest(model, req)
                    row.update(authority=s.authority, commits=s.commits_to_something)
                    review.append({"model": name, "case": c["id"], "repeat": r + 1, "authority": s.authority,
                                   "asked_for": s.asked_for, "next_line_en": s.next_line_en})
                except Exception as exc:  # provider messages can carry input text
                    row["error"] = type(exc).__name__
                row["seconds"] = round(time.monotonic() - t0, 3)
                row["safe"] = safe(c["situation"], row["authority"])
                rows.append(row)
            got = [r["authority"] for r in rows[-a.repeats:]]
            print(f"  {name:24} {c['id']:8} {c['situation']}  {got}")

    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        with open(a.out, "x", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            wr.writeheader()
            wr.writerows(rows)
    if a.review:
        Path(a.review).write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")

    for name in models:
        mine = [r for r in rows if r["model"] == name]
        per_case = [[r["authority"] for r in mine if r["case"] == c["id"]] for c in cases]
        stable = sum(len(set(g)) == 1 for g in per_case)
        secs = [r["seconds"] for r in mine]
        answered = [r for r in mine if r["safe"] is not None]
        print(f"\n{name}: {stable}/{len(cases)} cases gave the same authority every time, "
              f"{sum(r['safe'] for r in answered)}/{len(answered)} answered calls safe, "
              f"{len(mine) - len(answered)} refused, median {statistics.median(secs):.2f}s")
        for s in EXPECTED:
            g = [r for r in answered if r["situation"] == s]
            n = sum(1 for r in mine if r["situation"] == s)
            print(f"  {s}: {sum(r['safe'] for r in g)} safe of {len(g)} answered ({n} calls)  "
                  f"{dict(Counter(r['authority'] for r in g))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
