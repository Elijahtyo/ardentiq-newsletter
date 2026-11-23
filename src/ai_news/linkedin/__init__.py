"""LinkedIn drafting branch.

The news pipeline feeds two separate consumers:

* senior-staff digests, written to Databricks;
* LinkedIn drafts, written to files under ``linkedin/`` and never to Databricks.

Drafts read the digest produced by the same workflow run, so this package has no
dependency on the Databricks storage layer in either direction.
"""

from ai_news.linkedin.models import Draft, DraftRecord, DraftStatus
from ai_news.linkedin.store import DraftStore

__all__ = ["Draft", "DraftRecord", "DraftStatus", "DraftStore"]
