# Human feedback checkpoints

HumanFeedback runs its upstream nodes, resolves its connected `hint_message`,
and checkpoints the same run while waiting for a response. The feedback node
has status `102` and timeline state `WAITING`. Prefilled `human_input` and stale
feedback output are cleared when a new checkpoint is reached. A response is
accepted only through the resume operation, rather than implicitly trusting
saved node fields.

Current parallel-layer siblings drain and retain their outputs before the run
becomes `PAUSED`. All feedback nodes in that layer can join the same checkpoint.
No later layer enters execution while feedback is pending. A genuine sibling
failure remains `FAILED`; stopping while draining retains Stage 8's `STOPPING`
and `STOPPED` behavior.

## API

`workflow.resume` and `workflow_run_record.resume` accept:

```json
{
  "rid": "<existing run id>",
  "human_feedback_nodes": [
    {"node_id": "<pending feedback node id>", "content": "Human response"}
  ]
}
```

Every pending feedback node must appear exactly once, with nonblank string
content. Unknown IDs, duplicate entries, partial submissions, and blank input
return `400`. Runs that are not drained and paused return `409`; this includes
already resumed, finished, failed, or stopped runs. Successful resume returns
`200`, `msg=RUNNING`, and a serialized record with the same `rid`. In eager mode
the returned record can already be paused at the next checkpoint or finished.

`workflow.check_status` returns `102`, `msg=PAUSED`, and its usual workflow
snapshot. `data.data.pending_feedback_nodes` contains exactly the node IDs that
need responses. Run-record `get` and `list` retain status `PAUSED` and the
checkpoint in their data. Running/draining polling continues to use `202`.
FastAPI's synchronous wait and status endpoints return the paused checkpoint
immediately with payload status `102`. CLI execution exits with a JSON result
whose status is `PAUSED` and a nonzero exit code; it does not wait for input.

## Continuation and persistence

The checkpoint lives in the run record: completed nodes, node timeline, output
fields, artifacts, async-child state, accepted answers, and the continuation
generation. The existing shared diskcache transaction serializes task admission,
drain counts, resume, and stop. A resumed dispatcher constructs the remaining
DAG from the checkpoint and excludes `SUCCEEDED` and `SKIPPED` nodes. It does
not create a new run, reset outputs, or replay completed side effects.

Each accepted continuation advances `feedback_generation`; tasks from an older
chain generation cannot enter execution. Concurrent resume submissions admit
one continuation. A later checkpoint accepts only its own pending node IDs, so
a delayed submission for an earlier checkpoint cannot answer the new one.
Paused records survive application restart and can be resumed from a new
process. New runs clear checkpoint fields and require new feedback.

If publishing a continuation raises an error before any task remains admitted,
the run returns to `PAUSED` with `feedback_resume_ready=true`. The checkpoint
retains accepted answers and every result already saved, because publication
may have succeeded. The recovery action submits `human_feedback_nodes: []` to
continue from that checkpoint with a new generation. This recovery also covers
automatic parent continuation. If work is already admitted, its current state
is retained rather than claiming it was rolled back.

## Nested workflows and chat

Invocation, selector, and loop nodes propagate a child pause without consuming
polling retries. A paused parent's `pending_feedback_runs` contains child run
IDs. Fetch those records to display their feedback forms and submit responses
against the child's `rid`. The parent stays paused while its child continues,
then automatically continues when the child finishes. Independent child
cancellation stops its parent; child failures remain failures and cooperatively
stop other child runs instead of leaving their human prompts pending. A parent may
also have its own feedback nodes and requires those responses after its
children finish. Stopping a paused parent stops pending children and prevents
later resume.

A paused chat workflow keeps the existing running-workflow message code and
sets `metadata.recordStatus=PAUSED`. It does not append a model answer or claim
workflow completion. Resume changes that metadata back to `RUNNING`; normal
completion, failure, and stop projections still determine the terminal message.

## Verification and limits

`backend/tests/test_workflow_feedback_integration.py` exercises the actual task
wrappers and Celery runner against disposable SQLite storage, including
sequential and parallel checkpoints, draining, retained outputs, exact-set
validation, concurrent submissions, old chain generations, conditional skips,
nested selector pause/resume, publish recovery, stop, and a new-process resume
that proves completed file-writing effects are not replayed.

The protocol does not interrupt admitted tasks or reverse external effects.
Stage 8's operational limit remains: an unresponsive or abruptly terminated
admitted worker requires investigation and is not silently declared drained.
This checkpoint mechanism is specific to HumanFeedback and nested workflow
waiting; it is not a general arbitrary-node replay facility.
