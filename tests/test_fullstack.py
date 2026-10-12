"""Workspace/evidence/conformance/MCP end-to-end tests with synthetic data."""
import copy
import json
import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from kakanyo.adapters import OfflineAdapter
from kakanyo.conformance import add_review, aggregate, run_suite, run_trial, write_suite
from kakanyo.core import ContractError
from kakanyo.evidence import anchor, derivation_roots, verify_anchor, verify_claim_anchors
from kakanyo.fixtures import SCENARIOS, catalog, generate_fixture
from kakanyo.mcp import TOOLS, call_tool, process
from kakanyo.reporting import markdown, write_report
from kakanyo.workspace import Workspace

def synthetic():
    return generate_fixture("T01")

def supported_output(case):
    evidence=case["corpus"]["sources"][0]
    span=anchor(case,evidence["id"],"restart attempt")
    claim={"claim_id":"K1","statement":"Memo reports an attempted restart",
           "claim_type":"DIRECT","status":"candidate","evidence_refs":[evidence["id"]],
           "anchors":[span],"qualification":"","counterevidence":[],
           "counter_test":"Inspect independent service logs",
           "what_would_change_this":"The underlying memo proves fabricated"}
    return {"claims":[claim],"contradictions":[],
            "newly_open":["Success not independently verified"],"weakened_claims":[],
            "next_pressure_tests":["Obtain service logs"],
            "self_limitations":["Source identifies attempted restart only"]}

class SynthesisAdapter:
    local_only=True
    def __init__(self, reply): self.reply=reply
    def invoke(self,prompt):
        return copy.deepcopy(self.reply)

