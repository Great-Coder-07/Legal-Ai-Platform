import re

try:
    from sentence_transformers import SentenceTransformer, util
    _ST_IMPORT_ERROR = None
except Exception as e:
    # Handles locked-down environments where torch DLL loading is blocked.
    SentenceTransformer = None
    util = None
    _ST_IMPORT_ERROR = e

from backend.services.risk_engine import assess_risk

model = None
label_embeddings = None
model_load_failed = False

labels = [
    "Definition of confidential information clause",
    "Obligations of confidentiality and non-disclosure clause",
    "Permitted disclosures and exceptions clause",
    "Term and duration of agreement clause",
    "Termination of agreement clause",
    "Return or destruction of confidential information clause",
    "Governing law and jurisdiction clause",
    "Dispute resolution and arbitration clause",
    "Remedies and injunctive relief clause",
    "Intellectual property ownership clause",
    "No license or rights granted clause",
    "Entire agreement and amendments clause",
    "Severability clause",
    "Notices and communications clause",
    "Parties and recitals clause",
]

RULE_LABELS = [
    ("Governing law and jurisdiction clause", [r"\bgoverned by\b", r"\bconstrued in accordance with\b", r"\bjurisdiction of\b", r"\bcourts?\b"]),
    ("Termination of agreement clause", [r"\bterminate\b", r"\btermination\b", r"\bwithout cause\b", r"\bseverance\b", r"\bat-will\b"]),
    ("Obligations of confidentiality and non-disclosure clause", [r"^\s*\d+\.\s*confidentiality\b", r"\bkeep confidential\b", r"\bconfidentiality\b", r"\btrade secrets\b", r"\bwill not disclose\b", r"\bproprietary information\b"]),
    ("Base salary and payment clause", [r"\bsalary\b", r"\bpayable\b", r"\bpayment\b", r"\binstallments?\b", r"\blate fee\b"]),
    ("Definition of confidential information clause", [r"\bfor the purposes of this agreement\b", r"\bconfidential information includes\b", r"\bmeans\b.{0,30}\bconfidential information\b"]),
    ("Intellectual property ownership clause", [r"\bintellectual property\b", r"\bownership\b", r"\bcopyright\b", r"\blicen[cs]e\b"]),
    ("Return or destruction of confidential information clause", [r"\breturn or destroy\b", r"\breturn\b.{0,40}\bconfidential\b", r"\bdestroy\b.{0,40}\bconfidential\b"]),
    ("Permitted disclosures and exceptions clause", [r"\bpublic domain\b", r"\bindependently developed\b", r"\brequired by law\b", r"\bthird party\b.{0,40}\bwithout\b.{0,20}\brestriction\b"]),
    ("Remedies and injunctive relief clause", [r"\binjunctive relief\b", r"\birreparable harm\b", r"\binterim relief\b"]),
    ("Dispute resolution and arbitration clause", [r"\barbitration\b", r"\bdispute resolution\b", r"\bdisputes?\b"]),
    ("Entire agreement and amendments clause", [r"\bentire agreement\b", r"\bamend(?:ed|ment)?\b", r"\bmodified only in writing\b"]),
    ("Severability clause", [r"\bseverab(?:ility|le)\b", r"\binvalid provision\b"]),
    ("Notices and communications clause", [r"\bnotices?\b", r"\bcommunications?\b", r"\bwritten notice\b"]),
    ("No license or rights granted clause", [r"\bno licen[cs]e\b", r"\bno rights granted\b"]),
    ("Term and duration of agreement clause", [r"\bfor a period of\b", r"\bthereafter\b", r"\bterm of employment\b", r"\byears?\b"]),
    ("Limitation of liability clause", [r"\blimitation of liability\b", r"\bliability\b.{0,30}\bunlimited\b", r"\bwithout financial cap\b", r"\bwithout any cap\b"]),
]

SKIP_PATTERNS = re.compile(
    r"^("
    r"this\s+(confidentiality|non.disclosure|nda|agreement)\s+"
    r"|this\s+agreement\s+is\s+made"
    r"|between\s+.{0,80}(party|parties)"
    r"|hereinafter\s+referred"
    r"|whereas"
    r"|now[\s,]+therefore"
    r"|in\s+witness\s+whereof"
    r"|signed\s+by|executed\s+by|authorized\s+signatory"
    r"|name\s*:|title\s*:|date\s*:|signature\s*:"
    r"|note\s*:"
    r"|\(note"
    r"|to\s+be\s+duly\s+signed"
    r"|key\s+managerial"
    r"|confidentiality\s+and\s+non\s+disclosure\s+agreement"
    r"|non.disclosure\s+agreement"
    r"|non.circumvention\s+agreement"
    r"|mutual\s+non.disclosure"
    r")",
    re.IGNORECASE,
)

