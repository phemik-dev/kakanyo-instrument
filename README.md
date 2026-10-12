# Kakanyo — an independent epistemic instrument

**P0 technical reference · not accepted canon · not yet model-portability tested**

> Kakanyo is not the model. Kakanyo is the epistemic behaviour the model is required to instantiate.

Kakanyo is a source-bound method for *disciplined curiosity*: evidence independence, provenance preservation, explicit inference, uncertainty conservation, contradiction, context, counter-tests, human boundaries, reversible synthesis and reflexive challenge.

The 12-invariant / five-movement / 21-cycle method originated in the September 2026 instrument programme. This public repository contains a **structural reference implementation**. It does **not** contain private research corpora, proprietary case studies or any human biography.

## Quick start

Python 3.10+ is required; runtime uses the standard library.

```bash
python -m kakanyo validate examples/synthetic-case.json
python -m kakanyo method
python -m kakanyo run examples/synthetic-case.json --state /tmp/kakanyo-demo-state.json --adapter offline
python -m kakanyo status /tmp/kakanyo-demo-state.json
python -m unittest discover -s tests -v
```

Each `run` processes exactly **one** scheduled cycle and persists state. The `offline` adapter is a **smoke-test stub**. It performs NO actual research analysis, and its state is not a valid case-study conclusion.

## Model adapters (explicit opt-in only)

A Chat Completions-compatible endpoint can be used with the following shape. This sends the complete authorised synthetic/approved case data to the configured provider; verify permission and the endpoint first.

```bash
export KAKANYO_API_KEY="set-privately-in-your-shell"
python -m kakanyo run examples/synthetic-case.json --state /tmp/kakanyo-model-state.json \
  --adapter openai-compatible --endpoint https://YOUR-APPROVED-ENDPOINT/v1/chat/completions \
  --model YOUR-MODEL
```

For Anthropic's Messages API, set `KAKANYO_ANTHROPIC_KEY` and run `--adapter claude --model YOUR-MODEL`.

Keys are read from environment variables; never commit them. Remote adapters are **not yet live-provider certified**, even if request/response structural tests pass.

## What exists

- 12 epistemic invariants; 5 movements; 21 defined cycles.
- Explicit source independence roots; claim typing; provenance reference IDs; open and contradiction registers.
- Corpus/inquiry contracts; deterministic source-level release checks; bounded prompt size.
- Durable per-cycle state; digest-based detection of modified input; fail-closed response validation.
- Offline custody-only stub and opt-in remote adapters.
- Executable structural tests; documented research conformance plan.

## What is *not* proven

Passing validation cannot establish that a statement is supported by the cited source. Declared independence roots may be wrong. No automated evaluator yet proves causality restraint, respectful human inference, omission detection or general research quality. There is no distributed state locking, multi-user authorisation, live provider certification, independently scored P0 portability study or callable remote MCP service.

The same source ID existing is **not** the same as correct provenance. This is not yet suitable as an unattended autonomous researcher.

See [KCP-001 conformance plan](docs/KCP-001.md) and [build roadmap](docs/ROADMAP.md). Changes should be reviewed via pull requests before adoption.

Copyright © 2026 Phemi Kgomongwe. All rights reserved until a repository licence is explicitly approved.
