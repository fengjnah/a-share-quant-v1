"""python -m ai_trade.project_progress; formal metrics are always read-only."""
import argparse
import copy
import json
from decimal import Decimal
from pathlib import Path

from .core import METRICS, PlanError, calculate, load, propose, read_json, validate
from .render import board, roadmap


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", type=Path, default=METRICS)
    parser.add_argument("--render", action="store_true", help="explicitly regenerate only the two Markdown views")
    parser.add_argument("--check-docs", action="store_true")
    parser.add_argument("--baseline", type=Path, help="trusted prior metrics: enforce identical history/evidence prefix")
    parser.add_argument("--propose", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--simulate", nargs=3, metavar=("TASK", "ACCEPTANCE", "STATUS"))
    args = parser.parse_args(argv)
    try:
        if sum(bool(v) for v in [args.render, args.check_docs, args.propose, args.simulate]) > 1:
            raise PlanError("choose one mode")
        if bool(args.candidate) != bool(args.propose):
            raise PlanError("--propose and --candidate must be used together")
        data = load(args.metrics)
        if args.baseline:
            validate(data, baseline=load(args.baseline))
        if args.propose:
            if args.candidate.resolve() == args.metrics.resolve():
                raise PlanError("cannot overwrite formal metrics")
            candidate = propose(data, read_json(args.propose))
            with args.candidate.open("x", encoding="utf-8") as stream:
                json.dump(candidate, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
            print(json.dumps({"candidate": str(args.candidate), "before": calculate(data),
                              "after": calculate(candidate)}, ensure_ascii=False, indent=2))
            return 0
        if args.simulate:
            tid, aid, status = args.simulate
            if status not in {"FAIL", "UNVERIFIED", "NOT_RUN"}:
                raise PlanError("simulation may only remove evidence credit")
            from .core import snapshots
            event = copy.deepcopy(snapshots(data).get(tid))
            if not event or aid not in event["results"]:
                raise PlanError("unknown task/acceptance")
            event.update(state="PARTIAL", reason="read-only hypothetical failure; not an actual task update")
            event["results"][aid] = {"status": status, "evidence": []}
            # The simulation computes a scenario separately; the real task state never changes.
            # Dependent snapshots may retain their recorded states; report impacts without recertifying them.
            before = calculate(data)
            from .core import dependency_failures, recommendations
            changed = {**snapshots(data), tid: event}
            task = next(t for t in data["tasks"] if t["id"] == tid)
            recorded_state = snapshots(data)[tid]['state']
            new_score = (0 if recorded_state in {'PLANNED','REJECTED'} else
                         sum(a['weight'] for a in task['acceptance']
                             if event['results'][a['id']]['status']=='PASS'))
            lost = before['task_percent'][tid] - new_score
            stage = next(s for s in data["stages"] if s["id"] == task["stage"])
            delta = Decimal(str(stage["weight"])) * Decimal(str(task["weight"])) * Decimal(str(lost)) / 10000
            print(json.dumps({"hypothetical": True, "before_percent": before["project_percent"],
                              "after_percent": float(Decimal(str(before["project_percent"]))-delta),
                              "next": next(iter(recommendations(data, changed)), None),
                              "impacted_dependencies": {t["id"]: dependency_failures(t, changed) for t in data["tasks"] if dependency_failures(t, changed)}}, ensure_ascii=False, indent=2))
            return 0
        views = {"TASK_BOARD.md": board(data), "ROADMAP_V1_3.md": roadmap(data)}
        for name, content in views.items():
            target = args.metrics.parent / name
            if args.render:
                target.write_text(content, encoding="utf-8")
            if args.check_docs and (not target.exists() or target.read_text(encoding="utf-8") != content):
                raise PlanError(f"stale generated document: {name}; run --render after review")
        print(json.dumps(calculate(data), ensure_ascii=False, indent=2))
        return 0
    except (PlanError, OSError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "REJECTED", "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
