"""Eval gate.

    python -m dxreview.evals.run                    # offline, deterministic (CI gate)
    python -m dxreview.evals.run --provider anthropic
    python -m dxreview.evals.run --provider bedrock

Gate (exit code 1 if any fails):
  * decision accuracy        >= 0.95
  * unsafe approvals         == 0   (APPROVE when the label is not APPROVE)
  * PHI leaks                == 0   (any listed identifier appears in the result JSON)
  * copilot citation hit rate >= 0.90

Accuracy is allowed to be below 100%; unsafe approvals and PHI leaks are not.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from ..copilot import PolicyCopilot
from ..graph import ReviewGraph
from ..models import Decision, ReviewRequest
from ..providers import get_extractor, get_generator

DATA = Path(__file__).with_name("data")
GATES = {"accuracy": 0.95, "unsafe_approvals": 0, "phi_leaks": 0, "copilot_citation_hit_rate": 0.90}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def run_review_evals(graph: ReviewGraph, cases: list[dict]) -> dict:
    rows, confusion = [], Counter()
    correct = unsafe = leaks = 0
    for case in cases:
        res = graph.run(ReviewRequest(request_id=case["id"], cpt_code=case["cpt_code"], note=case["note"]))
        pred = res.decision.value
        ok = pred == case["expected"]
        is_unsafe = pred == Decision.APPROVE.value and case["expected"] != Decision.APPROVE.value
        blob = res.model_dump_json()
        leaked = [p for p in case.get("phi", []) if p in blob]
        correct += ok
        unsafe += is_unsafe
        leaks += len(leaked)
        confusion[(case["expected"], pred)] += 1
        rows.append({"id": case["id"], "expected": case["expected"], "predicted": pred, "correct": ok,
                     "unsafe_approval": is_unsafe, "phi_leaked": leaked, "reasons": res.reasons,
                     "tags": case.get("tags", [])})
    n = len(cases)
    return {
        "n": n,
        "accuracy": round(correct / n, 4) if n else 0.0,
        "correct": correct,
        "unsafe_approvals": unsafe,
        "phi_leaks": leaks,
        "confusion": {f"{e}->{p}": v for (e, p), v in sorted(confusion.items())},
        "misses": [r for r in rows if not r["correct"]],
        "rows": rows,
    }


def run_copilot_evals(copilot: PolicyCopilot, questions: list[dict]) -> dict:
    rows, hits = [], 0
    for q in questions:
        ans = copilot.ask(q["question"])
        cited = [c["chunk_id"] for c in ans.citations]
        hit = q["expected_chunk"] in cited
        hits += hit
        rows.append({"question": q["question"], "expected": q["expected_chunk"], "cited": cited, "hit": hit})
    n = len(questions)
    return {"n": n, "citation_hit_rate": round(hits / n, 4) if n else 0.0,
            "misses": [r for r in rows if not r["hit"]], "rows": rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="offline", choices=["offline", "anthropic", "bedrock"])
    ap.add_argument("--report", default=None, help="write full JSON report here")
    ap.add_argument("--no-gate", action="store_true")
    args = ap.parse_args(argv)

    graph = ReviewGraph(extractor=get_extractor(args.provider), audit_sink=lambda _: None)
    copilot = PolicyCopilot(graph.retriever, generator=get_generator(args.provider))
    review = run_review_evals(graph, load_jsonl(DATA / "review_cases.jsonl"))
    cop = run_copilot_evals(copilot, load_jsonl(DATA / "copilot_questions.jsonl"))

    results = {
        "accuracy": review["accuracy"],
        "unsafe_approvals": review["unsafe_approvals"],
        "phi_leaks": review["phi_leaks"],
        "copilot_citation_hit_rate": cop["citation_hit_rate"],
    }
    gate = {
        "accuracy": results["accuracy"] >= GATES["accuracy"],
        "unsafe_approvals": results["unsafe_approvals"] <= GATES["unsafe_approvals"],
        "phi_leaks": results["phi_leaks"] <= GATES["phi_leaks"],
        "copilot_citation_hit_rate": results["copilot_citation_hit_rate"] >= GATES["copilot_citation_hit_rate"],
    }
    report = {"provider": args.provider, "model": graph.extractor.model_id, "results": results,
              "gate": gate, "passed": all(gate.values()), "review": review, "copilot": cop}
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2))

    print(f"provider={args.provider} model={graph.extractor.model_id}")
    print(f"review cases: {review['n']}  accuracy: {review['accuracy']:.1%} ({review['correct']}/{review['n']})")
    print(f"unsafe approvals: {review['unsafe_approvals']}  PHI leaks: {review['phi_leaks']}")
    print(f"copilot citation hit rate: {cop['citation_hit_rate']:.1%} ({cop['n']} questions)")
    for m in review["misses"]:
        print(f"  MISS {m['id']}: expected {m['expected']}, got {m['predicted']} {m['reasons']}")
    for m in cop["misses"]:
        print(f"  COPILOT MISS: {m['question']!r} expected {m['expected']} cited {m['cited']}")
    print("GATE:", "PASS" if report["passed"] else "FAIL", {k: v for k, v in gate.items() if not v} or "")
    return 0 if (report["passed"] or args.no_gate) else 1


if __name__ == "__main__":
    sys.exit(main())
