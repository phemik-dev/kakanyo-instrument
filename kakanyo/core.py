"""Deterministic evidence contracts and custody; no semantic claim truth is certified."""
import copy
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

CLAIM_TYPES = {"DIRECT", "INFERENCE", "QUALIFY", "OPEN", "COUNTER_TEST"}
CLAIM_STATUSES = {"candidate", "contested", "open", "rejected"}
REQUIRED_CORPUS = {"corpus_id", "scope", "sources", "excluded_sources", "temporal_bounds",
                   "known_gaps", "permissions", "retrieval_limitations"}
REQUIRED_INQUIRY = {"object_of_inquiry", "central_question", "prohibited_inferences",
                    "desired_movement_depth", "decision_context", "stopping_condition"}
REQUIRED_CLAIM = {"claim_id", "statement", "claim_type", "evidence_refs", "qualification",
                  "counterevidence", "counter_test", "status", "what_would_change_this"}
OUTPUT_SECTIONS = ("claims", "contradictions", "newly_open", "weakened_claims",
                   "next_pressure_tests", "self_limitations")

class ContractError(ValueError):
    pass

def _require(record, fields, label):
    if not isinstance(record, dict):
        raise ContractError(f"{label} must be an object")
    missing = fields - set(record)
    if missing:
        raise ContractError(f"{label} missing fields: {sorted(missing)}")

def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())

def _strings(value, label):
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise ContractError(f"{label} must be a list of strings")

def validate_case(case: dict) -> None:
    _require(case, {"corpus", "inquiry"}, "case")
    corpus, inquiry = case["corpus"], case["inquiry"]
    _require(corpus, REQUIRED_CORPUS, "corpus")
    _require(inquiry, REQUIRED_INQUIRY, "inquiry")
    if not isinstance(corpus["sources"], list) or not corpus["sources"]:
        raise ContractError("At least one source required")
    for key in ("corpus_id", "scope", "permissions", "retrieval_limitations"):
        if not _nonempty(corpus[key]):
            raise ContractError(f"Nonempty corpus.{key} required")
    for key in ("object_of_inquiry", "central_question", "decision_context", "stopping_condition"):
        if not _nonempty(inquiry[key]):
            raise ContractError(f"Nonempty inquiry.{key} required")
    for key in ("excluded_sources", "known_gaps"):
        _strings(corpus[key], "corpus." + key)
    _strings(inquiry["prohibited_inferences"], "inquiry.prohibited_inferences")
    ids = set()
    for source in corpus["sources"]:
        _require(source, {"id", "text", "provenance", "independence_root", "permissions"}, "source")
        for key in ("id", "text", "provenance", "independence_root", "permissions"):
            if not _nonempty(source[key]):
                raise ContractError(f"Nonempty source.{key} required")
        if source["id"] in ids:
            raise ContractError("Duplicate source ID")
        ids.add(source["id"])

def independence_count(case: dict, evidence_refs: list[str]) -> int:
    sources = {s["id"]: s for s in case["corpus"]["sources"]}
    _strings(evidence_refs, "evidence_refs")
    if any(ref not in sources for ref in evidence_refs):
        raise ContractError("Unknown evidence reference")
    return len({sources[ref]["independence_root"] for ref in evidence_refs})

def validate_claim(case: dict, claim: dict) -> dict:
    _require(claim, REQUIRED_CLAIM, "claim")
    if not _nonempty(claim["claim_id"]) or not _nonempty(claim["statement"]):
        raise ContractError("Claim ID and statement required")
    if claim["claim_type"] not in CLAIM_TYPES or claim["status"] not in CLAIM_STATUSES:
        raise ContractError("Invalid claim type or status; this engine cannot canonise or approve")
    count = independence_count(case, claim["evidence_refs"])
    independence_count(case, claim["counterevidence"])
    if claim["claim_type"] == "DIRECT" and count == 0:
        raise ContractError("DIRECT claim requires source references")
    if claim["claim_type"] in {"INFERENCE", "QUALIFY"} and not _nonempty(claim["qualification"]):
        raise ContractError("Inference or qualification must acknowledge its limits")
    if not _nonempty(claim["what_would_change_this"]):
        raise ContractError("Synthesis reversibility required")
    if not isinstance(claim["counter_test"], str):
        raise ContractError("counter_test must be text")
    if claim.get("source_independence_count") not in (None, count):
        raise ContractError("Source independence cannot be forged by model output")
    cleaned = copy.deepcopy(claim)
    cleaned["source_independence_count"] = count
    return cleaned

