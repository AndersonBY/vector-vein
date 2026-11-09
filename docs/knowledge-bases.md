# Knowledge bases

The Data page exposes **Knowledge bases** and **Relational databases** as peers. The former standalone vector-database screens and CRUD endpoints are retired. Relational database tables and SQL workflow nodes retain their existing behavior.

## Document management

A knowledge base owns an embedding provider/model, dimension setting, chunk size and overlap. The desktop create form defaults to 1,000 characters with 150 characters of overlap. Embedding models come from Settings → Embedding models. Renaming a knowledge base does not change its embedding configuration.

The browser provides a folder tree, breadcrumbs, name search, pagination, native file/directory import, folder creation, rename, move, recursive deletion, extracted-text preview and source opening. Directory import preserves hierarchy. IDs remain stable across moves and renames. Mutations require the observed update timestamp; conflicts refresh metadata before another confirmation.

Supported document extensions are TXT, Markdown, HTML/HTM, JSON, CSV/TSV, SRT, PDF, DOCX, PPTX and XLSX. Imported sources are copied into managed storage; editing or deleting knowledge entries never changes the original selected files. Each file is limited to 50 MiB; extracted text is limited to four million characters. Directory traversal is bounded to 2,000 entries and 20 levels. Links and Windows reparse/junction paths are rejected. Office archive expansion is bounded before parsing. Image-only documents require a separate text/OCR preparation step.

## Storage and indexing

`config.data_path/knowledge-base/` contains:

- `metadata.sqlite3`: knowledge bases, hierarchy, extracted text, chunks, FTS5, durable jobs and legacy-import receipts.
- `originals/`: managed copies named by generated IDs, independent of the displayed folder paths.
- `vectors/`: derived Qdrant collections, one collection per knowledge base.
- `.owner.lock`: a lifetime exclusive writer lock, acquired before recovery or migration.

SQLite is authoritative. The desktop owns the index writer; metadata-only readers do not acquire the vector store. A second writer cannot reset another process's running jobs. Qdrant remains in embedded local mode, with explicit cosine distance, bounded embedding batches and dimension/finite-value validation. Arbitrary index-open failures never trigger collection deletion or recreation.

New imports are queued automatically. Jobs progress through extraction, embedding and publication. Each attempt is bound to a document generation; deleting or reindexing a document invalidates older work. Extracted chunks are independently published to lexical retrieval before embedding. An embedding failure leaves usable text and keyword evidence, records a safe error code and permits explicit retry. Partial vectors never qualify as a complete semantic index. Restarted jobs rebuild their interrupted document and reclaim partial derived points.

The UI polls indexing state and exposes retry/rebuild actions. Rebuilding can invoke the configured embedding provider again. Closing to the system tray keeps indexing and Agent scheduling running; exiting stops the desktop and pending work resumes on the next start.

## Retrieval and Agent mounts

Search supports keyword, semantic and hybrid modes. SQLite FTS5 trigram retrieval supports Chinese text; short terms use a scoped substring query. Hybrid retrieval combines ranked lexical/vector candidates using reciprocal rank fusion. KB and optional folder scope are applied before candidate selection. Only candidate text is loaded, and current document generations/scope are checked again after embedding calls. Warnings about unavailable or incomplete indexes are aggregated per KB; incomplete retrieval is not presented as an unqualified empty result.

Agent profiles store `knowledge_base_ids`, with at most 20 distinct knowledge bases. Task creation freezes validated `{kb_id,name}` descriptors in `config_snapshot.knowledge_bases`. Later profile changes do not silently widen an existing task. Mounts are configured on the Agent configuration page; task details link to their knowledge bases.

Mounted Agents receive readonly `knowledge_list`, `knowledge_search` and `knowledge_read` tools. Configured child Agents inherit the same bound tools. No mounts means no knowledge tools. Results include document/chunk IDs, logical paths and excerpts. The model is instructed to cite sources and treat retrieved documents as data rather than instructions.

`knowledge_list` browses one level of mounted directories and files without invoking embedding or reranking. An initial call with no arguments lists the roots of all mounted bases; `folder_id` comes from a folder's `items.id`, and file IDs can be passed to `knowledge_read`. Its base summaries distinguish total documents, keyword-readable documents, semantic-ready documents and indexing states. `offset`/`limit` and `next_offset` provide stable pages of at most 50 entries; `truncated` reports the 10,000-offset cap. Listing never returns physical source paths or document bodies.

