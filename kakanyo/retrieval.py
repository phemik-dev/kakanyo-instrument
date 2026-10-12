"""Auditable deterministic excerpt selection for corpora larger than the context window.

Retrieval is lexical (not a claim of semantic recall); omissions remain explicit.
"""
import copy
import re
from .core import ContractError, validate_case
from .evidence import source_hash

MAX_PROMPT_EVIDENCE=52000

def words(text):
    return set(re.findall(r"[a-z0-9]{3,}",text.lower()))

def select_evidence(case: dict, question: str, budget: int=MAX_PROMPT_EVIDENCE, limit: int=16):
    validate_case(case)
    if not isinstance(question,str):raise ContractError("Query must be text")
    if budget<1000 or limit<1:raise ContractError("Evidence retrieval parameters too small")
    sources=case["corpus"]["sources"]
    combined=sum(len(x["text"]) for x in sources)
    if combined<=budget:
        return copy.deepcopy(case), {"strategy":"complete","selected":[x["id"] for x in sources],
                                      "omitted":[],"clipped":[]}
    tokens=words(question)
    scored=[]
    for idx,s in enumerate(sources):
        text=s["text"]
        hits=len(tokens.intersection(words(text[:min(len(text),200_000)])))
        scored.append((-hits,idx,s))
    scored.sort(key=lambda x:(x[0],x[1]))
    picked=scored[:min(limit,len(scored))]
    allocation=max(300,budget//len(picked)-400)
    chosen=[]
    clipped=[]
    for _,_,source in picked:
        clone=copy.deepcopy(source)
        text=source["text"]
        if len(text)>allocation:
            # Prefer a lexical hit vicinity, retaining exact byte-for-byte substring.
            lowered=text.lower()
            positions=[lowered.find(token) for token in sorted(tokens) if lowered.find(token)>=0]
            center=min(positions) if positions else 0
            start=max(0,center-350)
            end=min(len(text),start+allocation)
            clone["text"]=text[start:end]
            clone["excerpt_start"]=start
            clone["excerpt_end"]=end
            clone["original_sha256"]=source_hash(source)
            clipped.append(source["id"])
        chosen.append(clone)
    selected={x["id"] for x in chosen}
    omitted=[x["id"] for x in sources if x["id"] not in selected]
    material=copy.deepcopy(case)
    material["corpus"]["sources"]=chosen
    material["corpus"]["known_gaps"].append(
        "RETRIEVAL PARTIAL: some source documents or sections are not in this prompt; "
        "absence from excerpts is not evidence of absence from the underlying corpus.")
    material["corpus"]["retrieval_limitations"]+="; deterministic lexical excerpt selection"
    return material, {"strategy":"lexical-partial","selected":[x["id"] for x in chosen],
                       "omitted":omitted,"clipped":clipped,
                       "selected_source_offsets":{x["id"]:[x.get("excerpt_start",0),
                          x.get("excerpt_end",len(x["text"]))] for x in chosen}}
