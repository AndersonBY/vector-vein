# Workflow CLI

Run `pdm run cli` in backend, or use the console executable `VectorVeinCLI` included beside the desktop executable in CLI-enabled builds. Commands write UTF-8 JSON to stdout; progress goes to stderr. No desktop window or separate Celery worker is required.

Global options precede the command:

- `--workspace DIR`: directory containing config.json and data/. Defaults to the source backend or executable directory. Use the desktop workspace or an isolated experiment directory.
- `--settings FILE`: external vv-llm V2 configuration for this process; credentials are not imported into the settings database.
- `--output-dir DIR`: artifact directory for this process.
- `--result-file FILE`: also save the command result as JSON.

```sh
python cli.py --workspace ./workspace init
python cli.py --workspace ./workspace workflow validate --file workflow.json
python cli.py --workspace ./workspace workflow create --file workflow.json --title "My workflow"
python cli.py --workspace ./workspace workflow list
python cli.py --workspace ./workspace workflow get WORKFLOW_ID
python cli.py --workspace ./workspace workflow update WORKFLOW_ID --file revised.json --expected-version 1
python cli.py --workspace ./workspace workflow patch WORKFLOW_ID --inputs values.json --expected-version 2
python cli.py --workspace ./workspace --settings settings.local.json workflow run WORKFLOW_ID --inputs values.json
python cli.py --workspace ./workspace workflow status RUN_ID
python cli.py --workspace ./workspace workflow records WORKFLOW_ID
```

A definition is a nodes/edges object or an exported workflow with its definition under data. Creation and updates validate unique IDs, registered tasks, edge handles, one incoming edge per field and an acyclic graph. Updates preserve metadata and do not call a model to generate Agent tool metadata.

Input overrides and patches:

```json
[{"node_id":"input-node","field_name":"text","value":"New input"}]
```

patch saves a new version. run uses a run-only copy, records the saved version and returns its run ID/status/output fields. --full on run/status includes the complete node snapshot. Unknown node/field references fail.

Exit codes: 0 success, 1 workflow failure, 2 invalid arguments/configuration/input. Run start emits its ID to stderr, permitting status queries from another process. Python nodes execute the code in the supplied workflow.

Model node templates also accept max_output_tokens and max_concurrent_requests (positive integers; 0 or absent inherits configuration), endpoint_policy="first", and thinking_enabled=false for DeepSeek/Qwen. Schema failures retain validation diagnostics and invalid output in run_stats; invalid outputs are never cached as successes.

Reproduce CLI tests with `python -m pytest tests/test_cli.py`. Help/version do not initialize a workspace.
