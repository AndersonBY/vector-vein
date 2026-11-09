"""Single-owner embedded Qdrant adapter, separate from legacy workflow indexes."""
from __future__ import annotations

import math
import os
from pathlib import Path

from .storage import KnowledgeError, safe_path


def checked_vectors(values, count: int, dimension: int | None = None) -> list[list[float]]:
    try:
        vectors = [[float(value) for value in vector] for vector in values]
        lengths = {len(vector) for vector in vectors}
        if (len(vectors) != count or not vectors or len(lengths) != 1 or 0 in lengths
                or any(not math.isfinite(value) or abs(value) > 3.402823466e38 for vector in vectors for value in vector)
                or (dimension is not None and lengths != {dimension})):
            raise ValueError
        return vectors
    except (ValueError, TypeError, OverflowError):
        raise KnowledgeError("invalid_embedding", "The embedding model returned invalid or inconsistent vectors.") from None


class EmbeddedVectors:
    def __init__(self, path: Path):
        self.path, self.pid, self.client = path, os.getpid(), None

    def _client(self):
        if os.getpid() != self.pid:
            raise KnowledgeError("wrong_process", "Knowledge indexes are owned by the desktop process.", 503)
        if self.client is None:
            from qdrant_client import QdrantClient

            safe_path(self.path, exists=False)
            self.path.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(self.path), force_disable_check_same_thread=True)
        return self.client

    @staticmethod
    def collection(kb_id: str) -> str:
        return "kb_" + kb_id

    def write(self, kb_id, dimension, chunks, vectors, token):
        from qdrant_client.models import Distance, PointStruct, VectorParams

        client = self._client()
        collection = self.collection(kb_id)
        if not client.collection_exists(collection):
            client.create_collection(collection, vectors_config=VectorParams(size=dimension, distance=Distance.COSINE))
        client.upsert(collection, points=[
            PointStruct(id=chunk["id"], vector=vector, payload={
                "document_id": chunk["document_id"], "token": token, "kb_id": kb_id,
            }) for chunk, vector in zip(chunks, vectors, strict=True)
        ], wait=True)

    def search(self, kb_id, vector, tokens, limit):
        from qdrant_client.models import FieldCondition, Filter, MatchAny

        if not tokens:
            return []
        client = self._client()
        if not client.collection_exists(self.collection(kb_id)):
            return []
        result = client.query_points(
            self.collection(kb_id), query=vector,
            query_filter=Filter(must=[FieldCondition(key="token", match=MatchAny(any=tokens))]),
            limit=limit, with_payload=False, with_vectors=False,
        )
        return [str(point.id).replace("-", "") for point in result.points]

    def delete_document(self, kb_id, document_id):
        from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue

        client = self._client()
        if not client.collection_exists(self.collection(kb_id)):
            return
        condition = Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))])
        client.delete(self.collection(kb_id), points_selector=FilterSelector(filter=condition), wait=True)

    def delete_base(self, kb_id):
        client = self._client()
        if client.collection_exists(self.collection(kb_id)):
            client.delete_collection(self.collection(kb_id))

    def close(self):
        if self.client is not None:
            self.client.close()
            self.client = None
