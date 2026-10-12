"""Source ingestion, long evidence retrieval, cycle design and local HTTP integration."""
import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from kakanyo.adapters import LocalOllamaAdapter, ProviderError
from kakanyo.core import ContractError, new_state
from kakanyo.evidence import derivation_roots
from kakanyo.fixtures import generate_fixture
from kakanyo.http_service import create_server
from kakanyo.ingest import case_from_directory
from kakanyo.method import cycle_instruction
from kakanyo.retrieval import select_evidence
from kakanyo.runtime import build_retrieved_prompt
from kakanyo.workspace import Workspace

class IntakeTests(unittest.TestCase):
    def test_document_folder_preserves_privacy_and_duplicates(self):
        with TemporaryDirectory() as tmp:
            Path(tmp,"a.txt").write_text("A long test memo.",encoding="utf-8")
            Path(tmp,"b.md").write_text("A long test memo.",encoding="utf-8")
            Path(tmp,"c.html").write_text("<html><script>bad()</script><body>Independent note</body></html>",encoding="utf-8")
            case=case_from_directory(tmp,"test-docs","What do the notes say?","Synthetic test")
            self.assertEqual(case["corpus"]["permissions"],"private")
            self.assertEqual(len(case["corpus"]["sources"]),3)
            self.assertEqual(case["corpus"]["sources"][0]["independence_root"],
                             case["corpus"]["sources"][1]["independence_root"])
            self.assertNotIn("bad()",case["corpus"]["sources"][2]["text"])
            with TemporaryDirectory() as db:
                ws=Workspace(db);ws.import_case(case)
                with self.assertRaises(ContractError):
                    ws.execute("test-docs",type("Remote",(),{"local_only":False,"invoke":lambda x,y:{}})())
    def test_hidden_document_ignored(self):
        with TemporaryDirectory() as tmp:
            Path(tmp,".env").write_text("secret",encoding="utf-8")
            Path(tmp,"a.txt").write_text("Safe fixture",encoding="utf-8")
            case=case_from_directory(tmp,"test-hidden","What happened?","Test")
            self.assertEqual(len(case["corpus"]["sources"]),1)
    def test_unapproved_type_rejected(self):
        with TemporaryDirectory() as tmp:
            Path(tmp,"a.txt").write_text("Content",encoding="utf-8")
            with self.assertRaises(ContractError):
                case_from_directory(tmp,"test","Question","Scope","public")

class RetrievalTests(unittest.TestCase):
    def test_large_source_is_excerpted_with_disclosure(self):
        case=generate_fixture("T03")
        case["corpus"]["sources"][0]["text"]="irrelevant " * 12000 + "board quorum failure" + " filler"*2000
        focused,manifest=select_evidence(case,"quorum failure",budget=1200)
        self.assertEqual(manifest["strategy"],"lexical-partial")
        self.assertTrue(manifest["clipped"])
        self.assertIn("quorum failure",focused["corpus"]["sources"][0]["text"])
        self.assertEqual(case["corpus"]["sources"][0]["text"][:10],"irrelevant")
        state=new_state(case)
        state["next_cycle"]=7
        prompt,rec=build_retrieved_prompt(case,state,7,budget=1200)
        self.assertIn("RETRIEVAL DISCLOSURE",prompt)
    def test_retrieval_full_scope(self):
        case=generate_fixture("T02")
        focused,manifest=select_evidence(case,"causality")
        self.assertEqual(manifest["omitted"],[])
        self.assertEqual(focused["corpus"]["sources"],case["corpus"]["sources"])
    def test_cycle_guides_are_specific(self):
        self.assertNotEqual(cycle_instruction(2),cycle_instruction(21))
        self.assertIn("private",cycle_instruction(13).lower())

class OllamaTests(unittest.TestCase):
    def test_nonlocal_endpoint_is_denied(self):
        with self.assertRaises(ProviderError):
            LocalOllamaAdapter("model","https://example.org/api/chat")
    def test_local_message_shape(self):
        payload='{"claims":[],"contradictions":[],"newly_open":[],"weakened_claims":[],"next_pressure_tests":[],"self_limitations":[]}'
        with patch("kakanyo.adapters._post",return_value={"message":{"content":payload}}) as req:
            result=LocalOllamaAdapter("synthetic").invoke("question")
            self.assertEqual(result["claims"],[])
            self.assertEqual(req.call_args.args[0],"http://127.0.0.1:11434/api/chat")

class HTTPTests(unittest.TestCase):
    def test_loopback_and_bearer_authorization(self):
        with TemporaryDirectory() as tmp:
            secret="synthetic-test-token-long-enough-for-ci"
            server=create_server(tmp,port=0,token=secret)
            th=threading.Thread(target=server.serve_forever,daemon=True)
            th.start()
            try:
                endpoint=f"http://127.0.0.1:{server.server_port}/mcp"
                message=json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/list"}).encode()
                invalid=urllib.request.Request(endpoint,data=message,headers={"Content-Type":"application/json"})
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(invalid,timeout=4)
                self.assertEqual(ctx.exception.code,401)
                valid=urllib.request.Request(endpoint,data=message,headers={
                    "Authorization":"Bearer "+secret,"Content-Type":"application/json"})
                with urllib.request.urlopen(valid,timeout=4) as response:
                    obj=json.loads(response.read())
                self.assertEqual(len(obj["result"]["tools"]),10)
            finally:
                server.shutdown();th.join(timeout=5);server.server_close()
    def test_external_bind_denied(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ContractError):
                create_server(tmp,host="0.0.0.0",token="long-synthetic-secret-123456789")

if __name__=="__main__":unittest.main()
