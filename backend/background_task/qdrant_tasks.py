# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2025-08-04
# Qdrant-specific Celery tasks

import uuid
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Filter,
    Distance,
    MatchValue,
    PointStruct,
    VectorParams,
    FilterSelector,
    FieldCondition,
)

from celery_worker import app, timer
from models import UserObject
from utilities.general import mprint_with_name
from utilities.config import config, cache
from utilities.ai_utils import EmbeddingClient

mprint = mprint_with_name(name="Qdrant Tasks")


def get_qdrant_client():
    """Get QdrantClient instance"""
    qdrant_path = Path(config.data_path) / "qdrant_db"
    return QdrantClient(path=qdrant_path.absolute().as_posix())


@app.task(bind=True)
@timer
def q_create_collection(self, vid: str, size: int = 768):
    """Create Qdrant collection"""
    try:
        client = get_qdrant_client()
        client.recreate_collection(
            collection_name=f"{vid}_text_collection",
            vectors_config=VectorParams(size=size, distance=Distance.COSINE),
            on_disk_payload=True,
        )

        mprint(f"Created Qdrant collection: {vid}_text_collection")
        return True
    except Exception as e:
        mprint.error(f"Failed to create collection {vid}: {e}")
        self.retry(countdown=60, max_retries=3)
        return False


@app.task(bind=True)
@timer
def q_delete_collection(self, vid: str):
    """Delete Qdrant collection"""
    try:
        client = get_qdrant_client()
        client.delete_collection(f"{vid}_text_collection")

        mprint(f"Deleted Qdrant collection: {vid}_text_collection")
        return True
    except Exception as e:
        mprint.error(f"Failed to delete collection {vid}: {e}")
        self.retry(countdown=60, max_retries=3)
        return False


@app.task(bind=True)
@timer
def q_add_point(self, vid: str, point: dict):
    """Add point to Qdrant collection"""
    try:
        client = get_qdrant_client()
        client.upsert(
            collection_name=f"{vid}_text_collection",
            points=[
                PointStruct(
                    id=uuid.uuid4().hex,
                    payload={
                        "object_id": point.get("object_id"),
                        "text": point.get("text"),
                        "embedding_type": point.get("embedding_type"),
                        "extra_data": point.get("extra_data"),
                    },
                    vector=point.get("embedding") or [],
                ),
            ],
        )

        chunk_count = point.get("chunk_count") or 0
        if point.get("chunk_index") == chunk_count - 1:
            user_object: UserObject = UserObject.get(UserObject.oid == point.get("object_id"))
            user_object.status = "VA"
            user_object.save()

        cache.set(
            f"qdrant-point-progress:{vid}:{point.get('object_id')}",
            {"chunk_index": point.get("chunk_index"), "chunk_count": chunk_count},
            expire=60 * 60,
        )

        mprint(f"Added point to collection {vid} for object {point.get('object_id')}")
        return True
    except Exception as e:
        mprint.error(f"Failed to add point to collection {vid}: {e}")
        self.retry(countdown=60, max_retries=3)
        return False


@app.task(bind=True)
@timer
def embedding_and_upload(
    self,
    vid: str,
    object_id: str,
    input: str | list,
    embedding_provider: str,
    embedding_model: str,
    embedding_type: str,
    embedding_dimensions: int | None = None,
    extra_data: dict | None = None,
):
    """Generate embeddings and upload to Qdrant"""
    try:
        input = input if isinstance(input, list) else [input]
        if extra_data is None:
            extra_data = {}

        embedding_client = EmbeddingClient(provider=embedding_provider, model_id=embedding_model, dimensions=embedding_dimensions)

        for index, text in enumerate(input):
            embedding = embedding_client.get(text)
            q_add_point.delay(
                vid=vid,
                point={
                    "object_id": object_id,
                    "text": text,
                    "embedding": embedding,
                    "embedding_type": embedding_type,
                    "extra_data": extra_data,
                    "chunk_index": index,
                    "chunk_count": len(input),
                },
            )

        mprint(f"Queued embedding tasks for object {object_id} in collection {vid}")
        return True
    except Exception as e:
        mprint.error(f"Failed to process embeddings for object {object_id}: {e}")
        self.retry(countdown=60, max_retries=3)
        return False


@app.task(bind=True)
@timer
def q_delete_point(self, vid: str, object_id: str):
    """Delete point from Qdrant collection"""
    try:
        client = get_qdrant_client()
        client.delete(
            collection_name=f"{vid}_text_collection",
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="object_id",
                            match=MatchValue(value=object_id),
                        ),
                    ],
                )
            ),
        )

        mprint(f"Deleted point from collection {vid} for object {object_id}")
        return True
    except Exception as e:
        mprint.error(f"Failed to delete point from collection {vid}: {e}")
        self.retry(countdown=60, max_retries=3)
        return False


@app.task(bind=True)
@timer
def q_search_point(
    self,
    vid: str,
    text_embedding: list,
    limit: int = 5,
):
    """Search points in Qdrant collection"""
    try:
        client = get_qdrant_client()
        text_hits = client.search(
            collection_name=f"{vid}_text_collection",
            query_vector=text_embedding,
            limit=limit,
        )

        results = [hit.payload for hit in text_hits]
        mprint(f"Searched collection {vid}, found {len(results)} results")
        return results
    except Exception as e:
        mprint.error(f"Failed to search collection {vid}: {e}")
        self.retry(countdown=60, max_retries=3)
        return []