def validate_output(case: dict, output: dict, cycle: int) -> dict:
    _require(output, set(OUTPUT_SECTIONS), "output")
    for name in OUTPUT_SECTIONS:
        if not isinstance(output[name], list):
            raise ContractError(f"Output {name} must be an array")
    for name in OUTPUT_SECTIONS[1:]:
        if not all(isinstance(x, str) and x.strip() for x in output[name]):
            raise ContractError(f"Output {name} must contain nonempty strings")
    claims = [validate_claim(case, c) for c in output["claims"]]
    if len({c["claim_id"] for c in claims}) != len(claims):
        raise ContractError("Duplicate claim IDs in cycle")
    cleaned = copy.deepcopy(output)
    cleaned["claims"] = claims
    cleaned["cycle"] = cycle
    return cleaned

def corpus_digest(case: dict) -> str:
    validate_case(case)
    payload = json.dumps(case, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def assert_external_release(case: dict) -> None:
    validate_case(case)
    allowed = {"synthetic", "approved-for-external-model"}
    if case["corpus"]["permissions"] not in allowed or any(
        s["permissions"] not in allowed for s in case["corpus"]["sources"]
    ):
        raise ContractError("External model access not approved for every source")

def new_state(case: dict) -> dict:
    validate_case(case)
    return {"version": "kakanyo-p0.1", "corpus_id": case["corpus"]["corpus_id"],
            "corpus_digest": corpus_digest(case), "claim_ledger": [],
            "contradiction_register": [], "open_register": [],
            "rejected_readings": [], "runs": [], "next_cycle": 1}

def apply_output(state: dict, case: dict, output: dict, cycle: int) -> dict:
    if state.get("corpus_id") != case["corpus"]["corpus_id"] or state.get("corpus_digest") != corpus_digest(case):
        raise ContractError("Evidence or corpus identity changed; start a revision, not silent resume")
    if state.get("next_cycle") != cycle or not (1 <= cycle <= 21):
        raise ContractError("Cycle out of order, already complete or out of bounds")
    checked = validate_output(case, output, cycle)
    previous = {c["claim_id"] for c in state["claim_ledger"]}
    if previous.intersection(c["claim_id"] for c in checked["claims"]):
        raise ContractError("Claim IDs cannot be reused")
    updated = copy.deepcopy(state)
    for claim in checked["claims"]:
        claim["cycle"] = cycle
        updated["claim_ledger"].append(claim)
        if claim["claim_type"] == "OPEN" or claim["status"] == "open":
            updated["open_register"].append({"cycle": cycle, "claim_id": claim["claim_id"],
                                             "reason": claim["qualification"]})
    updated["open_register"].extend({"cycle": cycle, "description": text} for text in checked["newly_open"])
    updated["contradiction_register"].extend({"cycle": cycle, "description": text} for text in checked["contradictions"])
    updated["rejected_readings"].extend({"cycle": cycle, "description": text} for text in checked["weakened_claims"])
    updated["runs"].append({"cycle": cycle, "timestamp": datetime.now(timezone.utc).isoformat(),
                            "output": checked})
    updated["next_cycle"] = cycle + 1
    return updated

def write_json_atomic(path, document) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".kakanyo-", suffix=".json", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(document, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def read_json(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
