import os
import re


WORD_TO_NUMBER = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}

CONFIDENTIALITY_CATEGORIES = {
    "confidentiality",
    "confidentiality_definition",
    "permitted_disclosure",
    "return_of_information",
}

JURISDICTION_ALIASES = {
    "india": ("india", "indian"),
    "delaware": ("delaware",),
    "california": ("california",),
    "new_york": ("new york", "new york state"),
    "texas": ("texas",),
    "england_wales": ("england and wales", "england & wales", "england", "wales"),
    "scotland": ("scotland",),
    "singapore": ("singapore",),
    "australia": ("australia",),
    "canada": ("canada",),
    "ireland": ("ireland",),
}


def _normalize_clause_type(clause_type: str) -> str:
    normalized = (clause_type or "").strip().lower()

    # Specific confidentiality sub-types must be checked before the broad
    # "confidential" match.
    if "return or destruction" in normalized or "return or destroy" in normalized:
        return "return_of_information"
    if "permitted disclosure" in normalized or "exceptions" in normalized:
        return "permitted_disclosure"
    if "definition of confidential" in normalized:
        return "confidentiality_definition"
    if "termination" in normalized:
        return "termination"
    if "governing law" in normalized or "jurisdiction" in normalized:
        return "governing_law"
    if "force majeure" in normalized:
        return "force_majeure"
    if "payment" in normalized or "salary" in normalized:
        return "payment"
    if "liability" in normalized or "damages" in normalized:
        return "liability"
    if "intellectual property" in normalized or "ownership" in normalized or "license" in normalized:
        return "ip"
    if "confidential" in normalized or "non-disclosure" in normalized:
        return "confidentiality"
    if "injunctive relief" in normalized or "remedies" in normalized:
        return "remedies"
    if "term and duration" in normalized or normalized == "duration":
        return "duration"
    if "dispute resolution" in normalized or "arbitration" in normalized:
        return "dispute_resolution"
    return normalized or "unclassified"


def _extract_duration(text: str) -> tuple[int | None, str | None]:
    number_pattern = "|".join(WORD_TO_NUMBER)
    patterns = (
        (rf"\b(?:[a-z]+\s*)?\((\d+)\)\s*(years?|months?)\b", True),
        (r"\b(\d+)\s*(years?|months?)\b", True),
        (rf"\b({number_pattern})\s+(years?|months?)\b", False),
    )

    for pattern, numeric in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        amount = int(match.group(1)) if numeric else WORD_TO_NUMBER[match.group(1)]
        unit = match.group(2)
        months = amount * 12 if unit.startswith("year") else amount
        return months, match.group(0)

    return None, None


def _append_unique(items: list, value: str) -> None:
    if value and value not in items:
        items.append(value)


