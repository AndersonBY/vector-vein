# @Author: Bi Ying
# @Date:   2023-04-13 15:45:13
"""Saved vector workflow nodes backed by managed knowledge bases."""
import time
from uuid import uuid4

from worker.tasks import task, timer
from utilities.workflow import Workflow
from utilities.text_processing import remove_markdown_image


PROCESSING_TIMEOUT = 300
PROCESSING_POLL_INTERVAL = 1


def knowledge_service():
    from knowledge_base import knowledge_service as get_service

    return get_service()


def _strings(value, field):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise ValueError(f"{field} must be a string or a list of strings")


def _item(service, kb_id, document_id):
    item = service.dispatch("get_item", {"kb_id": kb_id, "id": document_id})
    if item["kb_id"] != kb_id or item["id"] != document_id or item["kind"] != "file":
        raise ValueError("The document does not belong to the selected knowledge base")
    return item


def _wait_for_processing(service, kb_id, document_ids):
    deadline = time.monotonic() + PROCESSING_TIMEOUT
    pending = set(document_ids)
    while pending:
        for document_id in tuple(pending):
            item = _item(service, kb_id, document_id)
            status = item["status"]
            if status == "ready":
                pending.remove(document_id)
            elif status in ("failed", "unindexed"):
                raise RuntimeError(
                    f"Knowledge document {document_id} is {status}. "
                    "Check its indexing status in Knowledge bases and explicitly reindex it before retrying."
                )
            elif status not in ("queued", "indexing"):
                raise RuntimeError(f"Knowledge document {document_id} has an unsupported indexing status")
        if not pending:
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                "Knowledge base indexing timed out. Check document status in Knowledge bases; "
                "retry failed documents with Reindex before running dependent search nodes."
            )
        time.sleep(min(PROCESSING_POLL_INTERVAL, remaining))


@task
@timer
def add_data(workflow_data: dict, node_id: str):
    workflow = Workflow(workflow_data)
    raw_text = workflow.get_node_field_value(node_id, "text")
    raw_title = workflow.get_node_field_value(node_id, "content_title")
    raw_source = workflow.get_node_field_value(node_id, "source_url", "")
    values = [_strings(raw_text, "text"), _strings(raw_title, "content_title"),
              _strings(raw_source, "source_url")]
    length = max(map(len, values))
    texts, titles, sources = [value * length if len(value) == 1 else value for value in values]
    if not len(texts) == len(titles) == len(sources):
        raise ValueError(
            "Batch text, content_title, and source_url values must have equal lengths after single-value expansion"
        )
    kb_id = workflow.get_node_field_value(node_id, "database")
    service = knowledge_service()
    document_ids = []
    for text, title, source in zip(texts, titles, sources):
        payload = {
            "kb_id": kb_id, "name": title, "text": remove_markdown_image(text), "source_url": source,
        }
        try:
            item = service.dispatch("add_text", payload)
        except ValueError as exc:
            if getattr(exc, "code", None) != "name_conflict":
                raise
            # Saved workflows may reuse a title; KB sibling names must be unique.
            payload["name"] = f"{title[:205]} ({uuid4().hex})"
            item = service.dispatch("add_text", payload)
        document_ids.append(item["id"])
    if workflow.get_node_field_value(node_id, "wait_for_processing", False):
        _wait_for_processing(service, kb_id, document_ids)
    scalar = all(isinstance(value, str) for value in (raw_text, raw_title, raw_source))
    workflow.update_node_field_value(node_id, "object_id", document_ids[0] if scalar else document_ids)
    return workflow.data


@task
@timer
def delete_data(workflow_data: dict, node_id: str):
    workflow = Workflow(workflow_data)
    document_ids = _strings(workflow.get_node_field_value(node_id, "object_id"), "object_id")
    kb_id = workflow.get_node_field_value(node_id, "database")
    service = knowledge_service()
    # Validate the whole batch before deleting any document.
    items = [_item(service, kb_id, document_id) for document_id in dict.fromkeys(document_ids)]
    for item in items:
        service.dispatch("delete_item", {
            "kb_id": kb_id, "id": item["id"], "expected_updated_at": item["updated_at"],
        })
    workflow.update_node_field_value(node_id, "delete_success", True)
    return workflow.data


@task
@timer
def search_data(workflow_data: dict, node_id: str):
    workflow = Workflow(workflow_data)
    raw_query = workflow.get_node_field_value(node_id, "search_text")
    queries = _strings(raw_query, "search_text")
    output_type = workflow.get_node_field_value(node_id, "output_type")
    if output_type not in ("text", "list"):
        raise ValueError("output_type must be text or list")
    kb_id = workflow.get_node_field_value(node_id, "database")
    count = workflow.get_node_field_value(node_id, "count")
    service = knowledge_service()
    outputs = []
    for query in queries:
        response = service.dispatch("search", {
            "kb_ids": [kb_id], "query": query, "mode": "hybrid", "limit": count,
        })
        if any(result["kb_id"] != kb_id for result in response["results"]):
            raise RuntimeError("Knowledge search returned a document outside the selected knowledge base")
        if not response["results"] and any(
            warning.get("error_code") in ("semantic_unavailable", "index_incomplete", "unindexed")
            for warning in response.get("warnings", [])
        ):
            raise RuntimeError(
                "Knowledge search is unavailable or document indexing is incomplete. "
                "Check the embedding model settings and document status in Knowledge bases; "
                "wait for processing or use Reindex, then retry."
            )
        texts = [result["text"] for result in response["results"]]
        outputs.append("\n".join(texts) if output_type == "text" else texts)
    workflow.update_node_field_value(node_id, "output", outputs if isinstance(raw_query, list) else outputs[0])
    return workflow.data
