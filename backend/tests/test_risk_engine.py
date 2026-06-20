import unittest

from backend.services.risk_engine import assess_risk


class RiskEngineTests(unittest.TestCase):
    def test_classifier_label_maps_to_termination_rules(self):
        clause = "Either party may terminate this Agreement without cause with immediate termination."
        result = assess_risk(clause, "Termination of agreement clause")

        self.assertEqual(result["level"], "HIGH")
        self.assertEqual(result["category"], "termination")
        self.assertGreaterEqual(result["score"], 7)
        self.assertIn("Termination without cause", result["reason"])
        self.assertIn("Immediate termination", result["reason"])
        self.assertIn("No notice period", result["reason"])
        self.assertTrue(result["matched_rules"])
        self.assertTrue(result["recommendations"])

    def test_governing_law_label_detects_foreign_jurisdiction(self):
        clause = "This Agreement is governed by the laws of Delaware, and disputes shall be resolved there."
        result = assess_risk(clause, "Governing law and jurisdiction clause")

        self.assertEqual(result["level"], "MEDIUM")
        self.assertEqual(result["category"], "governing_law")
        self.assertIn("Non-home governing law", result["reason"])
        self.assertTrue(any(rule["rule_id"] == "governing_law_foreign" for rule in result["matched_rules"]))

    def test_required_by_law_carveout_is_not_flagged_as_disclosure_risk(self):
        clause = (
            "The Receiving Party may disclose Confidential Information if required by law "
            "or pursuant to a valid court order."
        )
        result = assess_risk(clause, "Permitted disclosures and exceptions clause")

        self.assertEqual(result["level"], "LOW")
        self.assertNotIn("Broad regulatory disclosure language", result["reason"])
        self.assertTrue(any(signal["label"] == "Standard legal disclosure carve-out" for signal in result["positive_signals"]))

    def test_plain_shall_language_does_not_create_false_positive(self):
        clause = "The parties shall keep all Confidential Information strictly confidential for two years."
        result = assess_risk(clause, "Obligations of confidentiality and non-disclosure clause")

        self.assertEqual(result["level"], "LOW")
        self.assertTrue(any(signal["label"] == "Defined duration (two years)" for signal in result["positive_signals"]))
        self.assertNotIn("One-sided obligation", result["reason"])
        self.assertNotIn("No confidentiality duration", result["reason"])

    def test_one_sided_receiving_party_obligation_is_flagged(self):
        clause = "The Receiving Party shall return or destroy all Confidential Information and certify in writing."
        result = assess_risk(clause, "Return or destruction of confidential information clause")

        self.assertEqual(result["level"], "MEDIUM")
        self.assertIn("One-sided confidentiality obligation", result["reason"])
        self.assertIn("Return or destruction obligation", result["reason"])
        self.assertIn("Written destruction certification required", result["reason"])
        self.assertEqual(len(result["matched_rules"]), 3)

    def test_protective_signals_are_captured_for_balanced_clause(self):
        clause = (
            "The Receiving Party shall protect the information, the Disclosing Party shall label it, "
            "liability shall be limited to fees paid, and disclosures required by law are permitted."
        )
        result = assess_risk(clause, "Obligations of confidentiality and non-disclosure clause")

        self.assertEqual(result["level"], "LOW")
        self.assertTrue(any(signal["label"] == "Mutual obligations present" for signal in result["positive_signals"]))
        self.assertTrue(any(signal["label"] == "Liability cap present" for signal in result["positive_signals"]))
        self.assertTrue(result["recommendations"])

    def test_positive_signal_includes_score_reduction_when_applicable(self):
        clause = (
            "Either party may terminate this Agreement upon thirty days notice, and liability shall be limited to fees paid. "
            "A cure period of fifteen days applies before termination for breach."
        )
        result = assess_risk(clause, "Termination of agreement clause")

        score_reducing_signals = {
            signal["label"]: signal.get("impact", 0)
            for signal in result["positive_signals"]
        }

        self.assertEqual(score_reducing_signals.get("Liability cap present"), -1)
        self.assertEqual(score_reducing_signals.get("Cure period present"), -1)

    def test_permitted_disclosure_clause_does_not_double_count_one_sided_language(self):
        clause = (
            "A Receiving Party shall not be restricted from disclosing Confidential Information if required by law. "
            "The Receiving Party shall promptly notify the Disclosing Party where legally permitted."
        )
        result = assess_risk(clause, "Permitted disclosures and exceptions clause")

        one_sided_rules = [rule for rule in result["matched_rules"] if "One-sided" in rule["label"]]
        self.assertEqual(len(one_sided_rules), 0)

    def test_home_jurisdiction_is_configurable(self):
        clause = "This Agreement is governed by the laws of Delaware."

        india_result = assess_risk(clause, "Governing law and jurisdiction clause", home_jurisdiction="india")
        delaware_result = assess_risk(clause, "Governing law and jurisdiction clause", home_jurisdiction="delaware")

        self.assertEqual(india_result["level"], "MEDIUM")
        self.assertEqual(delaware_result["level"], "LOW")
        self.assertTrue(any(signal["label"] == "Home jurisdiction selected" for signal in delaware_result["positive_signals"]))

    def test_definition_clause_is_not_penalized_for_missing_duration(self):
        clause = "Confidential Information includes technical, financial, and commercial information."
        result = assess_risk(clause, "Definition of confidential information clause")

        self.assertEqual(result["category"], "confidentiality_definition")
        self.assertNotIn("No confidentiality duration", result["reason"])

    def test_five_year_confidentiality_term_is_medium_not_high(self):
        clause = "Each party shall keep Confidential Information confidential for five years."
        result = assess_risk(clause, "Obligations of confidentiality and non-disclosure clause")

        self.assertEqual(result["level"], "MEDIUM")
        self.assertEqual(result["score"], 2)
        self.assertIn("Long duration", result["reason"])

    def test_unlimited_liability_is_high(self):
        clause = "The Supplier's liability is unlimited and without any financial cap."
        result = assess_risk(clause, "Limitation of liability clause")

        self.assertEqual(result["level"], "HIGH")
        self.assertTrue(any(rule["rule_id"] == "liability_unlimited" for rule in result["matched_rules"]))

    def test_without_limitation_in_definition_is_not_liability_language(self):
        clause = "Confidential Information includes, without limitation, designs and specifications."
        result = assess_risk(clause, "Definition of confidential information clause")

        self.assertNotIn("Unlimited liability", result["reason"])

    def test_damage_exclusion_is_not_flagged_as_missing(self):
        clause = "Neither party shall be liable for indirect or consequential damages."
        result = assess_risk(clause, "Limitation of liability clause")

        self.assertEqual(result["level"], "LOW")
        self.assertTrue(any(signal["label"] == "Damages exclusion present" for signal in result["positive_signals"]))

    def test_force_majeure_missing_pandemic_is_not_automatically_risky(self):
        clause = "Neither party is liable for delay caused by events beyond its reasonable control."
        result = assess_risk(clause, "Force majeure clause")

        self.assertEqual(result["level"], "LOW")
        self.assertTrue(result["recommendations"])

    def test_trade_secret_survival_is_not_treated_as_unlimited_ordinary_confidentiality(self):
        clause = "Obligations for trade secrets survive termination for so long as they remain trade secrets."
        result = assess_risk(clause, "Obligations of confidentiality and non-disclosure clause")

        self.assertNotIn("Post-termination obligations have no stated limit", result["reason"])

    def test_risk_output_states_it_is_issue_spotting(self):
        result = assess_risk("Standard clause text.", "Unclassified clause")

        self.assertIn("Automated issue-spotting only", result["review_notice"])


if __name__ == "__main__":
    unittest.main()
