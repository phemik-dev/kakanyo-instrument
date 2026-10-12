"""Transactional local research workspace with custody hash chain and human review.

Local SQLite is the authority for this runtime; no network server is exposed.
"""
import copy
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .core import ContractError, apply_output, assert_external_release, corpus_digest, new_state, validate_case
from .evidence import derivation_roots, verify_claim_anchors
from .runtime import build_prompt

ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")

def canonical(data) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

def digest(data) -> str:
    return hashlib.sha256(canonical(data).encode("utf-8")).hexdigest()

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

class Workspace:
    """One workspace database, explicit case IDs and transaction-level concurrency checks."""
    def __init__(self, directory):
        self.root = Path(directory).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "kakanyo.sqlite3"
        self._init()

    def connect(self):
        conn = sqlite3.connect(str(self.db), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init(self):
        with self.connect() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS cases (
                id TEXT PRIMARY KEY, corpus_hash TEXT NOT NULL, spec TEXT NOT NULL,
                state TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
                hold_reason TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS events (
                case_id TEXT NOT NULL, seq INTEGER NOT NULL, kind TEXT NOT NULL,
                payload TEXT NOT NULL, prev_hash TEXT NOT NULL, event_hash TEXT NOT NULL,
                created_at TEXT NOT NULL, PRIMARY KEY(case_id,seq),
                FOREIGN KEY(case_id) REFERENCES cases(id))""")
            c.execute("""CREATE TABLE IF NOT EXISTS reviews (
                case_id TEXT NOT NULL, claim_id TEXT NOT NULL, reviewer TEXT NOT NULL,
                judgement TEXT NOT NULL, rationale TEXT NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(case_id,claim_id,reviewer),
                FOREIGN KEY(case_id) REFERENCES cases(id))""")

    @staticmethod
    def validate_id(case_id):
        if not isinstance(case_id, str) or not ID_PATTERN.fullmatch(case_id):
            raise ContractError("Case ID must be an ordinary 1–120-character identifier")
        return case_id

    def _event(self, conn, case_id, kind, payload):
        old = conn.execute("SELECT seq,event_hash FROM events WHERE case_id=? ORDER BY seq DESC LIMIT 1",
                           (case_id,)).fetchone()
        seq = 1 if old is None else old["seq"] + 1
        previous = "GENESIS" if old is None else old["event_hash"]
        created = utcnow()
        record = {"case_id": case_id, "seq": seq, "kind": kind,
                  "payload": payload, "prev_hash": previous, "created_at": created}
        event_hash = digest(record)
        conn.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?)",
                     (case_id, seq, kind, canonical(payload), previous, event_hash, created))
        return event_hash

    def import_case(self, case):
        validate_case(case)
        derivation_roots(case)
        cid = self.validate_id(case["corpus"]["corpus_id"])
        state = new_state(case)
        at = utcnow()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM cases WHERE id=?", (cid,)).fetchone():
                raise ContractError("Case exists. Create a new revision ID; no silent corpus replacement.")
            conn.execute("INSERT INTO cases VALUES (?,?,?,?,?,?,?,?)",
                         (cid, corpus_digest(case), canonical(case), canonical(state),
                          "active", None, at, at))
            self._event(conn, cid, "case.created", {"corpus_hash": corpus_digest(case)})
        return self.status(cid)

    def list_cases(self):
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT id,status,hold_reason,created_at,updated_at FROM cases ORDER BY created_at DESC")]

    def _record(self, conn, case_id):
        row = conn.execute("SELECT * FROM cases WHERE id=?", (self.validate_id(case_id),)).fetchone()
        if row is None:
            raise ContractError("Unknown case")
        return row

    def get_case(self, case_id):
        with self.connect() as conn:
            return json.loads(self._record(conn, case_id)["spec"])

    def get_state(self, case_id):
        with self.connect() as conn:
            return json.loads(self._record(conn, case_id)["state"])

    def status(self, case_id):
        with self.connect() as conn:
            row = self._record(conn, case_id)
            state = json.loads(row["state"])
            return {"case_id": case_id, "status": row["status"], "hold_reason": row["hold_reason"],
                    "next_cycle": state["next_cycle"], "runs": len(state["runs"]),
                    "claims": len(state["claim_ledger"]),
                    "open": len(state["open_register"]),
                    "contradictions": len(state["contradiction_register"]),
                    "corpus_hash": row["corpus_hash"]}

    def hold(self, case_id, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise ContractError("A nonempty hold reason is mandatory")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._record(conn, case_id)
            conn.execute("UPDATE cases SET status='hold',hold_reason=?,updated_at=? WHERE id=?",
                         (reason, utcnow(), case_id))
            self._event(conn, case_id, "case.hold", {"reason": reason})
        return self.status(case_id)

    def resume(self, case_id, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise ContractError("Resume rationale is mandatory")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._record(conn, case_id)
            if row["status"] != "hold":
                raise ContractError("Only held cases can be resumed")
            conn.execute("UPDATE cases SET status='active',hold_reason=NULL,updated_at=? WHERE id=?",
                         (utcnow(), case_id))
            self._event(conn, case_id, "case.resume", {"reason": reason})
        return self.status(case_id)

    def execute(self, case_id, adapter):
        """Network call occurs before DB write; optimistic cycle check prevents duplicate effects."""
        with self.connect() as conn:
            row = self._record(conn, case_id)
            if row["status"] != "active":
                raise ContractError("Case is on HOLD")
            case, state = json.loads(row["spec"]), json.loads(row["state"])
        if state["next_cycle"] > 21:
            raise ContractError("All 21 cycles completed")
        if not getattr(adapter, "local_only", False):
            assert_external_release(case)
        cycle = state["next_cycle"]
        prompt = build_prompt(case, state, cycle)
        response = adapter.invoke(prompt)
        updated = apply_output(state, case, response, cycle)
        for claim in updated["runs"][-1]["output"]["claims"]:
            verify_claim_anchors(case, claim)
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            fresh = self._record(conn, case_id)
            if fresh["status"] != "active" or json.loads(fresh["state"])["next_cycle"] != cycle:
                raise ContractError("Concurrent case update; do not duplicate the cycle")
            if fresh["corpus_hash"] != corpus_digest(case):
                raise ContractError("Corpus digest changed")
            conn.execute("UPDATE cases SET state=?,updated_at=? WHERE id=?",
                         (canonical(updated), utcnow(), case_id))
            self._event(conn, case_id, "cycle.completed", {
                "cycle": cycle, "response_hash": digest(response),
                "new_claims": len(response["claims"])})
        return self.status(case_id)

    def review(self, case_id, claim_id, reviewer, judgement, rationale):
        if judgement not in {"supported", "unsupported", "uncertain", "needs-test"}:
            raise ContractError("Invalid reviewer judgement")
        if not all(isinstance(v, str) and v.strip() for v in (claim_id, reviewer, rationale)):
            raise ContractError("Review requires claim, reviewer and rationale")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._record(conn, case_id)
            if claim_id not in {c["claim_id"] for c in json.loads(row["state"])["claim_ledger"]}:
                raise ContractError("Cannot review nonexistent claim")
            if conn.execute("SELECT 1 FROM reviews WHERE case_id=? AND claim_id=? AND reviewer=?",
                            (case_id,claim_id,reviewer)).fetchone():
                raise ContractError("Reviewer opinion exists; corrections require explicit event")
            conn.execute("INSERT INTO reviews VALUES (?,?,?,?,?,?)",
                         (case_id, claim_id, reviewer, judgement, rationale, utcnow()))
            self._event(conn, case_id, "claim.reviewed",
                        {"claim_id": claim_id, "reviewer": reviewer, "judgement": judgement,
                         "rationale": rationale})
        return self.reviews(case_id)

    def reviews(self, case_id):
        with self.connect() as conn:
            self._record(conn, case_id)
            return [dict(r) for r in conn.execute(
                "SELECT claim_id,reviewer,judgement,rationale,created_at FROM reviews WHERE case_id=? ORDER BY created_at",
                (case_id,))]

    def events(self, case_id):
        with self.connect() as conn:
            self._record(conn, case_id)
            return [dict(r) for r in conn.execute(
                "SELECT seq,kind,payload,prev_hash,event_hash,created_at FROM events WHERE case_id=? ORDER BY seq",
                (case_id,))]

    def verify_history(self, case_id):
        prior = "GENESIS"
        events = self.events(case_id)
        for event in events:
            record = {"case_id": case_id, "seq": event["seq"], "kind": event["kind"],
                      "payload": json.loads(event["payload"]), "prev_hash": event["prev_hash"],
                      "created_at": event["created_at"]}
            if event["prev_hash"] != prior or event["event_hash"] != digest(record):
                raise ContractError(f"Custody event {event['seq']} tampered or detached")
            prior = event["event_hash"]
        return {"case_id": case_id, "events_verified": len(events), "chain_valid": True}

    def report(self, case_id):
        case = self.get_case(case_id)
        state = self.get_state(case_id)
        return {"status": self.status(case_id), "question": case["inquiry"]["central_question"],
                "scope": case["corpus"]["scope"], "known_gaps": case["corpus"]["known_gaps"],
                "claims": state["claim_ledger"], "open": state["open_register"],
                "contradictions": state["contradiction_register"],
                "rejected_readings": state["rejected_readings"], "reviews": self.reviews(case_id),
                "limitations": ["Source-ID and span validation is not semantic claim support.",
                                "Human review and live model verification are not automatic."]}
