# Reliable data workflows

Available in VectorVein 0.4.16. Existing node types are extended; no external workflow service is required.

## File input

File Loader reads all XLSX worksheets by default. Text output separates worksheets with their names. Choose **Structured JSON** to retain the absolute source path, sheet name, ordered columns, and one-based source row numbers. Worksheet names can be supplied as a list through a connection, or one name per line in the editor. An empty selection means all sheets; unknown or duplicate names fail the node.

Example:

```json
{
  "source": "input.xlsx",
  "sheets": [{
    "name": "Daily",
    "columns": ["Date", "Count"],
    "rows": [{"row_number": 2, "values": ["2025-05-10", 0]}]
  }]
}
```

Numbers, booleans, zero and null remain distinct. Dates and times become ISO strings. Formulas are read as formula strings, not evaluated. Other file types return source and content in structured mode. Text cleanup is applied only to text output; structured evidence remains unchanged.

## LLM validation and reuse

All base LLM nodes accept:

| Field | Default | Behavior |
|---|---|---|
| output_schema | empty | JSON Schema object or JSON text. Enables local validation. |
| max_repairs | 1 | Maximum additional schema repair calls; allowed range 0–2. |
| cache_results | false | Reuse successful outputs for up to 30 days. |
| cache_version | empty | User-controlled revision to invalidate cached results. |
| run_stats | output | Item count, cache hits, failure indexes and uncached token usage. |

Schemas are validated before requests. Draft selection follows the schema declaration, formats are checked, local references work, and remote references never fetch network resources. Output must be JSON without Markdown fences or non-finite numbers. Schema validation and function-calling mode must use separate nodes.

A schema adds the required format to the prompt. Invalid responses receive at most the configured number of repair requests. Exhausted repairs, empty responses and transport errors fail the batch and stop downstream execution. A valid JSON object alone does not establish factual accuracy; factual checks belong in downstream code.

The optional local cache stores only successful outputs, keyed by the prompt, system prompt, schema, model/provider and endpoint configuration, sampling/tool settings and cache revision. Cache hits are revalidated and add zero tokens to the new run. Successful items in a partially failed batch can be reused when the workflow is rerun. Changing a prompt, schema or configuration invalidates the relevant entry. The key payload is not stored or logged; only its digest is persisted alongside the result.

Increment cache_version when changing a deployed model's weights without changing its endpoint/model identity. Include source content in model inputs: a path string alone cannot detect changes to the file behind it. This is LLM result reuse, not a guarantee of deterministic fresh model generations or durable recovery of arbitrary side effects.

## Python execution and failures

Python nodes fail on exceptions by default. Enable **Continue on Python errors** only when a downstream branch explicitly handles error_msg. List inputs must have identical lengths. Top-level code executes once; if main is defined, it is then called with the declared parameters. Direct print calls are captured per node without replacing global stdout; output from imported libraries is not intercepted.

Legacy collection of newly created working-directory files is serialized between Python nodes. Existing destination files are preserved under unique names. New directories and symlinks are not moved. For reports, prefer returning structured data to Document nodes.

Task failures mark the run FAILED. Parallel branches are drained before the batch reports failure. Subworkflow polling retries use Celery's task retry mechanism and its configured limit.

## Structured exports

Select Structured JSON in a Document node, or connect a dictionary directly. All exports use a temporary file and replace the destination only after successful generation. File names must be valid portable base names. **Replace existing output** opts into overwriting; otherwise a unique suffix preserves existing files.

### XLSX

The workbook structure above is also accepted for output. Rows may be arrays or source records with a values array. Optional per-sheet column_types, column_formats and column_widths arrays must match the number of columns.

```json
{
  "sheets": [
    {
      "name": "Daily", "columns": ["Date", "Count"],
      "column_types": ["date", "integer"],
      "column_formats": ["yyyy-mm-dd", "0"],
      "column_widths": [16, 12],
      "rows": [["2025-05-10", 0], ["2025-05-11", 2]]
    },
    {"name": "Checks", "columns": ["Passed"], "rows": [[true]]}
  ]
}
```

Column types: auto, string, integer, number, boolean, date, datetime. Strings beginning with = remain literal data. Each sheet has a frozen header and an autofilter. In text mode, CSV quoting is respected.

### DOCX

```json
{
  "title": "Sample data report",
  "sections": [{
    "heading": "Verified results",
    "paragraphs": ["Total records: 2"],
    "table": {"columns": ["Date", "Count"], "rows": [["2025-05-11", 2]]},
    "images": [{"path": "counts.png", "caption": "Figure 1: Daily counts"}]
  }]
}
```

The optional template_file supplies a DOCX document whose existing content and styles are preserved; generated sections are appended. It is not a placeholder substitution engine. Without a template, the normal Word heading/table styles are used. Markdown-to-DOCX remains available in text mode.

### PNG

```json
{
  "type": "bar", "title": "Daily counts", "xlabel": "Date", "ylabel": "Records",
  "x": ["2025-05-10", "2025-05-11"],
  "series": [{"name": "Count", "y": [0, 2]}]
}
```

Line, grouped bar and scatter charts are rendered using Matplotlib Agg without a browser. Every series must contain one finite number per x value. Fonts available on the host determine language coverage.

## Reproduce the neutral end-to-end example

From backend, with the project dependencies installed:

```sh
pdm run python examples/reliable_report.py
pdm run python -m pytest tests/test_reliable_workflows.py -q
```

The example uses an isolated runtime under .cache/reliable-report-demo, a loopback-only deterministic model stub and the actual DAG/task implementations. It reads a two-sheet workbook, receives one intentionally invalid model response, repairs it, checks the total against source rows, and writes DOCX/XLSX/PNG in parallel. A second run must reuse the model result without another request. It does not contact an external model or evaluate model quality.

Outputs include input.xlsx, workflow.json, the three report artifacts and verification.json with run IDs, statuses and cache statistics. Pass --output-dir to place the demonstration elsewhere. The generated workflow definition can be inspected or adapted for a configured model; the stub endpoint exists only while the example runs.

For a real deployment, record the workflow JSON, source revision, model identity/revision, input hashes and environment versions. Keep credentials in local settings, outside exported workflows and source control.
