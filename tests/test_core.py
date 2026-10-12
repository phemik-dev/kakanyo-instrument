"""Structural tests, not semantic or cross-model conformance."""
import copy
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from kakanyo.adapters import OfflineAdapter
from kakanyo.core import (
    ContractError, apply_output, assert_external_release, corpus_digest,
    independence_count, new_state, read_json, validate_case, validate_claim, validate_output,
    write_json_atomic,
)
from kakanyo.method import CYCLES, INVARIANTS, cycle_record
from kakanyo.runtime import build_prompt, execute_cycle

CASE = read_json(Path(__file__).resolve().parents[1] / "examples" / "synthetic-case.json")

def claim():
    return {"claim_id": "C-001", "statement": "Memo A reports an attempted restart",
            "claim_type": "DIRECT", "evidence_refs": ["S1", "S2"],
            "qualification": "", "counterevidence": [], "counter_test": "Verify run logs",
            "status": "candidate", "what_would_change_this": "Authenticated log disproving restart attempt"}

def output():
    return {"claims": [claim()], "contradictions": [], "newly_open": [],
            "weakened_claims": [], "next_pressure_tests": [], "self_limitations": []}

class CoreContracts(unittest.TestCase):
    def test_t01_echo_not_multiple_observations(self):
        self.assertEqual(independence_count(CASE, ["S1", "S2"]), 1)
    def test_independent_roots(self):
        self.assertEqual(independence_count(CASE, ["S1", "S3"]), 2)
    def test_unknown_source_rejected(self):
        with self.assertRaises(ContractError):
            validate_claim(CASE, {**claim(), "evidence_refs": ["fake"]})
    def test_missing_direct_evidence(self):
        with self.assertRaises(ContractError):
            validate_claim(CASE, {**claim(), "evidence_refs": []})
    def test_unqualified_inference(self):
        with self.assertRaises(ContractError):
            validate_claim(CASE, {**claim(), "claim_type": "INFERENCE"})
    def test_claim_cannot_forge_independence_count(self):
        with self.assertRaises(ContractError):
            validate_claim(CASE, {**claim(), "source_independence_count": 25})
    def test_canon_grant_forbidden(self):
        with self.assertRaises(ContractError):
            validate_claim(CASE, {**claim(), "status": "approved"})
    def test_reversibility_required(self):
        with self.assertRaises(ContractError):
            validate_claim(CASE, {**claim(), "what_would_change_this": ""})
    def test_counterevidence_unknown_ref_rejected(self):
        with self.assertRaises(ContractError):
            validate_claim(CASE, {**claim(), "counterevidence": ["bad-ref"]})
    def test_nonempty_claim_id(self):
        with self.assertRaises(ContractError):
            validate_claim(CASE, {**claim(), "claim_id": ""})
    def test_claim_type_rejected(self):
        with self.assertRaises(ContractError):
            validate_claim(CASE, {**claim(), "claim_type": "FACT"})
    def test_duplicate_claim_ids_rejected(self):
        duplicate = output()
        duplicate["claims"].append(copy.deepcopy(claim()))
        with self.assertRaises(ContractError):
            validate_output(CASE, duplicate, 1)
    def test_bad_output_section_type(self):
        with self.assertRaises(ContractError):
            validate_output(CASE, {**output(), "contradictions": "hidden"}, 1)
    def test_invalid_case_duplicate_sources(self):
        changed = copy.deepcopy(CASE)
        changed["corpus"]["sources"][1]["id"] = "S1"
        with self.assertRaises(ContractError):
            validate_case(changed)
    def test_invalid_case_empty_source(self):
        changed = copy.deepcopy(CASE)
        changed["corpus"]["sources"][0]["text"] = ""
        with self.assertRaises(ContractError):
            validate_case(changed)
    def test_unapproved_corpus_blocks_provider(self):
        changed = copy.deepcopy(CASE)
        changed["corpus"]["sources"][1]["permissions"] = "private"
        with self.assertRaises(ContractError):
            assert_external_release(changed)
    def test_synthetic_corpus_eligible_for_opt_in(self):
        assert_external_release(CASE)
    def test_digest_detects_mutation(self):
        changed = copy.deepcopy(CASE)
        changed["corpus"]["sources"][0]["text"] = "different"
        self.assertNotEqual(corpus_digest(CASE), corpus_digest(changed))
    def test_movement_registry_and_invariants(self):
        self.assertEqual(len(INVARIANTS), 12)
        self.assertEqual(len(CYCLES), 21)
        self.assertEqual(cycle_record(21)["movement"], "V")
    def test_nonsense_cycle_refused(self):
        with self.assertRaises(ValueError):
            cycle_record(22)
    def test_out_of_order_cycle_refused(self):
        with self.assertRaises(ContractError):
            apply_output(new_state(CASE), CASE, output(), 2)
    def test_claim_id_collision_across_cycles(self):
        state = apply_output(new_state(CASE), CASE, output(), 1)
        with self.assertRaises(ContractError):
            apply_output(state, CASE, output(), 2)
    def test_case_id_mismatch(self):
        state = new_state(CASE)
        state["corpus_id"] = "different"
        with self.assertRaises(ContractError):
            apply_output(state, CASE, output(), 1)
    def test_context_not_silently_truncated(self):
        changed = copy.deepcopy(CASE)
        changed["corpus"]["sources"][0]["text"] = "x" * 90000
        with self.assertRaises(ContractError):
            build_prompt(changed, new_state(changed), 1)
    def test_prompt_contains_source_and_method(self):
        prompt = build_prompt(CASE, new_state(CASE), 1)
        self.assertIn("S1", prompt)
        self.assertIn("evidence_independence", prompt)
        self.assertIn("CYCLE", prompt)
    def test_offline_invocation_durable_and_disclaimed(self):
        with TemporaryDirectory() as directory:
            case_path = Path(directory) / "case.json"
            state_path = Path(directory) / "state.json"
            write_json_atomic(case_path, CASE)
            result = execute_cycle(case_path, state_path, OfflineAdapter())
            self.assertEqual(result["cycle"], 1)
            checkpoint = read_json(state_path)
            self.assertEqual(checkpoint["next_cycle"], 2)
            self.assertIn("Custody/CLI", checkpoint["runs"][0]["output"]["self_limitations"][0])
    def test_changed_corpus_denies_resume(self):
        with TemporaryDirectory() as directory:
            case_path = Path(directory) / "case.json"
            state_path = Path(directory) / "state.json"
            write_json_atomic(case_path, CASE)
            execute_cycle(case_path, state_path, OfflineAdapter())
            changed = copy.deepcopy(CASE)
            changed["corpus"]["sources"][0]["text"] = "rewritten evidence"
            write_json_atomic(case_path, changed)
            with self.assertRaises(ContractError):
                execute_cycle(case_path, state_path, OfflineAdapter())
    def test_offline_state_is_not_a_semantic_result(self):
        with TemporaryDirectory() as directory:
            case_path = Path(directory) / "case.json"
            state_path = Path(directory) / "state.json"
            write_json_atomic(case_path, CASE)
            result = execute_cycle(case_path, state_path, OfflineAdapter())
            self.assertIn("No semantic correctness", result["note"])
    def test_no_output_on_provider_error(self):
        class BrokenProvider:
            local_only = True
            def invoke(self, prompt):
                raise RuntimeError("provider down")
        with TemporaryDirectory() as directory:
            case_path = Path(directory) / "case.json"
            state_path = Path(directory) / "state.json"
            write_json_atomic(case_path, CASE)
            with self.assertRaises(RuntimeError):
                execute_cycle(case_path, state_path, BrokenProvider())
            self.assertFalse(state_path.exists())

if __name__ == "__main__":
    unittest.main()
