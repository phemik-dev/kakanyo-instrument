"""Kakanyo operator CLI: research custody, provider cycles, fixtures and stdio MCP."""
import argparse
import json
import os
import sys

from .adapters import ClaudeMessagesAdapter, OfflineAdapter, OpenAICompatibleAdapter, LocalOllamaAdapter
from .conformance import aggregate, run_suite, write_suite
from .core import ContractError, read_json, validate_case, write_json_atomic
from .evidence import anchor, derivation_roots
from .fixtures import SCENARIOS, catalog, generate_fixture
from .method import CYCLES, INVARIANTS
from .ingest import case_from_directory
from .reporting import write_report
from .runtime import execute_cycle
from .workspace import Workspace

def adapter_from(args):
    name = getattr(args, "adapter", "offline")
    if name == "offline":
        return OfflineAdapter()
    if name == "ollama":
        return LocalOllamaAdapter(getattr(args, "model", None) or "llama3.1")
    model = getattr(args, "model", None)
    if not model:
        raise ContractError("A --model is required for remote adapters")
    if name == "claude":
        return ClaudeMessagesAdapter(model, getattr(args, "key_env", None) or "KAKANYO_ANTHROPIC_KEY")
    if name == "openai-compatible":
        endpoint = getattr(args, "endpoint", None)
        if not endpoint:
            raise ContractError("An explicit --endpoint is required")
        return OpenAICompatibleAdapter(endpoint, model, getattr(args, "key_env", None) or "KAKANYO_API_KEY")
    raise ContractError("Unsupported adapter")