RECITAL_PATTERN = re.compile(r"^[A-E]\.\s+\S", re.MULTILINE)


def get_model():
    global model, label_embeddings, model_load_failed
    if model_load_failed:
        return None

    if SentenceTransformer is None or util is None:
        model_load_failed = True
        if _ST_IMPORT_ERROR is not None:
            print(f"[classifier] sentence_transformers unavailable ({_ST_IMPORT_ERROR}), falling back to rule-based classifier.")
        else:
            print("[classifier] sentence_transformers not installed, falling back to rule-based classifier.")
        return None

    if model is None:
        try:
            print("[classifier] Loading Sentence Transformer model...")
            model = SentenceTransformer("all-MiniLM-L6-v2")
            label_embeddings = model.encode(labels, convert_to_tensor=True)
        except Exception as e:
            model_load_failed = True
            print(f"[classifier] Transformer model unavailable, falling back to rule-based classifier: {e}")
            return None

    return model


def classify_clause_by_rules(clause: str):
    text = clause.lower()
    best_label = None
    best_hits = 0

    for label, patterns in RULE_LABELS:
        hits = sum(1 for pattern in patterns if re.search(pattern, text))
        if hits > best_hits:
            best_label = label
            best_hits = hits

    if best_label:
        confidence = min(0.55 + (best_hits * 0.12), 0.9)
        return best_label, confidence

    if "confidential" in text or "non-disclosure" in text:
        return "Obligations of confidentiality and non-disclosure clause", 0.45

    return "Unclassified clause", 0.2


