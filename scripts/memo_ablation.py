"""Does the authority memo actually change the suggestion, or is the prompt just cautious?

Every case in the 20-case evaluation shares one memo, so nothing there separates the memo's effect
from a prompt that defers by habit. This runs the same utterances past several memos and records what
comes back.

It feeds the scripted lines from samples/cases.json straight in as utterances rather than streaming
the audio. That is deliberate: the question is what the memo does to the suggestion, and putting
speech recognition in the path would mix transcription error into the answer. It also makes the run
free and repeatable. What it does not test is the pipeline — `scripts/e2e_eval.py` does that.

Situations C and D are the ones where the memo decides the answer: C asks for something the shipped
memo withholds, D asks for something it grants. A and B turn on what was said rather than on who may
agree to it, so they are not run here.

  python scripts/memo_ablation.py --list            # the memos and cases, no provider calls
  op run --env-file .env.op -- python -m scripts.memo_ablation --out docs/eval/memo.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

from app.models import SuggestRequest, Utterance
from app.suggest import GeminiJsonModel, JsonModel, suggest

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "samples" / "cases.json"

# The shipped memo, then the same engineer with the boundary moved. If the memo is doing work, the
# suggestion for one utterance should differ across these; if it is not, they will all read alike.
MEMOS: dict[str, str] = {
    "shipped": json.loads(CASES.read_text(encoding="utf-8"))["premise_ja"],
    "narrow": "自分は実装担当。staging 検証を含め、どの環境の合意にも社内確認が必要。納期・スコープ変更・追加工数の約束も社内確認が必要。",
    "broad": "自分は実装担当。staging 検証も本番反映も自分の裁量で合意できる。納期の約束だけは社内確認が必要。",
    "none": "",
}


def selected(cases: list[dict]) -> list[dict]:
    return [c for c in cases if c["situation"] in ("C", "D")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="print the memos and cases, make no calls")
    ap.add_argument("--out", default="", help="CSV of measurements (no model text)")
    ap.add_argument("--review", default="", help="JSON of the suggestions, for the human pass")
    a = ap.parse_args()

    cases = selected(json.loads(CASES.read_text(encoding="utf-8"))["cases"])
    if a.list:
        for name, memo in MEMOS.items():
            print(f"[{name}] {memo or '(no memo)'}")
        print()
        for c in cases:
            print(f"{c['id']}  {c['axis']}/{c['situation']}  {c['lines'][0]}")
        print(f"\n{len(cases)} cases x {len(MEMOS)} memos = {len(cases) * len(MEMOS)} calls")
        return 0

    if a.out and Path(a.out).exists():
        ap.error("--out must name a new file")

    model: JsonModel = GeminiJsonModel(
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("MSA_GEMINI_LOCATION", "global"),
        model=os.environ.get("MSA_GEMINI_MODEL", "gemini-2.5-flash-lite"))

    rows, review = [], []
    for c in cases:
        utterances = [Utterance(id=f"u{i+1}", text=t, t_ms=i * 4000) for i, t in enumerate(c["lines"])]
        for name, memo in MEMOS.items():
            row = {"case": c["id"], "axis": c["axis"], "situation": c["situation"], "memo": name,
                   "authority": None, "asked_for_len": None, "commits": None, "unconfirmed": None, "error": ""}
            try:
                s = suggest(model, SuggestRequest(premise=memo, utterances=utterances))
                row.update(authority=s.authority, asked_for_len=len(s.asked_for),
                           commits=s.commits_to_something, unconfirmed=len(s.unconfirmed))
                review.append({"case": c["id"], "memo": name, "heard": c["lines"],
                               "asked_for": s.asked_for, "authority": s.authority,
                               "next_line_en": s.next_line_en, "summary_ja": s.summary_ja,
                               "unconfirmed": [u.item for u in s.unconfirmed]})
            except Exception as exc:  # provider messages can carry input text
                row["error"] = type(exc).__name__
            rows.append(row)
            print(f"  {c['id']:8} {name:8} {str(row['authority']):14} commits={row['commits']} {row['error']}")

    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        with open(a.out, "x", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            wr.writeheader()
            wr.writerows(rows)
    if a.review:
        Path(a.review).write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")

    # Whether the memo mattered is a judgement about the sentences, not a number this script can emit.
    print(f"\n{len(rows)} calls, {sum(bool(r['error']) for r in rows)} errors. "
          f"Read the --review dump: the question is whether the same utterance gets a different answer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