class EvidenceTests(unittest.TestCase):
    def test_all_synthetic_fixtures_valid(self):
        from kakanyo.core import validate_case
        for key in SCENARIOS:
            with self.subTest(key=key):
                case=generate_fixture(key)
                validate_case(case)
                self.assertEqual(len(derivation_roots(case)),len(case["corpus"]["sources"]))
    def test_t01_counted_as_one_lineage(self):
        case=synthetic()
        self.assertEqual(len(case["corpus"]["sources"]),22)
        self.assertEqual(len({s["independence_root"] for s in case["corpus"]["sources"]}),2)
        self.assertEqual(derivation_roots(case)["E20"],"MEMO")
    def test_incorrect_root_rejected(self):
        case=synthetic()
        case["corpus"]["sources"][-1]["independence_root"]="FRAUD"
        with self.assertRaises(ContractError):derivation_roots(case)
    def test_unknown_parent_rejected(self):
        case=synthetic();case["corpus"]["sources"][-1]["derived_from"]="NONE"
        with self.assertRaises(ContractError):derivation_roots(case)
    def test_parent_cycle_rejected(self):
        case=synthetic()
        case["corpus"]["sources"][0]["derived_from"]="E20"
        with self.assertRaises(ContractError):derivation_roots(case)
    def test_exact_span_and_tampering(self):
        case=synthetic();a=anchor(case,"S1","restart attempt")
        self.assertTrue(verify_anchor(case,a))
        invalid={**a,"start":a["start"]+1}
        with self.assertRaises(ContractError):verify_anchor(case,invalid)
    def test_anchor_hash_refuses_altered_source(self):
        case=synthetic();a=anchor(case,"S1","restart attempt")
        case["corpus"]["sources"][0]["text"]+=" altered"
        with self.assertRaises(ContractError):verify_anchor(case,a)
    def test_claim_span_must_cite_source(self):
        case=synthetic();o=supported_output(case)
        o["claims"][0]["evidence_refs"]=["S2"]
        with self.assertRaises(ContractError):verify_claim_anchors(case,o["claims"][0])
    def test_genuine_anchor_checks_dont_claim_semantic_support(self):
        case=synthetic();r=verify_claim_anchors(case,supported_output(case)["claims"][0])
        self.assertEqual(r["semantic_support"],"NOT_EVALUATED")

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.ws=Workspace(self.temp.name)
        self.case=synthetic()
        self.cid=self.case["corpus"]["corpus_id"]
        self.ws.import_case(self.case)
    def tearDown(self):self.temp.cleanup()
    def test_import_initial_state(self):
        self.assertEqual(self.ws.status(self.cid)["next_cycle"],1)
        self.assertTrue(self.ws.verify_history(self.cid)["chain_valid"])
    def test_duplicate_import_fails(self):
        with self.assertRaises(ContractError):self.ws.import_case(self.case)
    def test_full_case_21_cycles(self):
        for i in range(21):
            result=self.ws.execute(self.cid,OfflineAdapter())
            self.assertEqual(result["next_cycle"],i+2)
        with self.assertRaises(ContractError):self.ws.execute(self.cid,OfflineAdapter())
        self.assertEqual(self.ws.status(self.cid)["runs"],21)
        self.assertEqual(self.ws.verify_history(self.cid)["events_verified"],22)
    def test_single_real_shaped_claim_and_review(self):
        self.ws.execute(self.cid,SynthesisAdapter(supported_output(self.case)))
        result=self.ws.report(self.cid)
        self.assertEqual(result["claims"][0]["source_independence_count"],1)
        self.ws.review(self.cid,"K1","reviewer-A","uncertain","Only attempted restart supported")
        self.assertEqual(len(self.ws.reviews(self.cid)),1)
        with self.assertRaises(ContractError):
            self.ws.review(self.cid,"K1","reviewer-A","supported","Change it")
    def test_unknown_claim_review_blocked(self):
        with self.assertRaises(ContractError):
            self.ws.review(self.cid,"not-here","auditor","supported","No reference")
    def test_hold_resume_and_log(self):
        self.ws.hold(self.cid,"No decision yet")
        with self.assertRaises(ContractError):self.ws.execute(self.cid,OfflineAdapter())
        self.ws.resume(self.cid,"Confirmed synthetic scope")
        self.assertEqual(self.ws.execute(self.cid,OfflineAdapter())["runs"],1)
        self.assertEqual(self.ws.verify_history(self.cid)["events_verified"],4)
    def test_hash_chain_tamper_detected(self):
        with self.ws.connect() as conn:
            conn.execute("UPDATE events SET payload=? WHERE case_id=? AND seq=1",('{"x":"fake"}',self.cid))
        with self.assertRaises(ContractError):self.ws.verify_history(self.cid)
    def test_db_write_rejects_invalid_anchor(self):
        o=supported_output(self.case)
        o["claims"][0]["anchors"][0]["quote"]="HALLUCINATED"
        with self.assertRaises(ContractError):self.ws.execute(self.cid,SynthesisAdapter(o))
        self.assertEqual(self.ws.status(self.cid)["runs"],0)
    def test_cycle_collision_does_not_advance_twice(self):
        start=threading.Barrier(2)
        class SyncAdapter:
            local_only=True
            def invoke(self,prompt):
                start.wait(timeout=10)
                return OfflineAdapter().invoke(prompt)
        results=[]
        def work():
            try:self.ws.execute(self.cid,SyncAdapter());results.append("OK")
            except ContractError:results.append("CONFLICT")
        a=threading.Thread(target=work);b=threading.Thread(target=work)
        a.start();b.start();a.join(15);b.join(15)
        self.assertCountEqual(results,["OK","CONFLICT"])
        self.assertEqual(self.ws.status(self.cid)["runs"],1)
    def test_markdown_html_json_exports(self):
        self.ws.execute(self.cid,OfflineAdapter())
        report=self.ws.report(self.cid)
        self.assertIn("Kakanyo research dossier",markdown(report))
        for fmt in ("md","html","json"):
            file=Path(self.temp.name)/("report."+fmt)
            write_report(report,file,fmt)
            self.assertTrue(file.exists())
            with self.assertRaises(ContractError):write_report(report,file,fmt)
    def test_case_id_is_not_path(self):
        bad=synthetic();bad["corpus"]["corpus_id"]="../private"
        with self.assertRaises(ContractError):self.ws.import_case(bad)

