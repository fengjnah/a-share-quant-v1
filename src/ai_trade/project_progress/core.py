"""Validate and recalculate a reviewed plan. No database, SDK or network access."""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[3]
METRICS = ROOT / "docs/TASK_METRICS.json"
SCHEMA = ROOT / "docs/TASK_METRICS.schema.json"
STATES = ("PLANNED", "READY", "IN_PROGRESS", "BLOCKED", "PARTIAL", "PASS", "REJECTED")


class PlanError(ValueError):
    """Malformed, contradictory or unauditable management data."""


def digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                         allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise PlanError(f"duplicate JSON key: {k}")
        result[k] = v
    return result


def read_json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_pairs,
                          parse_constant=lambda v: (_ for _ in ()).throw(PlanError(f"illegal number: {v}")))
    except (OSError, ValueError) as exc:
        raise PlanError(f"cannot load {Path(path).name}: {exc}") from exc


def seal(event: dict, previous: str) -> dict:
    event = copy.deepcopy(event)
    event.pop("hash", None)
    event["previous_hash"] = previous
    event["hash"] = digest(event)
    return event


def snapshots(data: dict) -> dict:
    return {e["task_id"]: e for e in data["events"]}


def _total(values, label):
    if sum((Decimal(str(v)) for v in values), Decimal(0)) != 100:
        raise PlanError(f"{label} weights must sum to 100")


def validate(data: dict, schema: dict | None = None, baseline: dict | None = None) -> dict:
    schema = read_json(SCHEMA) if schema is None else schema
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data),
                    key=lambda e: str(list(e.path)))
    if errors:
        raise PlanError(f"schema {list(errors[0].path)}: {errors[0].message}")
    tasks = {t["id"]: t for t in data["tasks"]}
    stages = {s["id"]: s for s in data["stages"]}
    evidence = {e["id"]: e for e in data["evidence"]}
    if len(tasks) != len(data["tasks"]) or len(stages) != len(data["stages"]) or len(evidence) != len(data["evidence"]):
        raise PlanError("duplicate task/stage/evidence ID")
    _total((s["weight"] for s in stages.values()), "project")
    for s in stages.values():
        if any(d not in stages for d in s["depends_on"]):
            raise PlanError("unknown stage dependency")
        _total((t["weight"] for t in tasks.values() if t["stage"] == s["id"]), s["id"])
    for t in tasks.values():
        if t["stage"] not in stages:
            raise PlanError("unknown stage")
        acs = {a["id"]: a for a in t["acceptance"]}
        if t["estimated_hours"] and t["estimated_hours"]["low"] > t["estimated_hours"]["high"]:
            raise PlanError("estimated hours range is reversed")
        if len(acs) != len(t["acceptance"]):
            raise PlanError("duplicate acceptance ID")
        if not any(a['mandatory'] for a in acs.values()):
            raise PlanError("task needs at least one mandatory acceptance")
        _total((a["weight"] for a in acs.values()), t["id"])
        for dep in t["depends_on"]:
            if dep["task"] not in tasks or dep["task"] == t["id"]:
                raise PlanError("unknown/self task dependency")
            if not set(dep["acceptance"]) <= {a["id"] for a in tasks[dep["task"]]["acceptance"]}:
                raise PlanError("unknown dependency acceptance")
    def cycle(nodes, edges):
        done, active = set(), set()
        def visit(k):
            if k in active:
                raise PlanError("dependency cycle")
            if k in done:
                return
            active.add(k)
            for dep in edges(k):
                visit(dep)
            active.remove(k)
            done.add(k)
        for k in nodes:
            visit(k)
    cycle(tasks, lambda k: [d["task"] for d in tasks[k]["depends_on"]])
    cycle(stages, lambda k: stages[k]["depends_on"])
    previous = "0" * 64
    updated = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
    last_time = None
    prior = {}
    for seq, e in enumerate(data["events"], 1):
        raw = {k: v for k, v in e.items() if k != "hash"}
        if e["seq"] != seq or e["previous_hash"] != previous or digest(raw) != e["hash"]:
            raise PlanError("broken event sequence/hash chain")
        previous = e["hash"]
        time = datetime.fromisoformat(e["at"].replace("Z", "+00:00"))
        if time > updated or (last_time and time < last_time):
            raise PlanError("event/update timestamps out of order")
        last_time = time
        if e["task_id"] not in tasks:
            raise PlanError("unknown event task")
        t = tasks[e["task_id"]]
        acs = {a["id"]: a for a in t["acceptance"]}
        if set(e["results"]) != set(acs):
            raise PlanError("event must explicitly contain every acceptance result")
        refs = list(e["basis"]) + e["review"]["evidence"] + e["production"]["evidence"]
        for pr in e["prs"]:
            refs.extend(pr["evidence"])
            if pr["merged"] != (pr["state"] == "MERGED"):
                raise PlanError("contradictory PR merge state")
            if not pr["evidence"]:
                raise PlanError("PR state needs evidence")
        for aid, r in e["results"].items():
            refs.extend(r["evidence"])
            if r["status"] == "PASS" and (not r["evidence"] or not any(
                evidence.get(ref, {}).get("kind") in acs[aid]["evidence_kinds"] for ref in r["evidence"]
            )):
                raise PlanError("PASS requires evidence of the required type")
        if not set(refs) <= set(evidence):
            raise PlanError("unknown evidence reference")
        if e["review"]["status"] == "PASS" and not any(evidence[r]["kind"] == "review" for r in e["review"]["evidence"]):
            raise PlanError("independent review requires review evidence")
        if e["production"]["status"] == "PASS" and not any(evidence[r]["kind"] == "production" for r in e["production"]["evidence"]):
            raise PlanError("production approval requires separate evidence")
        passed = all(e["results"][a["id"]]["status"] == "PASS" for a in acs.values() if a["mandatory"])
        if e["state"] == "PASS" and (not passed or e["blockers"]):
            raise PlanError("PASS task has unpassed mandatory acceptance or blockers")
        if e["state"] == "BLOCKED" and not e["blockers"]:
            raise PlanError("BLOCKED needs a reason")
        if t["origin"] == "SUGGESTION" and e["state"] != "PLANNED":
            raise PlanError("a suggestion cannot be presented as an executed task")
        if e["state"] == "PLANNED" and any(r["status"] == "PASS" for r in e["results"].values()):
            raise PlanError("planned task cannot have passed acceptance")
        if e["state"] in {"READY", "IN_PROGRESS", "PASS"} and dependency_failures(t, prior):
            raise PlanError("new snapshot state contradicts dependencies at recording time")
        for aid, r in e["results"].items():
            if r["status"] == "PASS" and aid == "merge" and not any(p["merged"] for p in e["prs"]):
                raise PlanError("merge acceptance needs an actually merged PR")
            if r["status"] == "PASS" and aid == "review" and e["review"]["status"] != "PASS":
                raise PlanError("review acceptance is separate from implementation")
            if r["status"] == "PASS" and aid == "production" and e["production"]["status"] != "PASS":
                raise PlanError("production acceptance needs approval")
        prior[e["task_id"]] = e
    current = snapshots(data)
    if set(current) != set(tasks):
        raise PlanError("every task needs an explicit snapshot event")
    if baseline is not None:
        for key in ["plan_version", "stages", "tasks"]:
            if data[key] != baseline[key]:
                raise PlanError("plan/weights/acceptance changes require a separate reviewed plan revision")
        if data["events"][:len(baseline["events"])] != baseline["events"]:
            raise PlanError("historical events must remain an identical prefix")
        if data["evidence"][:len(baseline["evidence"])] != baseline["evidence"]:
            raise PlanError("historical evidence must remain an identical prefix")
    return data


