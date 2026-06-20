import unittest
from unittest.mock import Mock, patch

from backend.pipelines import research_agent


class _Encoded:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values


class _FakeEmbedder:
    def encode(self, texts, **_kwargs):
        return _Encoded([[0.1, 0.2, 0.3] for _ in texts])


class ClauseLibraryTests(unittest.TestCase):
    def test_clause_records_are_deterministic_and_clause_sized(self):
        text = (
            "1. Confidentiality\nThe Receiving Party shall keep information confidential for two years.\n\n"
            "2. Governing Law\nThis Agreement is governed by the laws of India."
        )

        first_hash, first = research_agent.build_clause_records("contract.txt", text, "India")
        second_hash, second = research_agent.build_clause_records("renamed.txt", text, "India")

        self.assertEqual(first_hash, second_hash)
        self.assertEqual([item["id"] for item in first], [item["id"] for item in second])
        self.assertGreaterEqual(len(first), 1)
        self.assertTrue(all(item["metadata"]["schema_version"] == 2 for item in first))
        self.assertTrue(all(item["metadata"]["clause_type"] for item in first))

    def test_page_metadata_is_preserved(self):
        text = "Confidentiality obligations apply.\n\nGoverning law is India."
        pages = [
            "The Receiving Party shall keep Confidential Information secret for two years.",
            "This Agreement is governed by the laws of India and courts at Delhi have jurisdiction.",
        ]

        _document_hash, records = research_agent.build_clause_records(
            "contract.pdf",
            text,
            "India",
            pages,
        )

        self.assertEqual({item["metadata"]["page_number"] for item in records}, {1, 2})

    def test_ingestion_uses_upsert_to_avoid_duplicates(self):
        collection = Mock()
        text = "The Receiving Party shall keep Confidential Information confidential for two years."

        with (
            patch.object(research_agent, "get_embedder", return_value=_FakeEmbedder()),
            patch.object(research_agent, "get_vector_collection", return_value=collection),
        ):
            first = research_agent.ingest_document("contract.txt", text)
            second = research_agent.ingest_document("contract.txt", text)

        self.assertEqual(first["document_hash"], second["document_hash"])
        self.assertEqual(collection.upsert.call_count, 2)
        first_ids = collection.upsert.call_args_list[0].kwargs["ids"]
        second_ids = collection.upsert.call_args_list[1].kwargs["ids"]
        self.assertEqual(first_ids, second_ids)

    def test_search_filters_low_similarity_and_excludes_current_document(self):
        collection = Mock()
        collection.count.return_value = 4
        collection.query.return_value = {
            "ids": [["current", "good", "weak", "duplicate"]],
            "documents": [[
                "Current clause",
                "A similar termination clause",
                "A weakly related payment clause",
                "Another clause from the same source",
            ]],
            "metadatas": [[
                {"document_hash": "current-hash", "source": "current.pdf", "clause_hash": "a", "clause_type": "Termination clause"},
                {"document_hash": "other-hash", "source": "other.pdf", "clause_hash": "b", "clause_type": "Termination clause"},
                {"document_hash": "weak-hash", "source": "weak.pdf", "clause_hash": "c", "clause_type": "Payment clause"},
                {"document_hash": "other-hash", "source": "other.pdf", "clause_hash": "d", "clause_type": "Termination clause"},
            ]],
            "distances": [[0.02, 0.12, 0.75, 0.14]],
        }

        with (
            patch.object(research_agent, "get_embedder", return_value=_FakeEmbedder()),
            patch.object(research_agent, "get_vector_collection", return_value=collection),
        ):
            result = research_agent.search_similar_clauses(
                "Termination text",
                clause_type="Termination clause",
                exclude_document_hash="current-hash",
                min_similarity=0.45,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(result["matches"][0]["id"], "good")
        self.assertEqual(result["matches"][0]["similarity_percent"], 88)

    def test_search_returns_at_most_one_match_per_document(self):
        collection = Mock()
        collection.count.return_value = 3
        collection.query.return_value = {
            "ids": [["one-a", "one-b", "two-a"]],
            "documents": [["Clause A", "Clause B", "Clause C"]],
            "metadatas": [[
                {"document_hash": "one", "source": "one.pdf", "clause_hash": "a", "clause_type": "Type"},
                {"document_hash": "one", "source": "one.pdf", "clause_hash": "b", "clause_type": "Type"},
                {"document_hash": "two", "source": "two.pdf", "clause_hash": "c", "clause_type": "Type"},
            ]],
            "distances": [[0.05, 0.06, 0.08]],
        }

        with (
            patch.object(research_agent, "get_embedder", return_value=_FakeEmbedder()),
            patch.object(research_agent, "get_vector_collection", return_value=collection),
        ):
            result = research_agent.search_similar_clauses("query", top_k=3, min_similarity=0)

        self.assertEqual(len(result["matches"]), 2)
        self.assertEqual(
            {item["metadata"]["document_hash"] for item in result["matches"]},
            {"one", "two"},
        )

    def test_empty_library_has_clear_status(self):
        collection = Mock()
        collection.count.return_value = 0

        with (
            patch.object(research_agent, "get_embedder", return_value=_FakeEmbedder()),
            patch.object(research_agent, "get_vector_collection", return_value=collection),
        ):
            result = research_agent.search_similar_clauses("query")

        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["matches"], [])


if __name__ == "__main__":
    unittest.main()