class ConformanceTests(unittest.TestCase):
    def test_catalog_has_eight_challenges(self):
        self.assertEqual(len(catalog()),8)
    def test_offline_runs_no_semantic_score(self):
        results=run_suite(OfflineAdapter())
        self.assertEqual(len(results),8)
        self.assertTrue(all(r["structural_result"]=="PASS" for r in results))
        self.assertTrue(all(r["semantic_score"]=="NOT_REVIEWED" for r in results))
    def test_blinded_review_is_human_scored(self):
        trial=run_trial("T03",OfflineAdapter())
        self.assertEqual(aggregate([trial])["unreviewed"],1)
        trial=add_review(trial,"reviewer1",1,"Conflict not analysed")
        trial=add_review(trial,"reviewer2",0,"No disagreement mentioned")
        summary=aggregate([trial])
        self.assertEqual(summary["disagreements"],["T03"])
        self.assertEqual(summary["portability_verdict"],"NOT_ESTABLISHED")
    def test_reviewer_cannot_self_overwrite(self):
        trial=add_review(run_trial("T01",OfflineAdapter()),"auditor",0,"No analysis")
        with self.assertRaises(ContractError):add_review(trial,"auditor",2,"Pretend pass")
    def test_trial_file_does_not_overwrite(self):
        with TemporaryDirectory() as directory:
            write_suite(directory,run_suite(OfflineAdapter()),"trial1")
            with self.assertRaises(ContractError):
                write_suite(directory,run_suite(OfflineAdapter()),"trial1")

class MCPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.ws=Workspace(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def rpc(self,method,params=None):
        return process(self.ws,{"jsonrpc":"2.0","id":10,"method":method,"params":params or {}})
    def test_mcp_initialize(self):
        result=self.rpc("initialize")["result"]
        self.assertEqual(result["serverInfo"]["name"],"kakanyo-instrument")
    def test_tools_declared(self):
        tools=self.rpc("tools/list")["result"]["tools"]
        self.assertEqual(len(tools),10)
    def test_import_run_audit_via_mcp(self):
        case=synthetic()
        def tool(name,args):
            r=self.rpc("tools/call",{"name":"kakanyo_"+name,"arguments":args})["result"]
            self.assertFalse(r["isError"],r)
            return json.loads(r["content"][0]["text"])
        status=tool("import_case",{"case":case})
        self.assertEqual(status["next_cycle"],1)
        status=tool("run_cycle",{"case_id":status["case_id"]})
        self.assertEqual(status["next_cycle"],2)
        check=tool("verify_history",{"case_id":status["case_id"]})
        self.assertTrue(check["chain_valid"])
    def test_mcp_remote_fail_closed(self):
        old=os.environ.pop("KAKANYO_MCP_REMOTE_ENABLED",None)
        try:
            r=self.rpc("tools/call",{"name":"kakanyo_run_cycle",
                "arguments":{"case_id":"N/A","adapter":"openai-compatible"}})["result"]
            self.assertTrue(r["isError"])
        finally:
            if old is not None:os.environ["KAKANYO_MCP_REMOTE_ENABLED"]=old
    def test_mcp_incorrect_arguments_rejected(self):
        result=self.rpc("tools/call",{"name":"kakanyo_list_cases","arguments":{"unexpected":1}})["result"]
        self.assertTrue(result["isError"])
    def test_mcp_notification_has_no_response(self):
        self.assertIsNone(process(self.ws,{"jsonrpc":"2.0","method":"notifications/initialized"}))
    def test_mcp_unknown_method_returns_error(self):
        self.assertEqual(self.rpc("imaginary")["error"]["code"],-32601)

if __name__=="__main__":unittest.main()