def main(argv=None):
    p = argparse.ArgumentParser(description="Kakanyo: evidence-bound research instrument")
    s = p.add_subparsers(dest="command", required=True)
    def add_workspace(cmd):
        cmd.add_argument("--workspace", default=os.environ.get("KAKANYO_WORKSPACE", ".kakanyo"))
    def add_provider(cmd):
        cmd.add_argument("--adapter", default="offline",
                         choices=["offline", "openai-compatible", "claude", "ollama"])
        cmd.add_argument("--model")
        cmd.add_argument("--endpoint")
        cmd.add_argument("--key-env")

    c=s.add_parser("validate",help="Validate a case JSON");c.add_argument("case")
    s.add_parser("method",help="Print the invariant and movement registry")
    c=s.add_parser("run",help="Legacy JSON checkpoint one-cycle runner")
    c.add_argument("case");c.add_argument("--state",default="kakanyo-state.json");add_provider(c)
    c=s.add_parser("status",help="Legacy JSON checkpoint inspection");c.add_argument("state")
    c=s.add_parser("import-case",help="Ingest a scoped case into local SQLite");c.add_argument("case");add_workspace(c)
    c=s.add_parser("ingest",help="Ingest documents from a local directory as a bounded research case")
    c.add_argument("directory");c.add_argument("--case-id",required=True)
    c.add_argument("--question",required=True);c.add_argument("--scope",required=True)
    c.add_argument("--permissions",choices=["private","synthetic","approved-for-external-model"],default="private")
    add_workspace(c)
    c=s.add_parser("list-cases");add_workspace(c)
    c=s.add_parser("case-status");c.add_argument("case_id");add_workspace(c)
    c=s.add_parser("cycle",help="Run next cycle; model adapter or explicit offline stub")
    c.add_argument("case_id");add_workspace(c);add_provider(c)
    c=s.add_parser("pursue",help="Run consecutive cycles (bounded to --count)")
    c.add_argument("case_id");c.add_argument("--count",type=int,default=1);add_workspace(c);add_provider(c)
    c=s.add_parser("case-report");c.add_argument("case_id");c.add_argument("--output");c.add_argument("--format",choices=["json","md","html"],default="md");add_workspace(c)
    c=s.add_parser("review");c.add_argument("case_id");c.add_argument("claim_id");c.add_argument("--reviewer",required=True);c.add_argument("--judgement",required=True,choices=["supported","unsupported","uncertain","needs-test"]);c.add_argument("--rationale",required=True);add_workspace(c)
    c=s.add_parser("hold");c.add_argument("case_id");c.add_argument("--reason",required=True);add_workspace(c)
    c=s.add_parser("resume");c.add_argument("case_id");c.add_argument("--reason",required=True);add_workspace(c)
    c=s.add_parser("audit");c.add_argument("case_id");add_workspace(c)
    c=s.add_parser("anchor");c.add_argument("case");c.add_argument("source_id");c.add_argument("quote")
    c=s.add_parser("fixtures");c.add_argument("--outdir")
    c=s.add_parser("benchmark",help="Execute synthetic T01-T08, save unscored raw trials")
    c.add_argument("--output-dir",required=True);c.add_argument("--name",required=True);add_provider(c)
    c=s.add_parser("benchmark-summary");c.add_argument("trials")
    c=s.add_parser("serve-mcp",help="Serve local stdio MCP (no HTTP listener)");add_workspace(c)

    a=p.parse_args(argv)
    try:
        if a.command=="method":
            result={"invariants":INVARIANTS,"cycles":CYCLES}
        elif a.command=="validate":
            case=read_json(a.case);validate_case(case);roots=derivation_roots(case)
            result={"structural_contract":"PASS","sources":len(roots),"semantic_conformance":"NOT_TESTED"}
        elif a.command=="run":
            result=execute_cycle(a.case,a.state,adapter_from(a))
        elif a.command=="status":
            state=read_json(a.state)
            result={"corpus_id":state["corpus_id"],"completed_cycles":len(state["runs"]),
                    "next_cycle":state["next_cycle"],"claims":len(state["claim_ledger"])}
        elif a.command=="fixtures":
            result=catalog()
            if a.outdir:
                from pathlib import Path
                root=Path(a.outdir).expanduser().resolve()
                root.mkdir(parents=True,exist_ok=True)
                for item in result:
                    file=root/(item["id"]+".json")
                    if file.exists():raise ContractError("Fixture destination already exists: "+str(file))
                    write_json_atomic(file,generate_fixture(item["id"]))
        elif a.command=="benchmark":
            trials=run_suite(adapter_from(a),getattr(a,"model",None) or "offline")
            result={"file":write_suite(a.output_dir,trials,a.name),"summary":aggregate(trials)}
        elif a.command=="benchmark-summary":
            result=aggregate(read_json(a.trials))
        elif a.command=="anchor":
            result=anchor(read_json(a.case),a.source_id,a.quote)
        elif a.command=="serve-mcp":
            from .mcp import serve
            serve(a.workspace)
            return
        else:
            ws=Workspace(a.workspace)
            if a.command=="import-case":
                result=ws.import_case(read_json(a.case))
            elif a.command=="ingest":
                case=case_from_directory(a.directory,a.case_id,a.question,a.scope,a.permissions)
                result=ws.import_case(case)
            elif a.command=="list-cases":
                result=ws.list_cases()
            elif a.command=="case-status":
                result=ws.status(a.case_id)
            elif a.command=="cycle":
                result=ws.execute(a.case_id,adapter_from(a))
            elif a.command=="pursue":
                if not 1<=a.count<=21:raise ContractError("--count must be 1..21")
                if a.adapter=="offline" and a.count>1:
                    raise ContractError("Offline is a stub; use a model for multi-cycle research")
                result=[]
                for _ in range(a.count):
                    current=ws.status(a.case_id)
                    if current["next_cycle"]>21:break
                    result.append(ws.execute(a.case_id,adapter_from(a)))
            elif a.command=="case-report":
                report=ws.report(a.case_id)
                if a.output:
                    result={"file":write_report(report,a.output,a.format),"status":report["status"]}
                else:
                    result=report
            elif a.command=="review":
                result=ws.review(a.case_id,a.claim_id,a.reviewer,a.judgement,a.rationale)
            elif a.command=="hold":
                result=ws.hold(a.case_id,a.reason)
            elif a.command=="resume":
                result=ws.resume(a.case_id,a.reason)
            elif a.command=="audit":
                result=ws.verify_history(a.case_id)
            else: raise ContractError("Unknown command")
        print(json.dumps(result,indent=2,ensure_ascii=False))
    except (ContractError,ValueError,FileNotFoundError,KeyError) as exc:
        p.exit(2,"Kakanyo error: "+str(exc)+"\n")

if __name__=="__main__":
    main()
