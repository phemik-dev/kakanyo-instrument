"""Local MCP stdio service. Transport inherits host process trust; never exposes HTTP.

Tool inputs are bounded; remote model use is disabled unless explicitly configured by operator.
"""
import json
import os
import sys

from .adapters import OfflineAdapter, OpenAICompatibleAdapter, ClaudeMessagesAdapter, LocalOllamaAdapter
from .core import ContractError
from .fixtures import catalog
from .workspace import Workspace

PROTOCOL="2025-06-18"
MAX_MESSAGE=2_000_000

def spec(name, description, required, properties):
    return {"name": "kakanyo_"+name, "description": description,
            "inputSchema":{"type":"object","properties":properties,
                           "required":required,"additionalProperties":False}}

def prop(kind="string", description=""):
    return {"type":kind,"description":description}

TOOLS=[
    spec("list_cases","List local case IDs and status",[],{}),
    spec("import_case","Import an approved corpus and inquiry object into the local workspace",["case"],{"case":prop("object")}),
    spec("case_status","Read the bounded case state",["case_id"],{"case_id":prop()}),
    spec("run_cycle","Execute the next research cycle; local offline stub by default",["case_id"],{"case_id":prop(),"adapter":{"type":"string","enum":["offline","openai-compatible","claude","ollama"]}}),
    spec("run_inquiry","Execute multiple consecutive research cycles with bounded provider usage",["case_id","count"],{
        "case_id":prop(),"count":{"type":"integer","minimum":1,"maximum":21},
        "adapter":{"type":"string","enum":["offline","openai-compatible","claude","ollama"]}}),
    spec("case_report","Read claims, uncertainty and human reviews for a case",["case_id"],{"case_id":prop()}),
    spec("hold_case","Pause a case with an explicit reason",["case_id","reason"],{"case_id":prop(),"reason":prop()}),
    spec("resume_case","Resume a held case with a recorded rationale",["case_id","reason"],{"case_id":prop(),"reason":prop()}),
    spec("review_claim","Submit an accountable human claim assessment",["case_id","claim_id","reviewer","judgement","rationale"],{
        "case_id":prop(),"claim_id":prop(),"reviewer":prop(),
        "judgement":{"type":"string","enum":["supported","unsupported","uncertain","needs-test"]},
        "rationale":prop()}),
    spec("verify_history","Verify the local custody hash chain",["case_id"],{"case_id":prop()}),
    spec("fixture_catalog","List eight completely synthetic adversarial test cases",[],{}),
]

def adapter_for_mcp(name):
    if name=="offline":return OfflineAdapter()
    if name=="ollama":return LocalOllamaAdapter(os.environ.get("KAKANYO_MCP_MODEL","llama3.1"))
    if os.environ.get("KAKANYO_MCP_REMOTE_ENABLED")!="1":
        raise ContractError("Remote model invocation is disabled for this MCP service")
    if name=="openai-compatible":
        endpoint=os.environ.get("KAKANYO_MCP_ENDPOINT")
        model=os.environ.get("KAKANYO_MCP_MODEL")
        if not endpoint or not model:
            raise ContractError("Operator must configure KAKANYO_MCP_ENDPOINT and KAKANYO_MCP_MODEL")
        return OpenAICompatibleAdapter(endpoint,model)
    if name=="claude":
        model=os.environ.get("KAKANYO_MCP_MODEL")
        if not model:raise ContractError("Operator must configure KAKANYO_MCP_MODEL")
        return ClaudeMessagesAdapter(model)
    raise ContractError("Unknown MCP adapter")

