# Workflow execution recovery

Chat workflow messages query the authoritative run as soon as they mount and
continue polling while it is running, queued, stopping, or paused. Returning to
a conversation shows current state and completed outputs without expanding
execution details by default. Failure and feedback states expand their existing
details. Responses belonging to an unmounted message or a different run are
discarded. Conversation drafts are independent of workflow polling.

Successful chat runs pass `record_id` to `message.append_answer`. The backend
validates the finished run and its source message, projects the result before
building model history, and serializes continuation creation. Each continuation
stores `metadata.workflow_record_id`. A repeated request, or a source message
that is no longer the conversation's current tail, returns
`data.already_appended=true` without creating a message or changing the selected
branch. The client refreshes history in that case.

## Process exit detection

Each executing process holds a kernel file lock for its lifetime under
`<data_path>/execution-locks/<random UUID>`. Runs store the process identities in
`data._execution_owners` at submission and task admission. Resume adds the new
owner; starting a new run clears inherited ownership. Windows uses byte-range
locking and Unix uses `flock`; process exit releases either lock automatically.

Desktop startup reconciles runs before starting Celery and the scheduler. A
`RUNNING`, `QUEUED`, or `STOPPING` run becomes `FAILED` with failure code
`WORKFLOW_INTERRUPTED` only when every recorded owner has provably exited.
Completed node snapshots, output fields, artifacts, and timing are retained;
unfinished timeline entries become failed. Stale active counts are cleared.
Registered parents observe the child's failure through existing propagation.
Late broker deliveries are rejected by the terminal-state admission guard.
Failure to project a chat message cannot roll back the recovered run.

Live owners, invalid ownership markers, inaccessible locks, legacy records with
no owners, paused feedback checkpoints, and terminal runs are preserved.
There is no timeout-based failure inference and no automatic replay after an
interruption. External side effects may already have occurred; inspecting the
retained results precedes a manual new run. Results that existed only inside a
terminated node and had not been checkpointed cannot be recovered.

`backend/tests/test_workflow_recovery_integration.py` exercises real process
locks, recovery and preservation cases, parent propagation, retained files,
late delivery, terminal message projection, fast completion during submission,
and idempotent chat continuation. `frontend/tests/chatFailures.test.js` covers
mounted chat restoration, overlapping polls, stale responses, draft isolation,
and late submission results.