Search requires meaningful letters or numbers. A wildcard-only or punctuation-only query (such as `*`) returns `invalid_query` before any provider call, with guidance to browse instead. Empty results from a valid search mean no matching excerpts, not an absent mount or an empty base. The private bridge preserves only fixed allowlisted error messages; arbitrary provider exceptions remain redacted.

The App Server process never opens Qdrant storage. It calls an authenticated numeric-loopback bridge owned by the desktop. The bridge checks its runtime credential, saved task identity, frozen mounts and requested subset on every call. Credentials are inherited privately at process launch and removed from the child's environment before tool execution; they never enter snapshots, tool schemas, model arguments or results. Browser-origin requests and non-loopback requests are rejected. Specific LAN API binds receive an additional loopback listener so this private path remains local.

## Read-only virtual workspace

Mounted sources are exposed under `.knowledge/<mount-alias>/<logical-document-path>` through the ordinary `find_files`, `read_file`, `search_files` and `file_info` tools. Aliases derive from the task's frozen mount names; duplicate/sanitized-name collisions receive stable ID suffixes. Nothing is copied into the task or Project directory. Unmounted tasks keep their existing local file-tool behavior.

`find_files` at the workspace root advertises `.knowledge/` separately without changing local pagination. Use `path=".knowledge/"` explicitly to enumerate or search mounted text. Ordinary workspace-root searches remain local. Knowledge filename patterns, literal/regex matching, case handling, content/count/file-list output, context and multiline matching are bounded; incomplete scans and clipped snippets are reported. PDF and Office filenames retain their original extensions, while reads/searches use their extracted UTF-8 text. File information reports the extracted text byte size.

The owner bridge validates saved task identity and frozen mounts for every virtual operation. Path traversal never falls back to the physical filesystem. Version-bound paged reads reject sources changed during a read or after a continuation cursor was issued. `write_file` and `edit_file` always reject virtual targets, including under full-access permission mode. Bash has no materialized `.knowledge` directory to access. Child Agents inherit the same task-bound routing and permissions.

The task workspace panel lists mounted documents alongside local files and previews their extracted text. Virtual files show a read-only label and have no native open/reveal action. Semantic results retain their logical `path` and additionally expose `knowledge_path`, which can be passed directly to `read_file` or used as a preview link. The existing ID-based knowledge tools remain available.

## Reranking and Vekai

Settings → Reranking models configures vv-llm `llm_settings.rerank_backends` independently of embedding models. Select a provider and configured model key under the knowledge retrieval default to enable reranking; clearing the selection disables it. The business setting is `knowledge_retrieval.rerank = {provider, model}`, disabled by default. The saved selection applies to subsequent desktop, Agent and workflow KB searches without reindexing documents.

Reranking runs after lexical/vector candidate fusion, on at most `min(limit * 4, 200)` scoped excerpts. Returned indexes select the original candidate text; provider-supplied document content is ignored. Invalid indexes, duplicate indexes, non-finite scores and service failures retain the original retrieval order and produce `rerank_unavailable`. Provider calls do not hold the metadata lock. Scope, document generations, names and paths are revalidated before results are returned.

The **Connect Vekai** action in each embedding/reranking settings card header adds that service to the settings draft:

- Embedding: `http://127.0.0.1:8013`, OpenAI embeddings protocol, default model alias `local-embedding`. Vector dimensions are inferred from actual responses.
- Reranking: `http://127.0.0.1:8012`, custom HTTP mapping to `/v1/rerank`, default model alias `local-reranker`. Response indexes and scores come from `results[*].index` and `results[*].relevance_score`.

Addresses and model IDs are editable. Existing model configurations and endpoint credentials are preserved; conflicting endpoint addresses are rejected. Adding the preset does not activate reranking: choose its model and save settings explicitly. Vekai must already be running with the chosen models; VectorVein connects to its HTTP services and does not download models or start Vekai. Configure any required credentials in the shared endpoint editor.

Both retrieval model lists and their edit dialogs provide **Test connection**. The test uses the current model draft, a selected endpoint binding and any saved credential reference without saving settings. Embedding probes send two short sample strings and verify vector count, finite values and dimensions; reranking probes validate document indexes and scores. Results show elapsed time and dimensions or relevance scores. Tests use a single request with a 20-second timeout, and distinguish invalid configuration, authentication, missing endpoints/models, connection failures, timeout and invalid responses. Changing the draft or closing the test dialog discards stale responses.

