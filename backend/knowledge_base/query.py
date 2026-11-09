"""Shared retrieval query validation; importing this module opens no application data."""
from .storage import KnowledgeError


INVALID_QUERY_MESSAGE = (
    "Search requires meaningful words/question; use knowledge_list to browse mounted contents. "
    "Wildcards are not supported."
)


def validate_query(query) -> str:
    if not isinstance(query, str) or not 1 <= len(query) <= 4000 or not any(char.isalnum() for char in query):
        raise KnowledgeError("invalid_query", INVALID_QUERY_MESSAGE)
    return query.strip()