def call_tool(ws, name, args):
    if not isinstance(args,dict):
        raise ContractError("Tool arguments must be an object")
    mapping={t["name"]:t for t in TOOLS}
    if name not in mapping:raise ContractError("Unknown Kakanyo tool")
    schema=mapping[name]["inputSchema"]
    missing=set(schema["required"])-set(args)
    unknown=set(args)-set(schema["properties"])
    if missing or unknown:raise ContractError(f"Bad arguments: missing={sorted(missing)}, unknown={sorted(unknown)}")
    for key,val in args.items():
        kind=schema["properties"][key]["type"]
        if (kind=="string" and not isinstance(val,str)) or (kind=="object" and not isinstance(val,dict)):
            raise ContractError("Invalid type for "+key)
        if kind=="integer" and (type(val) is not int or not 1<=val<=21):
            raise ContractError("count must be 1..21")
        valid=schema["properties"][key].get("enum")
        if valid and val not in valid:raise ContractError("Unsupported "+key)
    if name=="kakanyo_list_cases":return ws.list_cases()
    if name=="kakanyo_import_case":return ws.import_case(args["case"])
    if name=="kakanyo_case_status":return ws.status(args["case_id"])
    if name=="kakanyo_run_cycle":return ws.execute(args["case_id"],adapter_for_mcp(args.get("adapter","offline")))
    if name=="kakanyo_run_inquiry":
        count=args["count"]
        adapter=adapter_for_mcp(args.get("adapter","offline"))
        if isinstance(adapter,OfflineAdapter) and count>1:
            raise ContractError("Offline adapter cannot conduct a multi-cycle inquiry")
        if not getattr(adapter,"local_only",False):
            max_remote=int(os.environ.get("KAKANYO_MCP_REMOTE_CYCLE_LIMIT","3"))
            if count>max(1,min(21,max_remote)):
                raise ContractError("Exceeds configured remote cycle call limit")
        outcome=[]
        for _ in range(count):
            if ws.status(args["case_id"])["next_cycle"]>21:break
            outcome.append(ws.execute(args["case_id"],adapter))
        return {"completed":len(outcome),"state":ws.status(args["case_id"])}
    if name=="kakanyo_case_report":return ws.report(args["case_id"])
    if name=="kakanyo_hold_case":return ws.hold(args["case_id"],args["reason"])
    if name=="kakanyo_resume_case":return ws.resume(args["case_id"],args["reason"])
    if name=="kakanyo_review_claim":
        return ws.review(args["case_id"],args["claim_id"],args["reviewer"],args["judgement"],args["rationale"])
    if name=="kakanyo_verify_history":return ws.verify_history(args["case_id"])
    if name=="kakanyo_fixture_catalog":return catalog()
    raise ContractError("Unknown tool")

def process(ws, message):
    """Return JSON-RPC response or None (notification)."""
    if not isinstance(message,dict) or message.get("jsonrpc")!="2.0":
        return {"jsonrpc":"2.0","id":message.get("id") if isinstance(message,dict) else None,
                "error":{"code":-32600,"message":"Invalid JSON-RPC request"}}
    request_id=message.get("id")
    if "id" not in message:
        return None
    method=message.get("method")
    try:
        if method=="initialize":
            result={"protocolVersion":PROTOCOL,"capabilities":{"tools":{"listChanged":False}},
                    "serverInfo":{"name":"kakanyo-instrument","version":"0.2.0"}}
        elif method=="ping":result={}
        elif method=="tools/list":result={"tools":TOOLS}
        elif method=="tools/call":
            params=message.get("params",{})
            if not isinstance(params,dict):raise ContractError("Invalid tool call")
            output=call_tool(ws,params.get("name"),params.get("arguments",{}))
            result={"content":[{"type":"text","text":json.dumps(output,ensure_ascii=False)}],
                    "isError":False}
        elif method in {"resources/list","prompts/list"}:
            result={"resources":[] } if method=="resources/list" else {"prompts":[]}
        else:
            return {"jsonrpc":"2.0","id":request_id,
                    "error":{"code":-32601,"message":"Method not found"}}
        return {"jsonrpc":"2.0","id":request_id,"result":result}
    except Exception as exc:
        if method=="tools/call":
            return {"jsonrpc":"2.0","id":request_id,
                    "result":{"content":[{"type":"text","text":f"Kakanyo tool error: {type(exc).__name__}: {exc}"}],
                              "isError":True}}
        return {"jsonrpc":"2.0","id":request_id,
                "error":{"code":-32602,"message":str(exc)}}

def serve(workspace=".kakanyo"):
    ws=Workspace(workspace)
    for line in sys.stdin.buffer:
        if len(line)>MAX_MESSAGE:
            message={"jsonrpc":"2.0","id":None,
                     "error":{"code":-32600,"message":"Input exceeds size limit"}}
        else:
            try:
                obj=json.loads(line)
                message=process(ws,obj)
            except (ValueError,UnicodeDecodeError) as exc:
                message={"jsonrpc":"2.0","id":None,
                         "error":{"code":-32700,"message":"Parse error"}}
        if message is not None:
            sys.stdout.write(json.dumps(message,ensure_ascii=False,separators=(",",":"))+"\n")
            sys.stdout.flush()

if __name__=="__main__":
    serve(os.environ.get("KAKANYO_WORKSPACE",".kakanyo"))
