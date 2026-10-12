# Kakanyo build sequence

## P0 — Structural reference (this branch)
- [x] Independent Python package; no mandatory Hive imports
- [x] 12 invariants / 21-cycle method registry
- [x] Source and inquiry contract
- [x] Claim ledger, independent roots, uncertainty and contradiction registers
- [x] Digest-bound checkpoint; one-cycle execution; offline smoke adapter
- [x] OpenAI-compatible and Anthropic adapter shapes, no live credentials in source
- [x] Synthetic example and structural tests
- [ ] Independent PR review; install on a clean environment and inspect CI result

## P1 — Characteristic behaviour
- [ ] Eight complete synthetic gold corpora and blinded reference judgments
- [ ] Hard-fail versus degradable invariant policy and human scoring calibration
- [ ] Provenance spans, hashes and counterevidence support verification
- [ ] Explicit stopping/hold/resume protocol and reviewer case dispositions
- [ ] Side-by-side generic research baseline to test methodological distinctiveness

## P2 — Portability
- [ ] Real opt-in provider tests: GPT / Claude / DeepSeek / local open-weight
- [ ] Record prompt/corpus hashes, parameters, token budget, raw answers, review
- [ ] One frozen non-synthetic corpus with appropriate source-level approval
- [ ] Release a portability report with failures; do not presume pass

## P3 — Callable service
- [ ] Authenticated, scoped MCP interface over the already-proven core
- [ ] Tenant isolation, audit events, consent, bounded tools and rate limits
- [ ] ChatGPT, Work, Codex and HiveConnect adapters: separate transports, same kernel
- [ ] Failure, replay and permission testing against hostile inputs

**Architecture boundary:** HiveConnect may orchestrate Kakanyo work. It does not own or rewrite the epistemic kernel. Do not conflate a Workroom transcript with an evidence ledger.
