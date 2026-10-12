"""Command-line interface; no background worker, network listener or autonomous actions."""
import argparse
import json
from .adapters import ClaudeMessagesAdapter, OfflineAdapter, OpenAICompatibleAdapter
from .core import ContractError, read_json, validate_case
from .method import CYCLES, INVARIANTS
from .runtime import execute_cycle

def main():
    parser = argparse.ArgumentParser(description="Kakanyo P0 — model-portable instrument experiment")
    subs = parser.add_subparsers(dest="command", required=True)
    validate = subs.add_parser("validate", help="Validate a bounded corpus/inquiry contract")
    validate.add_argument("case")
    run = subs.add_parser("run", help="Execute exactly one stateful cycle")
    run.add_argument("case")
    run.add_argument("--state", default="kakanyo-state.json")
    run.add_argument("--adapter", choices=["offline", "openai-compatible", "claude"], default="offline")
    run.add_argument("--endpoint", help="Explicitly approved Chat Completions endpoint")
    run.add_argument("--model")
    run.add_argument("--key-env")
    status = subs.add_parser("status", help="Inspect saved research state")
    status.add_argument("state")
    subs.add_parser("method", help="Print the recovered registry and invariants")
    args = parser.parse_args()
    try:
        if args.command == "validate":
            validate_case(read_json(args.case))
            result = {"structural_contract": "PASS", "semantic_conformance": "NOT TESTED"}
        elif args.command == "method":
            result = {"invariants": INVARIANTS, "cycles": CYCLES}
        elif args.command == "status":
            state = read_json(args.state)
            result = {"corpus_id": state["corpus_id"], "completed_cycles": len(state["runs"]),
                      "next_cycle": state["next_cycle"],
                      "claims": len(state["claim_ledger"]),
                      "unresolved_open_entries": len(state["open_register"]),
                      "contradiction_entries": len(state["contradiction_register"])}
        else:
            if args.adapter == "offline":
                adapter = OfflineAdapter()
            elif args.adapter == "openai-compatible":
                if not args.endpoint or not args.model:
                    parser.error("--endpoint and --model are required")
                adapter = OpenAICompatibleAdapter(args.endpoint, args.model, args.key_env or "KAKANYO_API_KEY")
            else:
                if not args.model:
                    parser.error("--model is required")
                adapter = ClaudeMessagesAdapter(args.model, args.key_env or "KAKANYO_ANTHROPIC_KEY")
            result = execute_cycle(args.case, args.state, adapter)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (ContractError, ValueError, FileNotFoundError) as exc:
        parser.exit(2, "Kakanyo contract failure: " + str(exc) + "\n")

if __name__ == "__main__":
    main()
