# Kakanyo — independent epistemic research instrument

**Executable integrated build v0.2** · Python 3.10+ · local-first · framework-neutral

> Kakanyo is not the model. Kakanyo is the epistemic behaviour the model is required to instantiate.

Kakanyo applies disciplined curiosity to a bounded evidence corpus. Its five research movements contain 21 specific cycles. It preserves evidence ancestry, contradictions, uncertainty, counter-tests and the human decision boundary.

**Kakanyo is not a chatbot persona and is not a HiveForge module.** It works as a standalone Python package, a CLI, a local MCP tool service or a token-authenticated localhost HTTP MCP service. ChatGPT, Codex and HiveConnect can connect to the instrument through their supported host runtimes once configured.

## Get running

```bash
python -m pip install .
python -m unittest discover -s tests -v
kakanyo method
kakanyo fixtures --outdir ./example-fixtures
```

```bash
kakanyo ingest ./my-documents --case-id my-inquiry \
  --question "What does the evidence establish, and what is still unproven?" \
  --scope "The documents supplied for this inquiry" --workspace .kakanyo

# One local smoke cycle (custody only — no AI research)
kakanyo cycle my-inquiry --workspace .kakanyo --adapter offline

# One real model-backed cycle with a locally installed Ollama model
kakanyo cycle my-inquiry --workspace .kakanyo --adapter ollama --model YOUR_LOCAL_MODEL

kakanyo case-status my-inquiry --workspace .kakanyo
kakanyo audit my-inquiry --workspace .kakanyo
kakanyo case-report my-inquiry --workspace .kakanyo --output dossier.md
```

Install `".[documents]"` for optional PDF/DOCX extraction. Only read approved files. Default corpus permission is **private**, and provider egress is blocked unless each source is explicitly eligible.

## What's built

| Capability | Implementation |
|---|---|
| Portable method | 12 invariants, five movements, 21 distinct cycle instructions |
| Intake | Explicit local documents or typed JSON corpus/inquiry contracts |
| Evidence | Provenance IDs, derivative-independence checks, source span/hash anchors |
| Durable research | SQLite case state, 21-cycle progression, claim/OPEN/contradiction ledgers |
| Governance | Hold/resume, reviewer opinions, tamper-evident audit event history |
| Bounded context | Deterministic retrieval with logged omissions and no hidden truncation |
| Model adapters | Local Ollama, OpenAI-compatible APIs, Anthropic Claude and offline test stub |
| Interfaces | CLI, stdio MCP, bearer-gated loopback HTTP MCP |
| Results | Markdown/HTML/JSON dossiers and eight synthetic adversarial conformance cases |
| Build | Python test matrix and wheel CI |

## Conformance is not automatic

The eight challenges require evaluation of *meaning*, not just valid JSON. Structural tests and mock adapters cannot establish source entailment, fairness, real-provider interoperability or genuine cross-model behavioural portability. Kakanyo's output remains reversible and should receive accountable human review.

Read the [operator guide](docs/OPERATOR_GUIDE.md), [conformance profile](docs/KCP-001.md) and [roadmap](docs/ROADMAP.md).

## Hosting and privacy

`kakanyo serve-mcp` runs as a child process under a trusted client. `kakanyo serve-http` serves only the loopback interface, requires a long random `KAKANYO_HTTP_TOKEN`, and exposes JSON-RPC at `POST /mcp`. An internet-accessible endpoint, multi-tenant isolation and provider tokens require additional operator-managed infrastructure and acceptance testing. This repository does not silently deploy a public service.

No proprietary or private Kakanyo case corpus is in this public repository. Do not commit `.kakanyo/`, credentials or real-person evidence. Copyright © 2026 Phemi Kgomongwe. All rights reserved; licensing remains a separate explicit decision.
