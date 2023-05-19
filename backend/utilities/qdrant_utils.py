# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-16 17:44:39
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-17 11:51:35
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import (
    Filter,
    Distance,
    MatchValue,
    PointStruct,
    VectorParams,
    FilterSelector,
    FieldCondition,
)

from utilities.print_utils import mprint_error


qdrant_client = QdrantClient(path="./data/qdrant_db")


def create_collection(vid: str, size: int = 768):
    try:
        qdrant_client.recreate_collection(
            collection_name=f"{vid}_text_collection",
            vectors_config=VectorParams(size=size, distance=Distance.COSINE),
            on_disk_payload=True,
        )
        return True
    except UnexpectedResponse as e:
        mprint_error(e)
        return False


def delete_collection(vid: str):
    try:
        qdrant_client.delete_collection(f"{vid}_text_collection")
        return True
    except UnexpectedResponse as e:
        mprint_error(e)
        return False


def add_point(vid: str, point: dict):
    try:
        qdrant_client.upsert(
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
                    vector=point.get("embedding"),
                ),
            ],
        )
        return True
    except UnexpectedResponse as e:
        mprint_error(e)
        return False


def delete_point(vid: str, object_id: str):
    try:
        qdrant_client.delete(
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
        return True
    except UnexpectedResponse as e:
        mprint_error(e)
        return False


def search_point(
    vid: str,
    text_embedding: list,
    limit: int = 5,
):
    text_hits = qdrant_client.search(
        collection_name=f"{vid}_text_collection",
        query_vector=text_embedding,
        limit=limit,
    )
    return [hit.payload for hit in text_hits]