## Native API

The pywebview namespace is `knowledge_base__{action}` through `KnowledgeBaseAPI`. Responses use the existing `status/data/msg` envelope; failures expose a bounded `data.error_code` and safe message. There is no public generic HTTP knowledge-management endpoint.

| Action | Main input | Result |
| --- | --- | --- |
| `list`, `get` | Optional `id` for get | `{bases}` or a KB record |
| `create` | Name, embedding provider/model, optional dimensions/chunk settings | KB record |
| `update`, `delete` | `id`, `expected_updated_at`; update name/description | Record or success |
| `tree`, `items` | `kb_id`; optional parent/search/offset/limit | Folder tree or `{items,total,breadcrumbs}` |
| `create_folder` | `kb_id`, `parent_id`, `name` | Item |
| `import_files`, `import_directory` | `kb_id`, destination parent, selected absolute paths | `{items,skipped}` |
| `add_text` | `kb_id`, name/text, optional parent/source URL | Queued file item |
| `get_item`, `preview`, `open_file` | `kb_id`, item `id` | Metadata, bounded text or native opening |
| `rename`, `move`, `delete_item` | `kb_id`, item `id`, revision and target name/parent | Item or success |
| `reindex` | `kb_id`, optional file/folder `id` | `{queued_count}` |
| `search` | `kb_ids`, query, mode, optional folder/limit | `{results,warnings}` |
| `browse` | `kb_ids`, optional folder/offset/limit | Scoped base summaries, one-level items and pagination |

Normal file listing is parent-scoped; name search includes that parent's descendants. Root `parent_id` is null. IDs are UUID hex strings; timestamps are ISO strings. Agent reads are limited to 12,000 characters per call and Agent searches to 20 hits. The desktop search API allows up to 50 hits.

## Existing data and workflows

Legacy vector datasets and document IDs are imported idempotently from the old business database. Safe original files are copied when available; otherwise recovered text becomes a managed TXT source. Recovered chunks are available to keyword retrieval. Migrated documents remain `unindexed` for semantic retrieval until an explicit rebuild, so migration does not automatically make paid embedding calls. Legacy SQL rows and old index directories are preserved; deleting a migrated KB/item does not resurrect it on another startup.

Saved workflow identifiers `vector_db.add_data`, `vector_db.delete_data` and `vector_db.search_data` remain valid, but their implementations and selectors now operate on knowledge bases. Batch/scalar output shapes and source URLs are retained. Processing waits are bounded. An empty search caused by an unavailable/incomplete index raises an actionable workflow error instead of claiming no matches. Old `/api/database/*` HTTP routes return 410 with desktop KB guidance.

## Engine decision

This implementation keeps the already-used Qdrant local engine as an internal KB index. zvec 0.8.0 has native Windows/Python 3.12 support and was import-checked in VeraQ's environment. Its writable collections also require a single process owner. A replacement would require explicit metric/scope checks, migration and frozen-package validation; hierarchical storage and reliable ingestion do not require that replacement. No comparative performance benchmark or packaged zvec validation was performed. Metadata, originals and chunks remain independent of the derived vector index.

## Verification

- `test_knowledge_rerank.py` and `test_rerank_settings.py`: reranking protocols, persisted configuration, safe fallback and scope/generation races.
- `frontend/tests/rerankSettings.test.js`: Vekai presets, endpoint conflicts, model-key selection and translated settings.
- `test_knowledge_base.py`: real Qdrant, hierarchy/imports, Chinese/scoped retrieval, failed embeddings, generation races, crash recovery, migration and writer ownership.
- `test_task_agent_knowledge.py`: mount validation, private transport, forged scopes, source errors and real App Server/child delegation through a deterministic local model endpoint and real KB index.
- `test_knowledge_workflow.py` and `test_vector_db_batch_lengths.py`: saved workflow compatibility and bounded failure handling.
- `frontend/tests/knowledgeBase.test.js`: navigation, native-picker cancellation/deduplication, previews, conflicts and safe errors.
- `backend/tests/knowledge_base_browser_fixture.py`: isolated real-service backend for headless UI validation; synthetic fixtures and deterministic embeddings only.
