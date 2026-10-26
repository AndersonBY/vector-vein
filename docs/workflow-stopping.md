# Cooperative workflow stopping

`workflow_run_record.stop` accepts `{ "rid": "<run id>" }` and returns a normal
response with status `200`, the current run status in `msg`, and the serialized
run record in `data`. `workflow.stop` delegates to the same implementation and
also accepts an optional `wid`, which must match the run. The FastAPI route
`POST /api/workflow/{workflow_id}/stop/{record_id}` delegates to this operation.
Malformed identifiers return `400`; missing or mismatched records return `404`.

Stopping is idempotent. `FINISHED`, `FAILED`, and `STOPPED` are immutable terminal
states. A request received before any task is executing becomes `STOPPED`
immediately, including a queued run delivered later by the broker. A request
received while work is executing becomes `STOPPING`. Executing nodes may finish;
their output fields, artifacts, timing, and errors are retained. Nodes that have
not entered execution are blocked, and Celery chain continuations are cleared.
The run becomes `STOPPED` after admitted work and registered child runs drain.
Remaining pending or waiting timeline entries become `STOPPED`.

`workflow.check_status` returns `202` for `RUNNING`, `QUEUED`, and `STOPPING`, with
incremental completed nodes and the timeline. It returns `200` with `msg=STOPPED`
and the usual workflow snapshot for a stopped run. Clients must distinguish
`FINISHED` from `STOPPED` instead of interpreting every `200` as successful
completion. Run-record reads retain the actual status. Chat runs leave the
running state using the existing workflow terminal message code, with
`metadata.recordStatus=STOPPED` and a cancellation description.

Task admission, active counts, child registration, stop requests, and terminal
writes use the application's shared diskcache transaction. Final database
updates also compare the previous status. Every built-in task wrapper, parallel
batch, and workflow dispatcher uses the gate. Workflow invocation, selection,
and loop nodes register child runs before dispatch. Parent cancellation stops
those children and waits for their admitted work; an independently stopped
child propagates cancellation to its parent. Retry requests after stopping do
not publish another retry. An already published retry becomes a no-op when
delivered. A genuine failure in an admitted node remains `FAILED`, including a
failure observed after a stop request; cancellation does not hide errors.

Stopping does not kill worker processes or interrupt arbitrary Python, network,
model, media, or external service calls. It does not reverse external side
effects. An unresponsive admitted node keeps the run `STOPPING`. Active counts
are persistent rather than time-limited: an abruptly terminated worker requires
operational investigation and is never silently reported as drained. This
protocol applies to the current local Celery runner and does not copy the
server reference implementation's credit settlement or worker-kill behavior.

`backend/tests/test_workflow_stopping_integration.py` exercises actual task
wrappers, the eager Celery runner, disposable SQLite storage, queued delivery,
sequential and parallel drain, retained output/artifacts, recursive child drain,
retry suppression, genuine failure precedence, API responses, and concurrent
stop/completion terminal writes.
