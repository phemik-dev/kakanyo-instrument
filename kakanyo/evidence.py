"""Source-bound anchors and derivation checks. Literal evidence != semantic entailment."""
from hashlib import sha256
from .core import ContractError, validate_case

def source_hash(source: dict) -> str:
    return sha256(source["text"].encode("utf-8")).hexdigest()

def anchor(case: dict, source_id: str, quote: str, occurrence: int = 0) -> dict:
    """Construct an exact source anchor; no approximate or LLM-invented quotations."""
    validate_case(case)
    sources = {s["id"]: s for s in case["corpus"]["sources"]}
    if source_id not in sources or not isinstance(quote, str) or not quote:
        raise ContractError("Unknown source or empty quote")
    if not isinstance(occurrence, int) or occurrence < 0:
        raise ContractError("Occurrence must be >= 0")
    source = sources[source_id]
    cursor = 0
    for _ in range(occurrence + 1):
        position = source["text"].find(quote, cursor)
        if position < 0:
            raise ContractError("Quote not found in source")
        cursor = position + len(quote)
    return {"source_id": source_id, "start": position, "end": cursor,
            "quote": quote, "sha256": source_hash(source)}

def verify_anchor(case: dict, record: dict) -> bool:
    validate_case(case)
    if not isinstance(record, dict):
        raise ContractError("Evidence anchor must be an object")
    sources = {s["id"]: s for s in case["corpus"]["sources"]}
    sid = record.get("source_id")
    if sid not in sources:
        raise ContractError("Anchor refers to unknown source")
    source = sources[sid]
    a, b = record.get("start"), record.get("end")
    if not isinstance(a, int) or isinstance(a, bool) or not isinstance(b, int) or isinstance(b, bool):
        raise ContractError("Anchor offsets must be integers")
    if a < 0 or b <= a or b > len(source["text"]):
        raise ContractError("Anchor offset out of range")
    if source_hash(source) != record.get("sha256"):
        raise ContractError("Source hash has changed")
    if source["text"][a:b] != record.get("quote"):
        raise ContractError("Source quote does not match")
    return True

def verify_claim_anchors(case: dict, claim: dict) -> dict:
    """Only validates the integrity of supplied spans. Does not decide if words support a claim."""
    anchors = claim.get("anchors", [])
    if not isinstance(anchors, list):
        raise ContractError("Claim anchors must be an array")
    allowed = set(claim.get("evidence_refs", []))
    for record in anchors:
        if record.get("source_id") not in allowed:
            raise ContractError("Anchor source must be cited as evidence")
        verify_anchor(case, record)
    return {"anchors_checked": len(anchors), "semantic_support": "NOT_EVALUATED"}

def derivation_roots(case: dict) -> dict[str, str]:
    """Check optional derived_from edges against declared independence roots."""
    validate_case(case)
    sources = {source["id"]: source for source in case["corpus"]["sources"]}
    visiting, completed = set(), {}
    def root(sid):
        if sid in visiting:
            raise ContractError("Derivation cycle detected")
        if sid in completed:
            return completed[sid]
        source = sources[sid]
        visiting.add(sid)
        parent = source.get("derived_from")
        if parent:
            if parent not in sources:
                raise ContractError("Unknown derivation parent")
            resolved = root(parent)
            if source["independence_root"] != resolved:
                raise ContractError("Derived source falsely declared independent")
        else:
            resolved = source["independence_root"]
        visiting.remove(sid)
        completed[sid] = resolved
        return resolved
    for sid in sources:
        root(sid)
    return completed

def materialise_quotes(case: dict, output: dict, selected_ids=None) -> dict:
    """Validate literal source quotations before writing model claims."""
    from copy import deepcopy
    if not isinstance(output, dict) or not isinstance(output.get("claims"), list):
        raise ContractError("Model response must contain claims array")
    checked=deepcopy(output)
    permitted=set(selected_ids) if selected_ids is not None else None
    for claim in checked["claims"]:
        refs=set(claim.get("evidence_refs",[]))
        if permitted is not None and not refs.issubset(permitted):
            raise ContractError("Claim cites material omitted from this invocation")
        anchors=claim.get("anchors",[])
        quotes=claim.pop("evidence_quotes",[])
        if not isinstance(anchors,list) or not isinstance(quotes,list):
            raise ContractError("Source evidence anchors and quotes must be arrays")
        for item in quotes:
            if not isinstance(item,dict):
                raise ContractError("Quotation must specify source_id and quote")
            sid=item.get("source_id");quote=item.get("quote")
            if sid not in refs or not isinstance(quote,str) or not 1<=len(quote)<=1200:
                raise ContractError("Quotation must be short, exact and cited")
            anchors.append(anchor(case,sid,quote,item.get("occurrence",0)))
        claim["anchors"]=anchors
        verify_claim_anchors(case,claim)
        if claim.get("claim_type")=="DIRECT" and not anchors:
            raise ContractError("DIRECT claim requires an exact source anchor")
    return checked
