"""Bounded, explicit local document intake. No implicit network reads."""
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path

from .core import ContractError, validate_case

EXTENSIONS={".txt", ".md", ".markdown", ".csv", ".json", ".html", ".htm", ".pdf", ".docx"}
MAX_FILE_BYTES=10_000_000
MAX_FILES=250

class _ReadableHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip=0
        self.text=[]
    def handle_starttag(self,tag,attrs):
        if tag in {"script","style","noscript"}:self.skip+=1
    def handle_endtag(self,tag):
        if tag in {"script","style","noscript"}:self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip and data.strip():self.text.append(data.strip())

def extract_text(file: Path):
    ext=file.suffix.lower()
    if ext in {".txt",".md",".markdown",".csv",".json"}:
        return file.read_text(encoding="utf-8-sig")
    if ext in {".html",".htm"}:
        parser=_ReadableHTML()
        parser.feed(file.read_text(encoding="utf-8-sig"))
        return "\n".join(parser.text)
    if ext==".pdf":
        try:from pypdf import PdfReader
        except ImportError as exc:
            raise ContractError("PDF intake requires: pip install 'kakanyo-instrument[documents]'") from exc
        from io import BytesIO
        reader=PdfReader(BytesIO(file.read_bytes()))
        extracted="\n".join(page.extract_text() or "" for page in reader.pages)
        if not extracted.strip():
            raise ContractError("No extractable PDF text; OCR is not silently performed")
        return extracted
    if ext==".docx":
        try:from docx import Document
        except ImportError as exc:
            raise ContractError("DOCX intake requires: pip install 'kakanyo-instrument[documents]'") from exc
        d=Document(str(file))
        lines=[p.text for p in d.paragraphs if p.text.strip()]
        for table in d.tables:
            for row in table.rows:
                lines.append(" | ".join(c.text for c in row.cells))
        return "\n".join(lines)
    raise ContractError(f"Unsupported file type: {ext}")

def case_from_directory(directory, corpus_id, question, scope, permissions="private",
                        stopping_condition="Stop where the supplied evidence cannot support a conclusion"):
    root=Path(directory).expanduser().resolve()
    if not root.is_dir():raise ContractError("Source must be an existing directory")
    if permissions not in {"private","synthetic","approved-for-external-model"}:
        raise ContractError("Permissions must be explicitly classified")
    paths=sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS
                 and not p.is_symlink() and not any(x.startswith(".") for x in p.relative_to(root).parts))
    if not paths:raise ContractError("No supported source documents")
    if len(paths)>MAX_FILES:raise ContractError("Too many source documents; break into bounded corpora")
    sources=[];known_hashes={}
    for i,path in enumerate(paths,1):
        if path.stat().st_size>MAX_FILE_BYTES:
            raise ContractError("Source larger than 10MB: "+str(path.relative_to(root)))
        text=extract_text(path)
        if not text.strip():raise ContractError("Empty extracted document: "+str(path.relative_to(root)))
        doc_hash=sha256(text.encode("utf-8")).hexdigest()
        root_id=known_hashes.setdefault(doc_hash,doc_hash)
        sources.append({"id":f"D{i:04d}","text":text,
                        "provenance":str(path.relative_to(root)),
                        "independence_root":root_id,
                        "permissions":permissions,
                        "sha256":doc_hash})
    case={"corpus":{
        "corpus_id":corpus_id,"scope":scope,
        "sources":sources,"excluded_sources":["Sources outside selected local directory"],
        "temporal_bounds":"Not verified; determine during inquiry",
        "known_gaps":["No proof that distinct documents are independent; identical text is grouped by hash.",
                      "Chronology and document completeness are not independently verified."],
        "permissions":permissions,"retrieval_limitations":"Local document extraction only; images and attachments not inferred"},
        "inquiry":{
            "object_of_inquiry":scope,"central_question":question,
            "prohibited_inferences":["Private psychological states without testimony",
                                      "Unsupported causal conclusions", "Unapproved actions"],
            "desired_movement_depth":"I–V (21 cycles); reviewer may stop early",
            "decision_context":"Research and synthesis, no unilateral release authority",
            "stopping_condition":stopping_condition}}
    validate_case(case)
    return case