def _extract_evidence(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return ""


def _add_risk(
    matched_rules: list,
    reasons: list,
    recommendations: list,
    rule_id: str,
    label: str,
    impact: int,
    evidence: str,
    recommendation: str | None = None,
) -> int:
    if any(rule["rule_id"] == rule_id for rule in matched_rules):
        return 0
    matched_rules.append(
        {
            "rule_id": rule_id,
            "label": label,
            "impact": impact,
            "evidence": evidence,
        }
    )
    _append_unique(reasons, label)
    if recommendation:
        _append_unique(recommendations, recommendation)
    return impact


def _add_positive(
    positive_signals: list,
    label: str,
    evidence: str,
    impact: int = 0,
) -> int:
    if any(signal["label"] == label for signal in positive_signals):
        return 0
    positive_signals.append(
        {
            "label": label,
            "evidence": evidence,
            "impact": impact,
        }
    )
    return impact


def _summarize_clause(level: str, reasons: list, positives: list) -> str:
    if reasons:
        return f"{level} review priority driven by: {', '.join(reasons[:3])}."
    if positives:
        labels = ", ".join(item["label"] for item in positives[:2])
        return f"{level} review priority with protective signals such as {labels}."
    return "LOW review priority; no material rule-based concerns detected."


def _jurisdiction_key(value: str) -> str:
    normalized = re.sub(r"[^a-z_ ]", "", (value or "").strip().lower()).replace(" ", "_")
    for key, aliases in JURISDICTION_ALIASES.items():
        if normalized == key or any(normalized == alias.replace(" ", "_") for alias in aliases):
            return key
    return normalized


def _detect_jurisdiction(text: str) -> tuple[str | None, str]:
    for key, aliases in JURISDICTION_ALIASES.items():
        for alias in sorted(aliases, key=len, reverse=True):
            match = re.search(rf"\b{re.escape(alias)}\b", text)
            if match:
                return key, match.group(0)
    return None, ""


def assess_risk(
    clause_text: str,
    clause_type: str,
    home_jurisdiction: str | None = None,
) -> dict:
    """
    Produce a conservative issue-spotting score for contract review.

    Scores indicate review priority, not enforceability or a legal conclusion:
      LOW: 0-1, MEDIUM: 2-4, HIGH: 5+
    """
    text = re.sub(r"\s+", " ", (clause_text or "").lower()).strip()
    category = _normalize_clause_type(clause_type)
    home_jurisdiction_key = _jurisdiction_key(
        home_jurisdiction or os.getenv("LEGAL_HOME_JURISDICTION", "india")
    )
    score = 0
    reasons: list[str] = []
    matched_rules: list[dict] = []
    positive_signals: list[dict] = []
    recommendations: list[str] = []

    cap_pattern = re.search(
        r"\b(?:aggregate )?liability\b.{0,60}\b(?:capped at|limited to|shall not exceed)\b"
        r"|\b(?:capped at|limited to|shall not exceed)\b.{0,60}\b(?:fees paid|liability)\b",
        text,
    )
    if cap_pattern:
        score += _add_positive(
            positive_signals,
            "Liability cap present",
            cap_pattern.group(0),
            -1,
        )

    # Liability and damages
    if category == "liability":
        unlimited_pattern = re.search(
            r"\bunlimited liability\b"
            r"|\bliability\b.{0,35}\b(?:is |shall be )?unlimited\b"
            r"|\bliability\b.{0,35}\b(?:without (?:any |financial )?cap|without (?:financial )?limit|no limit)\b",
            text,
        )
        if unlimited_pattern:
            score += _add_risk(
                matched_rules,
                reasons,
                recommendations,
                "liability_unlimited",
                "Unlimited liability exposure",
                6,
                unlimited_pattern.group(0),
                "Consider a clear monetary cap and review any justified carve-outs separately.",
            )

        exclusion_pattern = re.search(
            r"\b(?:not liable for|neither party.{0,25}liable for|exclude[sd]?|excluding)\b.{0,60}"
            r"\b(?:indirect|consequential|special|incidental)\b.{0,35}\bdamages\b",
            text,
        )
        mentions_indirect = re.search(r"\b(?:indirect|consequential)\b.{0,25}\bdamages\b", text)
        if mentions_indirect and not exclusion_pattern:
            score += _add_risk(
                matched_rules,
                reasons,
                recommendations,
                "damages_not_excluded",
                "Indirect or consequential damages not clearly excluded",
                2,
                mentions_indirect.group(0),
                "Clarify whether indirect, consequential, special, and incidental damages are excluded.",
            )
        elif exclusion_pattern:
            score += _add_positive(
                positive_signals,
                "Damages exclusion present",
                exclusion_pattern.group(0),
            )

    # Termination
    if category == "termination":
        if "without cause" in text:
            score += _add_risk(
                matched_rules,
                reasons,
                recommendations,
                "termination_without_cause",
                "Termination without cause",
                3,
                "without cause",
                "Consider a reasonable written notice period for no-cause termination.",
            )

        immediate_match = re.search(r"\bimmediate termination\b|\bterminate\b.{0,25}\bimmediately\b", text)
        if immediate_match:
            score += _add_risk(
                matched_rules,
                reasons,
                recommendations,
                "termination_immediate",
                "Immediate termination right",
                2,
                immediate_match.group(0),
                "Limit immediate termination to defined serious events such as material breach or illegality.",
            )

        if re.search(r"\bwithout (?:prior |written )?notice\b|\bno notice\b", text):
            score += _add_risk(
                matched_rules,
                reasons,
                recommendations,
                "termination_without_notice",
                "Termination without notice",
                2,
                _extract_evidence(text, [r"without (?:prior |written )?notice", r"no notice"]),
                "Consider a commercially reasonable notice period.",
            )
        elif "notice" not in text and ("terminate" in text or "termination" in text):
            score += _add_risk(
                matched_rules,
                reasons,
                recommendations,
                "termination_no_notice",
                "No notice period stated",
                2,
                "notice not found",
                "State the required notice period and delivery method.",
            )
        else:
            score += _add_positive(
                positive_signals,
                "Notice period present",
                _extract_evidence(text, [r"\bnotice\b"]),
            )

        cure_match = re.search(r"\b(?:cure period|opportunity to cure|days? to cure)\b", text)
        if cure_match:
            score += _add_positive(
                positive_signals,
                "Cure period present",
                cure_match.group(0),
                -1,
            )

    # Duration. A conventional fixed term is informational, not inherently risky.
    duration_months, duration_evidence = _extract_duration(text)
    if category in {"confidentiality", "duration"} and duration_months is not None:
        if duration_months >= 60:
            score += _add_risk(
                matched_rules,
                reasons,
                recommendations,
                "duration_long",
                f"Long duration ({duration_months // 12} years)",
                2,
                duration_evidence or "",
                "Confirm that the duration is proportionate to the information and commercial need.",
            )
        else:
            score += _add_positive(
                positive_signals,
                f"Defined duration ({duration_evidence})",
                duration_evidence or "",
            )

    if category in {"confidentiality", "duration"} and re.search(r"\bperpetual(?:ly)?\b|\bindefinite(?:ly)?\b", text):
        score += _add_risk(
            matched_rules,
            reasons,
            recommendations,
            "duration_perpetual",
            "Open-ended confidentiality duration",
            3,
            _extract_evidence(text, [r"perpetual(?:ly)?", r"indefinite(?:ly)?"]),
            "Consider limiting ordinary confidential information while preserving appropriate protection for trade secrets.",
        )

    # Confidentiality and disclosure
    if "required by law" in text or "court order" in text:
        score += _add_positive(
            positive_signals,
            "Standard legal disclosure carve-out",
            _extract_evidence(text, [r"required by law", r"court order"]),
        )

    if (
        category == "confidentiality"
        and duration_months is None
        and not re.search(r"\bperpetual(?:ly)?\b|\bindefinite(?:ly)?\b|\bno expir", text)
    ):
        score += _add_risk(
            matched_rules,
            reasons,
            recommendations,
            "no_duration",
            "No confidentiality duration specified",
            2,
            "duration not found",
            "State a duration, with separate treatment where trade-secret protection should continue.",
        )

    if category == "confidentiality_definition":
        broad_match = re.search(
            r"\bany and all (?:information|data)\b"
            r"|\ball information\b.{0,60}\b(?:confidential|proprietary)\b",
            text,
        )
        exclusion_terms = (
            "public domain",
            "already known",
            "independently developed",
            "rightfully received",
        )
        if broad_match and not any(term in text for term in exclusion_terms):
            score += _add_risk(
                matched_rules,
                reasons,
                recommendations,
                "broad_definition",
                "Broad confidentiality definition without clear exclusions",
                2,
                broad_match.group(0),
                "Add customary exclusions for public, previously known, independently developed, and lawfully received information.",
            )

    if category == "permitted_disclosure" and "regulatory" in text and "required by law" not in text:
        score += _add_risk(
            matched_rules,
            reasons,
            recommendations,
            "disclosure_regulatory_broad",
            "Regulatory disclosure wording is not limited to mandatory disclosures",
            2,
            "regulatory",
            "Limit disclosure to what applicable law or a competent authority requires.",
        )

    if category in {"confidentiality", "return_of_information"}:
        receiving_obligation = re.search(r"\breceiving party\s+(?:shall|must|agrees|will)\b", text)
        mutual_language = (
            re.search(r"\bdisclosing party\s+(?:shall|must|agrees|will)\b", text)
            or re.search(r"\beach party\s+(?:shall|must|agrees|will)\b", text)
            or "both parties" in text
            or "mutual" in text
        )
        if receiving_obligation and not mutual_language:
            score += _add_risk(
                matched_rules,
                reasons,
                recommendations,
                "one_sided_receiving_party",
                "One-sided confidentiality obligation",
                2,
                receiving_obligation.group(0),
                "Confirm that a one-way NDA is intended; otherwise use reciprocal obligations.",
            )
        elif receiving_obligation and mutual_language:
            score += _add_positive(
                positive_signals,
                "Mutual obligations present",
                "mutual party obligations",
            )

    return_destroy = re.search(r"\breturn (?:or|and) destroy\b|\bdestroy (?:or|and) return\b", text)
    if category == "return_of_information" and return_destroy:
        score += _add_risk(
            matched_rules,
            reasons,
            recommendations,
            "return_destroy",
            "Return or destruction obligation",
            1,
            return_destroy.group(0),
            "Check practical carve-outs for backups, legal holds, and automatically retained records.",
        )

    if category == "return_of_information" and "certify in writing" in text:
        score += _add_risk(
            matched_rules,
            reasons,
            recommendations,
            "return_certification",
            "Written destruction certification required",
            1,
            "certify in writing",
            "Confirm who can certify compliance and within what period.",
        )

    if category in CONFIDENTIALITY_CATEGORIES and re.search(
        r"\bshared freely\b|\bwithout restriction\b|\bfreely shared\b", text
    ):
        score += _add_risk(
            matched_rules,
            reasons,
            recommendations,
            "unrestricted_sharing",
            "Information may be shared without restriction",
            4,
            _extract_evidence(text, [r"shared freely", r"without restriction", r"freely shared"]),
            "Define permitted recipients, purpose limitations, and required safeguards.",
        )

    if category in {"confidentiality", "confidentiality_definition"} and re.search(
        r"\b(?:oral|verbal)\b.{0,60}\b(?:confidential|disclos|information)\b", text
    ):
        score += _add_risk(
            matched_rules,
            reasons,
            recommendations,
            "oral_disclosures",
            "Oral disclosures included without a confirmation mechanism",
            1,
            _extract_evidence(text, [r"(?:oral|verbal).{0,50}(?:confidential|disclos|information)"]),
            "Consider requiring oral disclosures to be identified or confirmed in writing within a set period.",
        )

    survival_match = re.search(r"\bsurviv(?:e|es|al)\b.{0,35}\btermination\b", text)
    if category in CONFIDENTIALITY_CATEGORIES and survival_match:
        if duration_months is None and not re.search(r"\btrade secrets?\b", text):
            score += _add_risk(
                matched_rules,
                reasons,
                recommendations,
                "survival_unlimited",
                "Post-termination obligations have no stated limit",
                2,
                survival_match.group(0),
                "Define the survival period, with tailored treatment for trade secrets where appropriate.",
            )
        else:
            score += _add_positive(
                positive_signals,
                "Defined post-termination protection",
                survival_match.group(0),
            )

    # Governing law is an operational review point, not a statement that the
    # selected law is invalid or inferior.
    if category == "governing_law":
        detected_jurisdiction, jurisdiction_evidence = _detect_jurisdiction(text)
        if detected_jurisdiction and detected_jurisdiction != home_jurisdiction_key:
            score += _add_risk(
                matched_rules,
                reasons,
                recommendations,
                "governing_law_foreign",
                "Non-home governing law or forum",
                2,
                jurisdiction_evidence,
                "Confirm cost, counsel availability, dispute venue, and enforceability implications for the parties.",
            )
        elif detected_jurisdiction == home_jurisdiction_key:
            score += _add_positive(
                positive_signals,
                "Home jurisdiction selected",
                jurisdiction_evidence,
            )
        else:
            score += _add_risk(
                matched_rules,
                reasons,
                recommendations,
                "governing_law_unclear",
                "Governing law or forum is unclear",
                2,
                "jurisdiction not identified",
                "Specify the governing law and the court or arbitration forum.",
            )

    # Payment
    if category == "payment" and "non-refundable" in text:
        score += _add_risk(
            matched_rules,
            reasons,
            recommendations,
            "payment_non_refundable",
            "Non-refundable payment",
            2,
            "non-refundable",
            "Tie non-refundable amounts to defined work, milestones, or committed costs.",
        )

    # Remedies and control
    if category == "remedies" and ("injunctive relief" in text or "irreparable harm" in text):
        score += _add_risk(
            matched_rules,
            reasons,
            recommendations,
            "remedy_injunctive_relief",
            "Injunctive-relief provision",
            2,
            _extract_evidence(text, [r"injunctive relief", r"irreparable harm"]),
            "Check whether the remedy is mutual and consistent with the dispute-resolution clause.",
        )

    if "sole discretion" in text:
        score += _add_risk(
            matched_rules,
            reasons,
            recommendations,
            "control_sole_discretion",
            "Unilateral discretion",
            2,
            "sole discretion",
            "Consider objective standards, reasonableness, or mutual approval where appropriate.",
        )

    # Intellectual property
    if category == "ip" and re.search(r"\btransfer of ownership\b", text) and not re.search(
        r"\bno (?:explicit or implied )?transfer of ownership\b", text
    ):
        score += _add_risk(
            matched_rules,
            reasons,
            recommendations,
            "ip_transfer_ownership",
            "Intellectual-property ownership transfer",
            3,
            "transfer of ownership",
            "Confirm the intended assets, existing IP carve-outs, and whether a limited license would suffice.",
        )

    if category == "ip" and "royalty-free" in text and "irrevocable" in text:
        score += _add_risk(
            matched_rules,
            reasons,
            recommendations,
            "ip_irrevocable_license",
            "Irrevocable royalty-free license",
            3,
            _extract_evidence(text, [r"royalty-free", r"irrevocable"]),
            "Review scope, duration, territory, sublicensing, and permitted purpose.",
        )

    # Force-majeure wording varies by transaction. Missing a single named event
    # should prompt review, but should not itself increase the risk score.
    if category == "force_majeure":
        if re.search(r"\bepidemic\b|\bpandemic\b|\bgovernment(?:al)? action\b", text):
            score += _add_positive(
                positive_signals,
                "Modern disruption events addressed",
                _extract_evidence(text, [r"epidemic", r"pandemic", r"government(?:al)? action"]),
            )
        else:
            _append_unique(
                recommendations,
                "Check whether the listed force-majeure events and notice/mitigation duties fit the transaction.",
            )

    normalized_score = max(score, 0)
    if normalized_score >= 5:
        level = "HIGH"
    elif normalized_score >= 2:
        level = "MEDIUM"
    else:
        level = "LOW"

    if not recommendations and level == "LOW":
        recommendations.append(
            "No immediate rule-based redraft priority; confirm the clause fits the transaction and applicable law."
        )

    return {
        "level": level,
        "score": normalized_score,
        "category": category,
        "reason": "; ".join(reasons) if reasons else "No material rule-based concerns detected",
        "summary": _summarize_clause(level, reasons, positive_signals),
        "matched_rules": matched_rules,
        "positive_signals": positive_signals,
        "recommendations": recommendations,
        "review_notice": (
            "Automated issue-spotting only. Risk depends on the parties, transaction, bargaining position, "
            "governing law, and complete agreement."
        ),
    }
