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
