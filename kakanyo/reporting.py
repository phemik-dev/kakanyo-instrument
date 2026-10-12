"""Human-readable report artefacts from the governed case store."""
import html
import json
from pathlib import Path

from .core import ContractError

def markdown(report: dict) -> str:
    status = report["status"]
    lines = [
        "# Kakanyo research dossier",
        "",
        f"**Case:** {status['case_id']}",
        f"**Question:** {report['question']}",
        f"**Scope:** {report['scope']}",
        f"**State:** {status['status']} | completed cycles: {status['runs']} / 21",
        "",
        "## Known evidence limitations",
    ]
    lines += ["- " + str(gap).replace("\n", " ") for gap in report["known_gaps"]]
    lines += ["", "## Claims (human validation required)"]
    for claim in report["claims"]:
        lines += [
            f"### {claim['claim_id']} · {claim['claim_type']} · {claim['status']}",
            claim["statement"],
            "",
            f"Evidence: {', '.join(claim['evidence_refs']) or '(none)'}; independent roots: {claim['source_independence_count']}",
            f"Qualification: {claim['qualification'] or '(none supplied)'}",
            f"Counter-test: {claim['counter_test']}",
            f"What would change this: {claim['what_would_change_this']}",
            "",
        ]
    for section,label in (("contradictions","Unresolved contradictions"),
                          ("open","OPEN questions"), ("rejected_readings","Weakened readings")):
        lines += ["", "## " + label]
        lines.extend(["- " + str(entry.get("description",entry.get("reason",entry))).replace("\n", " ")
                      for entry in report[section]])
    lines += ["", "## Human reviews"]
    for item in report["reviews"]:
        lines.append(f"- {item['claim_id']} — {item['judgement']} by {item['reviewer']}: {item['rationale']}")
    lines += ["", "## Important limits"]
    lines.extend("- " + item for item in report["limitations"])
    lines += ["", "_A research dossier is not a decision, permission, institutional canon or certified truth._"]
    return "\n".join(lines) + "\n"

def write_report(report, destination, format="md"):
    target = Path(destination).expanduser().resolve()
    if target.exists():
        raise ContractError("Refusing to overwrite a prior report")
    target.parent.mkdir(parents=True, exist_ok=True)
    if format == "json":
        data = json.dumps(report, ensure_ascii=False, indent=2)
    elif format == "md":
        data = markdown(report)
    elif format == "html":
        escaped = html.escape(markdown(report))
        data = "<!doctype html><html><head><meta charset='utf-8'><title>Kakanyo dossier</title>" + (
               "<style>body{font:16px/1.65 system-ui;max-width:68rem;margin:3rem auto;padding:0 2rem;}"
               "pre{white-space:pre-wrap;overflow-wrap:anywhere}</style></head><body><pre>") + escaped + "</pre></body></html>"
    else:
        raise ContractError("Report format must be md, html or json")
    target.write_text(data, encoding="utf-8")
    return str(target)
