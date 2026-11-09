# Agent schedules, task visibility, and desktop notifications

Agent schedules run locally while the desktop application is running. The application does not install an operating-system timer or wake a closed application. Missed occurrences are skipped rather than replayed after startup. Times use the selected IANA time zone and the shared calendar rules described in [workflow scheduling](workflow-scheduling.md).

On Windows, minimizing to the system tray keeps the application and its schedulers running.
Choosing Exit stops them. The close dialog can remember either choice; **Settings → Window &
tray** changes it later. See [window close behavior](desktop-window.md).

## Configuration

The Agent sidebar includes **Schedules**. Each schedule stores a goal, an Agent profile, an optional Project, a model, reasoning effort, approval mode, repeat rule, and completion options. The form uses the shared `ScheduleEditor`, `ModelPicker`, `AgentPicker` and `TaskPicker` components. Agent and existing-task selection opens a searchable, filterable modal with a detail preview and explicit confirmation.

- **New task:** each occurrence creates a separate task. Without a Project it receives its own managed workspace. A Project uses the existing single- or multiple-root workspace rules.
- **Same task:** choose automatic creation on the first occurrence, or bind an existing task, including a hidden task. The chooser searches and paginates the full task history. Existing-task binding inherits that task's Agent and Project workspace; subsequent occurrences submit follow-up messages and retain its context. Each execution applies the schedule's saved model, reasoning effort, and approval mode. The original Agent capabilities and Project snapshot remain in force. Select a different existing task or switch to new-task mode to change that binding.
- **Hide after execution:** a completed, failed, or interrupted scheduled turn hides its task from ordinary task lists. Hidden tasks remain accessible under the task list's visibility filter and can be restored. Hiding does not stop execution or delete history or local files. Starting another scheduled follow-up makes the task visible while it runs.
- **Notify after execution:** the per-schedule switch requests a desktop notification, subject to the global Notifications setting. Ordinary Agent task completions also honor that global setting. Waiting for a user, approval, workflow, or paused execution does not count as completion.

Same-task occurrences are skipped while their task is busy or waiting. Independent new-task occurrences may overlap. An unconfirmed submission prevents further submissions from that schedule until it is reconciled or explicitly retried. The page refreshes execution status without invoking the model.

## Persistence and restart behavior

Business database schema 10 migrates existing versions in place. `tasks.hidden` defaults to zero. Schedules live in `task_schedules`; immutable admitted requests and outcomes live in `task_schedule_runs`. `task_completion_effects` deduplicates completion notifications per task and turn. Execution-store schema remains unchanged.

Occurrence admission and advancing the next scheduled time share a SQLite transaction. Each occurrence uses stable task, turn, and runtime-model-change request IDs. Replaying admission or retrying an uncertain App Server response uses the original request identity. A normal new **Run now** click starts a new occurrence; **Retry this run** resumes the saved occurrence. It does not silently replace an uncertain submission with a new task. Native command receipts retain the original request bytes.

Deleting a schedule stops future admissions while keeping existing tasks and files. Deleting a Project also removes its schedules in the Project deletion transaction; the existing protections against deleting active tasks still apply. A same-task schedule whose original task was deleted reports that the task is missing until another task is selected or the schedule is changed to new-task mode.

The desktop starts the scheduler and task projection consumer on startup and stops them during shutdown. CLI and test callers can use `service.scheduler.tick(instant)` for deterministic execution without a scheduler thread.

## API

The existing `task_agent` API exposes:

- `schedules`, `schedule`, `save_schedule`, `delete_schedule`.
- `run_schedule` with `schedule_id` and an idempotent `input_id`.
- `retry_schedule_run` with `schedule_id` and the original `run_id`.
- `set_hidden` with `task_id`, boolean `hidden`, and `expected_updated_at`.
- `list` accepts `visibility`: `visible` (default), `hidden`, or `all`, combined with its existing filters and pagination.

Schedule edits and deletion require `expected_updated_at`. Records include `next_run_at`, the retained same-task ID, and the latest occurrence's status and safe error code. Responses contain model selections but never endpoint credentials or raw provider exception text.

## Notifications

Settings includes **Desktop notifications**, disabled by default, and an explicit test button. Save the global switch to enable completion notifications. Notifications contain generic task status only; prompts, output, filenames, and model errors are excluded.

Windows uses native toast notifications through Windows PowerShell and registers `VectorVein.Desktop` under the current user's AppUserModelId registry key. The helper process has no visible console. macOS uses `osascript`; Linux uses `notify-send` when available. Commands are fixed and notification text is passed as separate data. System notification permissions and Do Not Disturb still control display.

Completion effects are claimed before submitting a native notification, favoring no duplicate notifications after restart. A crash between claiming and native submission can omit that notification. Native notification failure never changes the task outcome. Notification clicks do not navigate to a task.

## Verification

`test_task_agent_schedules.py` covers calendar timing, multi-root Projects, separate and continued tasks, hiding/restoring, completion deduplication, uncertain-response retry, restart admission, validation, API errors, and migration. `test_desktop_notifications.py` checks settings, status-only content, and command/data separation without displaying a native notification.

`test_task_agent.py::test_scheduled_agent_uses_real_app_server_project_continuation_and_completion_options` runs the real App Server against a local deterministic model endpoint. It verifies model and reasoning changes, retained follow-up context, Project/default workspaces, visibility, notification selection, and restart history without a paid model request or desktop automation.
