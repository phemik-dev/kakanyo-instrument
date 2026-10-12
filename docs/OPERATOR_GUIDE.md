# Kakanyo operator guide v0.2

Kakanyo is an independent evidence-bound inquiry instrument. This repository contains an executable reference, not an accepted cross-model scientific certification.

## Install and verify

```bash
python -m pip install .
python -m unittest discover -s tests -v
python -m kakanyo method
```

Optional PDF and DOCX support: `python -m pip install ".[documents]"`.

## Research a document collection

```bash
kakanyo ingest ./research-corpus --case-id my-first-inquiry \
  --scope "Scope and purpose of these source documents" \
  --question "Which claims survive adversarial testing?" \
  --workspace .kakanyo

kakanyo list-cases --workspace .kakanyo
kakanyo case-status my-first-inquiry --workspace .kakanyo
```

The default permission is **private**, so external model calls are blocked. The corpus remains inside the local SQLite workspace; do not commit `.kakanyo/` to Git.

## Run Kakanyo

A custody-only smoke test that does **no actual research**:

```bash
kakanyo cycle my-first-inquiry --workspace .kakanyo --adapter offline
```

To conduct model-backed research on a local Ollama instance:

```bash
kakanyo cycle my-first-inquiry --workspace .kakanyo --adapter ollama --model YOUR_LOCAL_MODEL
kakanyo pursue my-first-inquiry --workspace .kakanyo --adapter ollama --model YOUR_LOCAL_MODEL --count 20
```

For a case whose sources are *explicitly approved* for remote transmission, use `--adapter openai-compatible --endpoint https://YOUR_APPROVED_PROVIDER/v1/chat/completions --model MODEL` and `KAKANYO_API_KEY` from the environment. Claude's adapter uses `KAKANYO_ANTHROPIC_KEY`. Never place keys in prompts, files or Git.

Each execution commits **one** cycle. The 21 cycle guides run across Seeing, Context, Human Behind Usefulness, Origins/Choice/Becoming and Questions Turn Back. Case status tracks complete and open cycles.

## Stop, review and report

```bash
kakanyo hold my-first-inquiry --reason "Independent verification needed"
kakanyo resume my-first-inquiry --reason "Verification obtained and recorded"
kakanyo review my-first-inquiry K1 --reviewer steward-A --judgement uncertain \
  --rationale "Document proves a reported action but not its outcome"
kakanyo audit my-first-inquiry --workspace .kakanyo
kakanyo case-report my-first-inquiry --workspace .kakanyo --output dossier.md
```

Use `--format html` or `--format json` to change the export. Reports do not claim institutional approval.

## Adversarial testing

```bash
kakanyo fixtures --outdir ./fixture-corpus
kakanyo benchmark --adapter offline --output-dir ./trials --name smoke-01
kakanyo benchmark-summary ./trials/smoke-01.json
```

To produce blinded, scored trials:

```bash
kakanyo benchmark-blind ./trials/smoke-01.json --output-dir ./blinded --name batch-01
kakanyo benchmark-review ./blinded/batch-01.json --trial BLIND_ID \
  --reviewer researcher-A --score 1 --rationale "Specific supported criticism" \
  --output-dir ./reviewed --name batch-01-review-A
kakanyo benchmark-summary ./reviewed/batch-01-review-A.json
```

Use a second independent reviewer and retain the original trial-to-blind mapping separately.

Eight synthetic cases challenge source independence, causal restraint, contradiction, private-state inference, chronology, brand subtraction, authority and self-audit. Scores require blind human review; the offline run is a structural smoke.

## Callable interfaces

Local stdio MCP:

```bash
kakanyo serve-mcp --workspace .kakanyo
```

Local token-authenticated HTTP MCP:

```bash
export KAKANYO_HTTP_TOKEN="USE_A_RANDOM_SECRET_LONGER_THAN_24_CHARACTERS"
kakanyo serve-http --workspace .kakanyo --host 127.0.0.1 --port 8765
```

Eleven MCP tools cover case intake, status, cycle execution, reports, human reviews, holds and audit. No public HTTP binding is permitted by this reference transport. Remote ChatGPT installation still requires an approved hosting/gateway and the platform connection step; this repository does **not** deploy such infrastructure on its own.

MCP remote provider calls are disabled by default; local Ollama remains available. For external model calls, the operator must explicitly set `KAKANYO_MCP_REMOTE_ENABLED=1`, a provider configuration and approved source-level case permissions.

## What to improve after this end-to-end build

Document independence requires review beyond equal hashes. Lexical retrieval is not semantic completeness. Literal quotes are not proof of claim entailment. External model adapters and private hosting require live tests and security work. Real cross-model conformance is not yet established. A robust human reviewer and additional case types remain essential.
