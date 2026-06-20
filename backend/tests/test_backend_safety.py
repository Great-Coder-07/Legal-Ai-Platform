import io
import os
import unittest
from unittest.mock import Mock, patch

from fastapi import BackgroundTasks, HTTPException, UploadFile

from backend.pipelines import research_agent
from backend.routers.upload import upload_document


class _FakeEmbedder:
    def encode(self, _query, **_kwargs):
        return Mock(tolist=lambda: [[0.1, 0.2]])


class BackendSafetyTests(unittest.TestCase):
    def test_precedent_lookup_never_returns_invented_cases_on_database_error(self):
        collection = Mock()
        collection.count.return_value = 4
        collection.query.side_effect = RuntimeError("database unavailable")
        with (
            patch.object(research_agent, "get_embedder", return_value=_FakeEmbedder()),
            patch.object(research_agent, "get_vector_collection", return_value=collection),
        ):
            results = research_agent.search_precedents("sample clause")

        self.assertEqual(results, [])


class UploadSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_rejects_unsupported_task(self):
        upload = UploadFile(filename="sample.txt", file=io.BytesIO(b"contract text"))

        with self.assertRaises(HTTPException) as context:
            await upload_document(BackgroundTasks(), upload, "unknown_task")

        self.assertEqual(context.exception.status_code, 400)

    async def test_upload_limit_is_enforced(self):
        upload = UploadFile(filename="sample.txt", file=io.BytesIO(b"x" * 1025))

        with (
            patch.dict(os.environ, {"MAX_UPLOAD_MB": "0"}, clear=False),
            self.assertRaises(HTTPException) as context,
        ):
            await upload_document(BackgroundTasks(), upload, "analyze_contract")

        self.assertEqual(context.exception.status_code, 413)

    async def test_document_ingestion_requires_explicit_consent(self):
        upload = UploadFile(filename="sample.txt", file=io.BytesIO(b"A valid contract clause with enough text."))

        with (
            patch("backend.routers.upload.route_document", return_value={"contract_analysis": {}}),
            patch("backend.routers.upload.ingest_document") as ingest,
        ):
            response = await upload_document(BackgroundTasks(), upload, "analyze_contract")

        self.assertEqual(response["status"], "success")
        ingest.assert_not_called()
        self.assertEqual(response["library_indexing"], "not_requested")

    async def test_document_ingestion_can_be_requested_explicitly(self):
        upload = UploadFile(filename="sample.txt", file=io.BytesIO(b"A valid contract clause with enough text."))
        tasks = BackgroundTasks()

        with (
            patch.dict(os.environ, {"CLAUSE_LIBRARY_ENABLED": "true"}, clear=False),
            patch("backend.routers.upload.route_document", return_value={"contract_analysis": {}}),
        ):
            response = await upload_document(
                tasks,
                upload,
                "analyze_contract",
                True,
                "India",
            )

        self.assertEqual(response["library_indexing"], "scheduled")
        self.assertEqual(len(tasks.tasks), 1)

    async def test_pipeline_failure_is_returned_as_server_error(self):
        upload = UploadFile(filename="sample.txt", file=io.BytesIO(b"A valid contract clause with enough text."))

        with patch("backend.routers.upload.route_document", side_effect=RuntimeError("pipeline failed")):
            with self.assertRaises(HTTPException) as context:
                await upload_document(BackgroundTasks(), upload, "analyze_contract")

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(context.exception.detail, "Document processing failed.")


if __name__ == "__main__":
    unittest.main()
