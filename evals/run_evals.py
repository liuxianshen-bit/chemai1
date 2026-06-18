"""
ChemAI Eval Runner — runs all evals and prints unified report.

Usage:
    python evals/run_evals.py              # run all
    python evals/run_evals.py --unit       # unit tests only
    python evals/run_evals.py --classifier # classifier only
    python evals/run_evals.py --agent      # agent routing only
    python evals/run_evals.py --sse        # SSE streaming only
    python evals/run_evals.py --save       # save report to JSON
"""
import json
import sys
import os
import time
import argparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def run_all(save_report=False):
    from evals.conftest import EvalReport

    master = EvalReport()

    # ── Unit tests (no API needed) ──
    print("\n" + "=" * 60)
    print("  STAGE 1/4: Unit Tools (pure logic)")
    print("=" * 60)
    from evals.test_unit_tools import run as run_unit
    r1 = run_unit()
    master.results.extend(r1.results)

    # ── Classifier tests ──
    print("\n" + "=" * 60)
    print("  STAGE 2/4: Intent Classifier")
    print("=" * 60)
    from evals.test_classifier import run as run_classifier
    r2 = run_classifier()
    master.results.extend(r2.results)

    # ── Agent routing tests (needs DeepSeek API) ──
    print("\n" + "=" * 60)
    print("  STAGE 3/4: Agent Routing (end-to-end tool calling)")
    print("=" * 60)
    from evals.test_agent_routing import run as run_agent
    r3 = run_agent()
    master.results.extend(r3.results)

    # ── SSE streaming tests ──
    print("\n" + "=" * 60)
    print("  STAGE 4/4: SSE Streaming Structure")
    print("=" * 60)
    from evals.test_sse_streaming import run as run_sse
    r4 = run_sse()
    master.results.extend(r4.results)

    # ── Summary ──
    print(master.summary())

    if save_report:
        report_path = os.path.join(os.path.dirname(__file__), "eval_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total": len(master.results),
                "passed": sum(1 for r in master.results if r["passed"]),
                "failed": sum(1 for r in master.results if not r["passed"]),
                "results": master.results,
            }, f, ensure_ascii=False, indent=2)
        print(f"\nReport saved to: {report_path}")

    # Exit code: non-zero if any failures
    failures = sum(1 for r in master.results if not r["passed"])
    return 1 if failures > 0 else 0


def main():
    parser = argparse.ArgumentParser(description="ChemAI Eval Runner")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--classifier", action="store_true", help="Run classifier tests only")
    parser.add_argument("--agent", action="store_true", help="Run agent routing tests only")
    parser.add_argument("--sse", action="store_true", help="Run SSE streaming tests only")
    parser.add_argument("--save", action="store_true", help="Save report to JSON")
    args = parser.parse_args()

    # Check if any specific stage is requested
    specific = args.unit or args.classifier or args.agent or args.sse

    if not specific or args.unit:
        print("=== Unit Tools ===")
        from evals.test_unit_tools import run as run_unit
        r = run_unit()
        print(r.summary())

    if not specific or args.classifier:
        print("=== Classifier ===")
        from evals.test_classifier import run as run_classifier
        r = run_classifier()
        print(r.summary())

    if not specific or args.agent:
        print("=== Agent Routing ===")
        from evals.test_agent_routing import run as run_agent
        r = run_agent()
        print(r.summary())

    if not specific or args.sse:
        print("=== SSE Streaming ===")
        from evals.test_sse_streaming import run as run_sse
        r = run_sse()
        print(r.summary())

    if not specific:
        # Run full suite with unified report
        sys.exit(run_all(save_report=args.save))


if __name__ == "__main__":
    main()
