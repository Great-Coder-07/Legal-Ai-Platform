"""Rebuild the v2 clause library from the legacy ChromaDB collection."""

import json

from backend.pipelines.research_agent import migrate_legacy_collection


if __name__ == "__main__":
    print(json.dumps(migrate_legacy_collection(), indent=2))