def segment_clauses(text: str) -> list:
    """
    NDA-aware segmenter that:
    - Splits on numbered clauses (1. / 1.1 / 1.1.1)
    - Splits on ALL CAPS headings
    - Skips obvious non-clause metadata blocks
    - Falls back to paragraph segmentation when structure is weak
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?i)page\s+\d+\s+of\s+\d+", "", text)
    text = re.sub(r"\-\s*\d+\s*\-", "", text)

    # Looks for lines starting with "EXHIBIT A", "SCHEDULE 1", "APPENDIX", etc.
    exhibit_pattern = re.search(
        r'\n(?=(?:EXHIBIT|SCHEDULE|APPENDIX|ANNEX)\s+[A-Z0-9]{1,3}\b)', 
        text, 
        re.IGNORECASE
    )
    if exhibit_pattern:
        # Chop off the text exactly where the Exhibit starts
        text = text[:exhibit_pattern.start()]

    split_pattern = re.compile(
        r"\n\s*(?="
        r"(?:\d+[\.\)]\d*[\.\)]?\s)"
        r"|(?:[A-Z][A-Z\s\-]{4,}\n)"
        r")"
    )

    raw_chunks = split_pattern.split(text)

    all_chunks = []
    for chunk in raw_chunks:
        all_chunks.extend(re.split(r"\n{2,}", chunk))

    if len(all_chunks) <= 1:
        all_chunks = re.split(r"\n{2,}", text)

    cleaned = []
    for chunk in all_chunks:
        chunk = chunk.strip()
        if len(chunk) < 40:
            continue

        first_line = chunk.split("\n")[0].strip().lower()
        lower_chunk = chunk.lower()
        first_line_clean = first_line.lstrip("\"'(- ")

        # Skip only short opening blocks, not the whole contract body.
        if (
            first_line_clean.endswith("agreement")
            and ("made and entered into" in lower_chunk or "by and between" in lower_chunk)
            and len(chunk) < 420
        ):
            continue

        if SKIP_PATTERNS.match(first_line_clean):
            continue

        if RECITAL_PATTERN.match(chunk) and len(chunk) < 400:
            continue

        upper_ratio = sum(1 for c in chunk if c.isupper()) / max(len(chunk), 1)
        if upper_ratio > 0.55 and len(chunk) < 300:
            continue

        blank_ratio = chunk.count("_") / max(len(chunk), 1)
        if blank_ratio > 0.15:
            continue
        # Skip document title blocks (all caps title + note in brackets)
        if re.match(r'^[A-Z\s\(&]{10,}$', chunk.split('\n')[0].strip()):
            continue

        # Skip lettered recitals more aggressively — A. B. C. D. E.
        if re.match(r'^[A-E]\.\s+', chunk) and len(chunk) < 600:
            continue

        # Skip chunks that contain "note: to be" or signature instructions anywhere
        if re.search(r'note\s*:\s*to\s+be\s+(duly\s+)?signed|key\s+managerial\s+personnel', 
                     chunk, re.IGNORECASE):
            continue

        cleaned.append(chunk)

    # Never return empty for long parseable text.
    if not cleaned and len(text.strip()) >= 220:
        cleaned = [p.strip() for p in re.split(r"\n{2,}", text) if len(p.strip()) >= 40][:40]

    # The Max Size Safety Net
    MAX_CHARS = 2000 # Roughly 400-500 tokens (Safe for embedding models)
    safe_chunks = []
    
    for chunk in cleaned:
        if len(chunk) <= MAX_CHARS:
            safe_chunks.append(chunk)
        else:
            # If a chunk is massive, split it by single newlines first
            sub_chunks = chunk.split('\n')
            current_piece = ""
            
            for sub in sub_chunks:
                # If adding the next line exceeds the limit, save the piece and start a new one
                if len(current_piece) + len(sub) > MAX_CHARS and current_piece:
                    safe_chunks.append(current_piece.strip())
                    current_piece = sub + "\n"
                else:
                    current_piece += sub + "\n"
            
            if current_piece.strip():
                safe_chunks.append(current_piece.strip())

    return safe_chunks


def classify_clause(clause: str):
    rule_label, rule_confidence = classify_clause_by_rules(clause)
    mdl = get_model()

    if mdl is None:
        return rule_label, rule_confidence

    try:
        clause_input = clause[:600]
        clause_emb = mdl.encode(clause_input, convert_to_tensor=True)
        scores = util.cos_sim(clause_emb, label_embeddings)[0]
        best_idx = scores.argmax().item()
        confidence = float(scores[best_idx])
        model_label = labels[best_idx]

        if confidence < 0.25:
            return rule_label, max(rule_confidence, confidence)

        if rule_label != "Unclassified clause" and rule_confidence >= 0.79:
            return rule_label, max(rule_confidence, confidence)

        return model_label, confidence
    except Exception as e:
        print(f"[classifier] Embedding classification failed, using rules: {e}")
        return rule_label, rule_confidence


def run_contract_analysis(text: str) -> dict:
    clauses = segment_clauses(text)
    total_detected = len(clauses)
    analyzed_clauses = []

    for clause in clauses:
        try:
            top_label, confidence = classify_clause(clause)

            try:
                risk = assess_risk(clause, top_label)
            except Exception:
                risk = {
                    "level": "UNKNOWN",
                    "reason": "Risk engine failed",
                    "score": 0,
                    "category": "unknown",
                    "summary": "Risk engine failed.",
                    "matched_rules": [],
                    "positive_signals": [],
                    "recommendations": [],
                }

            analyzed_clauses.append({
                "clause_text": clause,
                "type": top_label,
                "confidence": round(confidence, 3),
                "risk_level": risk["level"],
                "risk_reason": risk["reason"],
                "risk_score": risk.get("score", 0),
                "risk_category": risk.get("category", "unknown"),
                "risk_summary": risk.get("summary", ""),
                "matched_rules": risk.get("matched_rules", []),
                "positive_signals": risk.get("positive_signals", []),
                "recommendations": risk.get("recommendations", []),
                "review_notice": risk.get("review_notice", ""),
            })
        except Exception as e:
            print(f"[contract_analyzer] Error processing clause: {e}")

    high = sum(1 for c in analyzed_clauses if c["risk_level"] == "HIGH")
    medium = sum(1 for c in analyzed_clauses if c["risk_level"] == "MEDIUM")
    low = sum(1 for c in analyzed_clauses if c["risk_level"] == "LOW")
    top_recommendations = []

    for clause in analyzed_clauses:
        for recommendation in clause.get("recommendations", []):
            if recommendation not in top_recommendations:
                top_recommendations.append(recommendation)

    return {
        "pipeline": "NDA Contract Analysis (Embedding-Based)",
        "total_clauses_detected": total_detected,
        "total_clauses_analyzed": len(analyzed_clauses),
        "risk_summary": {
            "HIGH": high,
            "MEDIUM": medium,
            "LOW": low,
            "top_recommendations": top_recommendations[:8],
        },
        "analyzed_clauses": analyzed_clauses,
    }
