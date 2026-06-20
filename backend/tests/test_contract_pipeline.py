import unittest
from unittest.mock import patch

from backend.pipelines import contract_analyzer
from backend.services.parsers import parse_document
from backend.services.risk_engine import assess_risk


class ContractPipelineTests(unittest.TestCase):
    def test_rule_based_classifier_handles_governing_law_without_model(self):
        clause = "This Agreement shall be construed in accordance with the laws of the State of Texas."

        with patch.object(contract_analyzer, "model_load_failed", True):
            label, confidence = contract_analyzer.classify_clause(clause)

        self.assertEqual(label, "Governing law and jurisdiction clause")
        self.assertGreaterEqual(confidence, 0.55)

    def test_rule_based_classifier_handles_termination_without_model(self):
        clause = "The Employer may terminate this Agreement immediately without cause and without notice."

        with patch.object(contract_analyzer, "model_load_failed", True):
            label, confidence = contract_analyzer.classify_clause(clause)

        self.assertEqual(label, "Termination of agreement clause")
        self.assertGreaterEqual(confidence, 0.55)

    def test_termination_without_notice_and_immediate_language_score_correctly(self):
        clause = "The Employer may terminate this Agreement immediately without cause and without notice."
        result = assess_risk(clause, "Termination of agreement clause")

        self.assertEqual(result["level"], "HIGH")
        self.assertIn("Termination without cause", result["reason"])
        self.assertIn("Immediate termination", result["reason"])
        self.assertIn("Termination without notice", result["reason"])

    def test_without_limitation_is_not_treated_as_unlimited_liability(self):
        clause = (
            "For the purposes of this Agreement, confidential information includes proprietary materials "
            "including without limitation specifications, drawings, designs, software and knowhow."
        )
        result = assess_risk(clause, "Definition of confidential information clause")

        self.assertEqual(result["level"], "LOW")
        self.assertNotIn("Unlimited liability exposure", result["reason"])

    def test_negative_transfer_language_is_not_flagged_as_ownership_transfer(self):
        clause = "There is no explicit or implied transfer of ownership to the receiving party."
        result = assess_risk(clause, "Intellectual property ownership clause")

        self.assertEqual(result["level"], "LOW")
        self.assertNotIn("Ownership transfer", result["reason"])

    def test_parse_document_cleans_plain_text(self):
        raw = b"Line one\nline two\n\n\nPage 1 of 3\n"
        parsed = parse_document("sample.txt", raw)

        self.assertIn("Line one line two", parsed)
        self.assertNotIn("Page 1 of 3", parsed)

    def test_injunctive_relief_is_medium_not_low(self):
        clause = "The disclosing party may seek injunctive relief for irreparable harm."
        result = assess_risk(clause, "Remedies and injunctive relief clause")

        self.assertEqual(result["level"], "MEDIUM")
        self.assertIn("Injunctive-relief provision", result["reason"])

    def test_segmenter_does_not_drop_unnumbered_contract_body(self):
        text = (
            "EMPLOYMENT AGREEMENT\\n"
            "This Employment Agreement is made and entered into by and between Employer and Employee.\\n\\n"
            "The Employer may terminate the Employee without cause and without notice. "
            "Compensation shall be payable monthly. This agreement is governed by the laws of California."
        )
        clauses = contract_analyzer.segment_clauses(text)

        self.assertGreaterEqual(len(clauses), 1)


if __name__ == "__main__":
    unittest.main()
