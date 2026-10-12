"""Provisional movement and invariant registry from the September 2026 instrument ledger."""

INVARIANTS = (
    "evidence_independence",
    "provenance_preservation",
    "claim_typing",
    "uncertainty_conservation",
    "contradiction_preservation",
    "recurrence_not_origin",
    "context_sensitivity",
    "counterfactual_subtraction",
    "shadow_obligation",
    "human_boundary",
    "synthesis_reversibility",
    "reflexive_challenge",
)

MOVEMENTS = {
    "I": ("SEEING", ("Broad Portrait", "Adversarial Reading", "Genealogy", "Subtraction", "Strengths & Shadows")),
    "II": ("CONTEXT", ("Web of Relationships", "Contradictions", "Time & Context", "Structures & Power", "Integration")),
    "III": ("THE HUMAN BEHIND USEFULNESS", ("Interdependence", "Care & Control", "Beyond Usefulness", "Disconfirmation", "Direct-Question Threshold")),
    "IV": ("ORIGINS, CHOICE & BECOMING", ("Origins & Chronology", "Adaptation & Principle", "Self & Structure", "Repeated Choice", "Working Portrait")),
    "V": ("QUESTIONS TURN BACK", ("Questioning the Questions",)),
}

CYCLES = tuple(
    (movement, index, title)
    for movement, (_, titles) in MOVEMENTS.items()
    for index, title in enumerate(titles, start={"I": 1, "II": 6, "III": 11, "IV": 16, "V": 21}[movement])
)

def cycle_record(cycle: int) -> dict:
    for movement, index, title in CYCLES:
        if cycle == index:
            return {"movement": movement, "movement_title": MOVEMENTS[movement][0],
                    "cycle": cycle, "cycle_title": title}
    raise ValueError("Cycle must be between 1 and 21")

# Cycle-level reasoning programmes. Output discipline remains controlled by the core.
CYCLE_GUIDANCE = {
  "1": "Form a provisional broad portrait of the evidence. Separate directly observed facts, deductions and missing testimony. Identify exactly which sources can support each claim.",
  "2": "Conduct an adversarial reading against the first portrait. Construct credible rival interpretations; do not argue for disconfirmation merely for theatrical balance.",
  "3": "Investigate genealogy of assertions. Track earliest surviving attestations, source derivation, influences and gaps; never equate earliest preserved record with origin.",
  "4": "Subtract names, metaphors, brands and fashionable terminology. Reassess what proposition survives without local language or institutional symbolism.",
  "5": "Pair each claimed strength with a shadow obligation: foreseeable failure mode, counter-example, power imbalance or stopping condition.",
  "6": "Map relationships and reliance. Distinguish relational recurrence from causality. Ask whose voice and authorship are present or missing.",
  "7": "Surface credible contradictions with exact references. Keep inconsistent accounts open until a justified reconciliation is possible.",
  "8": "Reconstruct the chronology and uncertainty in dates. Test what was possible at each time; resist backwards projection and post hoc causal stories.",
  "9": "Test structural forces and authority: rules, incentives, resources, permissions, hierarchy and power. Conditions are not proof of motives.",
  "10": "Integrate provisional contextual findings. Show survivors, weakened propositions, contradictions and genuinely unknown matters without flattening them.",
  "11": "Examine interdependence and agency. Ask whether actors preserve legibility, voice, contestability, authorship and developing capacity inside reliance.",
  "12": "Investigate care versus control. Judge work-facing arrangements by whose decision capacity remains; do not infer benevolent or malicious intentions.",
  "13": "Identify what lies beyond recorded usefulness or role. Do not infer private interior life, emotional state or identity from the absence of testimony.",
  "14": "Run the strongest available disconfirmation pass. Seek decisive counterevidence; state how each major claim would be weakened or overturned.",
  "15": "Identify the direct-question threshold: which claims require the relevant person's testimony, accountable interview or human decision rather than synthesis.",
  "16": "Map origins and chronology provisionally. Separate documented dates, proposed genealogy, repetition, unresolved gaps and probable later reinterpretations.",
  "17": "Contrast adaptation with principle while refusing to invent their origin. Test which costs and repeated choices support a hypothesis of commitment.",
  "18": "Inspect interactions between personal agency, institutional structures, geography, history and power. Avoid mono-causal character stories.",
  "19": "Examine repeated consequential choices across independent contexts. Separate behaviour recurrence from fixed essence, virtue or hidden motivation.",
  "20": "Produce a reversible working portrait. Distinguish strongly supported, weakly supported, rejected and still-open propositions; document counter-tests.",
  "21": "Turn the inquiry onto itself. Challenge loaded questions, category mistakes, blind spots, retrieval omissions, scoring incentives, inherited assumptions and whether the method earned its conclusions."
}

def cycle_instruction(cycle: int) -> str:
    if cycle not in range(1, 22):
        raise ValueError("Invalid Kakanyo cycle")
    return CYCLE_GUIDANCE[str(cycle)]
