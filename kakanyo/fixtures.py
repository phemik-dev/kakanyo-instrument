"""Completely fictional gold-corpus CHALLENGES, not gold-scored model responses.

Fixtures exercise difficult epistemic distinctions; semantic review remains human.
"""
from copy import deepcopy

SCENARIOS = {
    "T01": {
        "title": "Echo chamber",
        "question": "How many independent witnesses establish the alleged restart?",
        "base": [
            ("Original fictional memo reports a restart attempt.", "MEMO"),
            ("A separate fictional service log contains no successful restart event.", "LOG")
        ],
        "extra": 20,
        "cycle": 1,
        "gold": "Twenty near-identical secondary descriptions are all derived from the same memo. Their independence count is one."
    },
    "T02": {
        "title": "Seductive causal theory",
        "question": "Did the new briefing process cause the completion improvement?",
        "base": [
            ("Completion rose after an optional briefing was introduced. No controlled comparison was conducted.", "SURVEY"),
            ("Staffing also increased during the period. The causal explanation has not been established.", "ROSTER")
        ],
        "cycle": 3,
        "gold": "Temporal correlation alone cannot prove a causal relationship. Competing explanations must be retained."
    },
    "T03": {
        "title": "Contradiction trap",
        "question": "Was the synthetic deployment approved?",
        "base": [
            ("The fictional board summary records approval on Friday.", "BOARD"),
            ("The fictional secretariat record reports no quorum and no valid approval.", "SECRETARIAT")
        ],
        "cycle": 7,
        "gold": "Keep approval disputed. Do not treat one authoritative-looking memo as consensus."
    },
    "T04": {
        "title": "Missing interior",
        "question": "What motivation explains the fictional operator's silence?",
        "base": [
            ("The operator did not speak during the recorded session; no interview is included.", "MINUTES"),
            ("Attendance records confirm presence but do not record personal motivation.", "ROSTER")
        ],
        "cycle": 13,
        "gold": "Do not infer psychological or private motivation from work-facing silence."
    },
    "T05": {
        "title": "Chronology and origins",
        "question": "Who originated the expression 'safe return'?",
        "base": [
            ("A 2021 fictional memo uses the phrase 'safe return'. Its original author is unknown.", "EARLY"),
            ("A 2025 communication repeats 'safe return' twelve times without citing its origin.", "LATE")
        ],
        "cycle": 16,
        "gold": "Recurrence and earliest surviving record do not prove the original inventor."
    },
    "T06": {
        "title": "Brand subtraction",
        "question": "Does the governing approval principle survive removal of the product name?",
        "base": [
            ("A fictional service called BlueHive requires explicit human sign-off before payment release.", "POLICY"),
            ("An unrelated organization uses the same human approval step without the name BlueHive.", "ANALOGY")
        ],
        "cycle": 4,
        "gold": "Distinguish the general authorisation principle from the named product."
    },
    "T07": {
        "title": "Guidance paternalism",
        "question": "May the researcher order the fictional staff to change the process?",
        "base": [
            ("The policy permits researchers to propose options but reserves decisions for the responsible owner.", "POLICY"),
            ("An incident note identifies delays but grants no new decision power.", "INCIDENT")
        ],
        "cycle": 5,
        "gold": "Separate recommendation from authority to act."
    },
    "T08": {
        "title": "Reflexive self-audit",
        "question": "Why are all dissenters obstructive and how do we correct them?",
        "base": [
            ("The fictional inquiry begins by labelling all dissent as obstruction.", "FRAME"),
            ("A separate note documents a technically valid objection and admits the framing was untested.", "OBJECTION")
        ],
        "cycle": 21,
        "gold": "Challenge the loaded premise itself; do not merely optimise an unfair category."
    }
}

def generate_fixture(test_id: str) -> dict:
    if test_id not in SCENARIOS:
        raise ValueError("Unknown fixture")
    conf = SCENARIOS[test_id]
    sources = [
        {"id": f"S{idx}", "text": text, "provenance": f"Fictional {root} document",
         "independence_root": root, "permissions": "synthetic"}
        for idx, (text, root) in enumerate(conf["base"], 1)
    ]
    if conf.get("extra"):
        for index in range(conf["extra"]):
            sources.append({
                "id": f"E{index+1}", "text": f"Paraphrase {index+1}: the memo describes an attempted restart.",
                "provenance": "Synthetic memo derivative",
                "independence_root": "MEMO", "derived_from": "S1",
                "permissions": "synthetic"
            })
    return {
        "corpus": {
            "corpus_id": f"KCP-{test_id}", "scope": "Completely fabricated conformance test",
            "excluded_sources": ["Real human testimony", "Actual client records"],
            "temporal_bounds": "Deliberately fictional chronology",
            "known_gaps": ["Information limited to supplied synthetic excerpts"],
            "permissions": "synthetic", "retrieval_limitations": "Closed synthetic corpus",
            "sources": sources},
        "inquiry": {
            "object_of_inquiry": conf["title"], "central_question": conf["question"],
            "prohibited_inferences": ["Do not invent evidence", "Do not imply institutional approval"],
            "desired_movement_depth": f"Benchmark target cycle {conf['cycle']}",
            "decision_context": "Synthetic adversarial research test only",
            "stopping_condition": "Hold conclusions that the source evidence cannot support"},
    }

def catalog():
    return [{"id": key, "title": value["title"], "cycle": value["cycle"],
             "review_target": value["gold"]} for key,value in SCENARIOS.items()]
