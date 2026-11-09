# Workflow execution recovery

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

Live owners, invalid ownership markers, inaccessible locks, legacy records with
no owners, paused feedback checkpoints, and terminal runs are preserved.
There is no timeout-based failure inference and no automatic replay after an
interruption. External side effects may already have occurred; inspecting the
retained results precedes a manual new run. Results that existed only inside a
terminated node and had not been checkpointed cannot be recovered.

`backend/tests/test_workflow_recovery_integration.py` exercises real process
locks, recovery and preservation cases, parent propagation, retained files,
late delivery and fast completion during submission.
