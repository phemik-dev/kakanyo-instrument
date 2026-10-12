"""Execute model trials and collect blind manual reviews. No unearned auto-grading."""
import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from .core import ContractError, assert_external_release, new_state, validate_output
from .fixtures import SCENARIOS, generate_fixture
from .runtime import build_prompt
from .workspace import canonical, digest

INVARIANTS = {
    "T01": "evidence_independence", "T02": "uncertainty_conservation",
    "T03": "contradiction_preservation", "T04": "human_boundary",
    "T05": "recurrence_not_origin", "T06": "counterfactual_subtraction",
    "T07": "shadow_obligation", "T08": "reflexive_challenge",
}

def run_trial(test_id: str, adapter, model_label="unspecified") -> dict:
    """Run one *targeted* cycle, not a fake full 21-cycle case study."""
    case = generate_fixture(test_id)
    state = new_state(case)
    cycle = SCENARIOS[test_id]["cycle"]
    state["next_cycle"] = cycle  # Explicit synthetic isolated cycle stress test
    if not getattr(adapter, "local_only", False):
        assert_external_release(case)
    prompt = build_prompt(case, state, cycle)
    now = datetime.now(timezone.utc).isoformat()
    record = {"test_id": test_id, "cycle": cycle,
              "model_label": model_label, "timestamp": now,
              "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
              "corpus_sha256": digest(case["corpus"]),
              "challenge": SCENARIOS[test_id]["title"],
              "review_target": SCENARIOS[test_id]["gold"],
              "semantic_score": "NOT_REVIEWED"}
    try:
        raw = adapter.invoke(prompt)
        record["raw_output"] = raw
        record["validated_output"] = validate_output(case, raw, cycle)
        record["structural_result"] = "PASS"
    except Exception as exc:
        record["raw_output"] = None
        record["structural_result"] = "FAIL"
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record

def run_suite(adapter, model_label="unspecified") -> list:
    return [run_trial(test_id, adapter, model_label) for test_id in SCENARIOS]

def blind_trials(trials: list) -> list:
    """Random opaque trial IDs, with the private mapping retained separately by facilitator."""
    blinded = []
    for trial in trials:
        safe = {key: value for key, value in trial.items()
                if key not in {"model_label", "review_target", "test_id"}}
        safe["blind_id"] = secrets.token_hex(8)
        blinded.append(safe)
    return blinded

def add_review(trial: dict, reviewer: str, score: int, rationale: str, failures=None) -> dict:
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ContractError("Reviewer is required")
    if type(score) is not int or score not in (0, 1, 2):
        raise ContractError("Score must be 0, 1 or 2")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ContractError("A source-specific rationale is required")
    result = json.loads(json.dumps(trial))
    reviews = result.setdefault("reviews", [])
    if any(r["reviewer"] == reviewer for r in reviews):
        raise ContractError("Review cannot be silently overwritten")
    reviews.append({"reviewer": reviewer, "score": score,
                    "rationale": rationale, "failures": failures or [],
                    "at": datetime.now(timezone.utc).isoformat()})
    return result

def aggregate(trials: list) -> dict:
    result = {"total_trials": len(trials), "unreviewed": 0, "single_reviewed": 0,
              "double_reviewed": 0, "disagreements": [], "results": []}
    for trial in trials:
        reviews = trial.get("reviews", [])
        tid = trial.get("test_id", trial.get("blind_id"))
        if len(reviews) == 0:
            result["unreviewed"] += 1
        elif len(reviews) == 1:
            result["single_reviewed"] += 1
        else:
            result["double_reviewed"] += 1
            if len({r["score"] for r in reviews}) > 1:
                result["disagreements"].append(tid)
        result["results"].append({"trial": tid, "scores": [r["score"] for r in reviews],
                                  "structural": trial.get("structural_result")})
    result["portability_verdict"] = "NOT_ESTABLISHED"
    return result

def write_suite(directory, trials, name):
    root = Path(directory).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not isinstance(name, str) or not name.replace("-", "").replace("_", "").isalnum():
        raise ContractError("Run name must be alphanumeric with underscores/dashes")
    file = root / (name + ".json")
    if file.exists():
        raise ContractError("Cannot overwrite prior trial evidence")
    file.write_text(json.dumps(trials, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(file)