def load(path: Path = METRICS) -> dict:
    return validate(read_json(path))


def dependency_failures(task: dict, current: dict) -> list[str]:
    missing = []
    for dep in task["depends_on"]:
        event = current.get(dep["task"])
        if not event or event["state"] in {"BLOCKED", "REJECTED"}:
            missing.append(dep["task"] + ":blocked/rejected")
        elif not dep["acceptance"]:
            if event["state"] != "PASS":
                missing.append(dep["task"] + ":mandatory")
        else:
            missing.extend(dep["task"] + ":" + a for a in dep["acceptance"]
                           if event["results"][a]["status"] != "PASS")
    return missing


def calculate(data: dict) -> dict:
    """Read-only calculation; failed/rejected tasks earn zero, partial tasks earn proven points."""
    validate(data)
    current = snapshots(data)
    scores = {}
    for t in data["tasks"]:
        e = current[t["id"]]
        scores[t["id"]] = (Decimal(0) if e["state"] in {"PLANNED", "REJECTED"} else
                            sum((Decimal(str(a["weight"])) for a in t["acceptance"]
                                 if e["results"][a["id"]]["status"] == "PASS"), Decimal(0)))
    stages, total = {}, Decimal(0)
    for s in data["stages"]:
        score = sum((Decimal(str(t["weight"])) * scores[t["id"]] / 100
                     for t in data["tasks"] if t["stage"] == s["id"]), Decimal(0))
        stages[s["id"]] = float(score)
        total += Decimal(str(s["weight"])) * score / 100
    candidates = recommendations(data, current)
    return {"project_percent": float(total), "stage_percent": stages,
            "task_percent": {k: float(v) for k, v in scores.items()},
            "state_counts": {s: sum(e["state"] == s for e in current.values()) for s in STATES},
            "next": candidates[0] if candidates else None,
            "blockers": [{"id": t["id"], "reasons": current[t["id"]]["blockers"],
                          "dependencies": dependency_failures(t, current)} for t in data["tasks"]
                         if current[t["id"]]["blockers"] or dependency_failures(t, current)]}


def recommendations(data: dict, current: dict) -> list[dict]:
    candidates = []
    for t in data["tasks"]:
        e = current[t["id"]]
        if e["state"] in {"PLANNED", "READY"} and not e["blockers"] and not dependency_failures(t, current):
            candidates.append({"id": t["id"], "title": t["title"], "origin": t["origin"],
                               "reason": t["recommendation_reason"], "rank": t["recommendation_rank"]})
    candidates.sort(key=lambda t: (t["rank"], t["id"]))
    return candidates


def propose(data: dict, feedback: dict) -> dict:
    """Make a candidate in memory. Formal metrics and all prior events remain unchanged."""
    validate(data)
    result = copy.deepcopy(data)
    event = copy.deepcopy(feedback["event"])
    result["evidence"].extend(copy.deepcopy(feedback.get("new_evidence", [])))
    event["seq"] = len(result["events"]) + 1
    result["events"].append(seal(event, result["events"][-1]["hash"]))
    result["updated_at"] = event["at"]
    validate(result, baseline=data)
    return result
