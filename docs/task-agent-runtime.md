# Task Agent runtime

The desktop Task Agent pins vv-agent 0.33.1, contract 32.1.1 and App Server v5. Python 3.12, vv-llm 0.9.0 and the official MCP SDK 2.3.0 are the verified dependency baseline. The upstream 0.33.1 upgrade retains record schema 1, inbox schema 3 and SQLite user_version 3; existing 0.31.3 execution stores do not need migration.

## Process and storage

The desktop owns one UTF-8 JSON-RPC child process:


```sh
VectorVeinCLI --workspace WORKSPACE task-agent serve
```

The execution ledger is `data/task-agent/sessions.db`. Product history lives in the independent `data/task-agent/tasks.db`. Business schema version 10 upgrades versions 1–9 in place, preserving tasks and messages. It retains credential-free model-failure observations, task/request-keyed risk reviews, workflow and MCP execution identities, Agent profiles, versioned Skills, MCP configuration, command receipts, event projections and replay cursors. Task snapshots preserve model routing, reasoning effort, the source Agent configuration, selected integration versions and the engine version without API keys. Credentials are resolved in the child at execution time.

A background consumer follows active, paused and waiting tasks even when their detail page is closed. It reads public App Server events in bounded pages, stores allowlisted product fields and advances each cursor in the same transaction. Replays deduplicate by event ID. An unfinished replay remains scheduled after execution ends. Reopening a thread subscribes and recovers through `thread/resume`. Disconnects retain the last business history and show a reconnect notice; they are not interpreted as task failure.

Opening a detail page first requests `get` with `cached: true`. This reads durable product history without starting the App Server or acquiring its synchronization lock. The page displays that history before making its normal background synchronization request. Subsequent updates retain the existing identity checks and polling behavior; a response from a previous task cannot replace the current page.

Interactive `create` and `retry_start` requests validate and persist the task before returning its cached detail. A service-owned startup queue creates the runtime thread and first turn in the background; `start_pending` keeps the detail page readable while startup is in progress. The submission lock does not cover App Server startup, so another task can be admitted during cold startup. Replayed task IDs share the same original first-turn command receipts and cannot enqueue duplicate starts. Scheduler/service callers retain synchronous creation unless they explicitly request background startup.

Unstarted tasks remain durably `PENDING`. Startup failures expose a safe `start_model_failure`, and an unqueued pending task shows a retry action after restart. Reading its history does not implicitly rerun it. Runtime mutations are rejected while startup is pending; shutdown stops the owned worker and leaves unfinished tasks available for explicit retry.

Submissions persist their original method, IDs, expected turn and payload before sending. An uncertain result is retried with identical bytes. Steering retains the actual active turn ID. The UI keeps an unconfirmed request available for retry and ignores responses after switching tasks. Reading history does not change recent-activity order.

## Product surfaces

- Workbench: choose a task Agent, shared model/reasoning settings and attachments, then enter a goal. Recent tasks use lightweight summaries sorted by update time and refresh silently every five seconds, including empty and fully completed lists. Window focus/visibility restoration refreshes them immediately. Project searches retain their pagination, and leaving the page cancels refresh timers.
- My agents: save reusable instructions, an optional cycle limit (off by default), workspace file-writing, shell and sub-agent switches, a three-mode approval policy, and selected workflows, Skills and individual MCP tools. Each task retains a creation-time copy; later Agent edits do not change it.
- Tasks: a full-width table or card catalog with server-side title/goal search, Agent and multi-status filters, creation/update sorting, and 10/20/50/100-item pages over the full history. Active lists refresh automatically. Favorites and the view preference persist locally; table selections can be favorited together. Route query parameters retain filters, sort and page when returning from a task.
- Detail: chronological messages and tool progress, expandable arguments and results, a plan, task configuration snapshot and file workspace. Live text is a volatile preview reconciled with durable events.
- User questions: retained text/single/multiple-choice forms support selection or a free-text explanation. Replies copy the exact displayed identity and digest. Stale answers cannot answer another question.
- Controls: suspend, resume, cancel, steering and follow-up use public protocol operations. Cancellation uses the retained completion reason; acceptance alone is not proof that execution stopped. Ended tasks with unresolved external operations retain a warning.
- Files: bounded browsing and previews of task inputs and generated files; text/Markdown/image previews, native document opening and folder reveal. Relative links under inputs/ and outputs/ open the task preview. Paths cannot escape the task workspace; private runtime resources are excluded. Tool-result text is read through the public paginated receipt API. Native opening is limited to document extensions.

The enabled tools are ask_user, todo_write, find_files, file_info, read_file, search_files and read_image, plus write_file/edit_file when the task configuration allows them. Legacy task snapshots keep their original workspace boundary. New tasks may access external file paths through the approval policy below. Private retained resources use durable storage under data/task-agent/retained. The subprocess is not an operating-system sandbox.

The `list` API accepts optional `statuses`, `agent_id`, `sort_by` (`created_at` or `updated_at`), `sort_order` (`asc` or `desc`) and `summary`. With `summary: true`, it returns the filtered `total`, historical Agent choices within the Project scope, and each visible task's maximum saved timeline cycle as `current_cycle_index`. Filtering and sorting precede pagination. Summary queries use the product database without per-task engine calls; sidebar and workbench polling omit summaries and event aggregates. The desktop catalog shows actual Project/model fields instead of unsupported public-sharing and platform-credit columns.

Bash and configured worker sub-agents are enabled for new general-Agent tasks. Skills and MCP tools are available only when explicitly selected. Task forks and full execution-history pagination are not enabled. Workflow and MCP execution honor the existing ask/auto/full approval policy. Workflow approval and HumanFeedback checkpoints are distinct from ask_user questions.

## Skills and MCP

Skills use vv-agent's native parser, `available_skills` and `activate_skill`. Imports are copied into immutable managed revisions under `data/task-agent/skills`; task retries retain those revisions even after source removal, library edits or catalog deletion. Instructions and resource reads do not grant shell, write or unrelated MCP access. The same selected Skills are available to configured child agents.

MCP uses the official Python SDK for stdio, Streamable HTTP and SSE. Library reads are offline; only an explicit test discovers tools. Discovery is tied to the saved connection revision. Environment/header values and private URLs stay in backend configuration; normal responses show key names and masked destination information. Blank edits preserve saved private values and explicit clear lists remove them. Agent selections expose individual frozen tool schemas; changed destinations or schemas cannot redirect existing tasks, while recognized credentials may rotate for the same destination.

A public Provider owns tool admission, dispatch and retained results. Calls share an owned client within the actual parent or child session, with separate child state. Durable identities prevent automatic replay after uncertain dispatch. A post-dispatch timeout, disconnect, cancellation or restart remains unknown unless terminal evidence proves an outcome. Task details expose compact `mcp_runs` and retained media paths. Deletion rejects active or unresolved external operations. Terminal run events and application shutdown close owned clients and stdio processes.

MCP annotations are untrusted evidence and cannot bypass ask/auto review. The independent review model receives safe selected tool/destination information, never saved configuration secrets. Credential-containing evidence falls back to manual approval. See [Skills and MCP contracts](task-agent-skills-mcp.md) for API, validation, storage and acceptance details.

The opt-in `tests/task_agent_integrations_live_smoke.py --settings SETTINGS.json --workspace EMPTY_DIRECTORY` checks the configured `deepseek-v4.1-flash` model through a native Skill, a bundled resource and two sequential synthetic MCP calls with exact argument approval. It verifies retained results, shared process state, credential absence and process exit. Settings stay external; the script does not control the desktop.

## Verification

Run the task service, interaction and CLI checks with the backend Python environment:

```sh
cd backend
pdm run pytest tests/test_task_agent.py tests/test_task_agent_projection.py tests/test_task_agent_interactive.py tests/test_cli.py -q
cd ../frontend
node --test tests/taskAgent*.test.js
```

The interactive integration test uses a local deterministic model endpoint with real App Server execution and built-in tools. It covers planning, restart while waiting for an answer, answer replay, file generation/preview, event replay, immutable Agent configuration, suspend/resume and cancellation. Additional checks cover schema migration, atomic cursor commits, failed-message retry and workspace path boundaries.

GUI acceptance uses an isolated workspace and the local scenario endpoint from tests/task_agent_scenario.py. Create a task through the desktop, inspect the plan, answer the form, verify completion and preview the generated report. Create a custom Agent, select it from the workbench and reopen the task after restarting the app. This requires actual UI interaction in addition to automated tests.

## Workflow jobs

Task creation captures each selected workflow's ID, version, root-definition digest and public input schema. Workflow contents and model credentials are not copied into the task configuration. A changed or unavailable root workflow is rejected before dispatch; a new task can select its updated definition. Nested workflows retain the existing runner's dependency-resolution semantics.

Each exposed workflow is a FunctionTool with a public RunConfig.tool_providers binding and an approval requirement honored by ask/auto modes. Full access bypasses per-call approval. Its Provider implements submit/query/cancel/authenticate. Job identity derives from the task, operation and attempt. Before publication, the adapter saves that identity and an assigned run ID in tasks.db. The existing workflow runner accepts that run ID with a submission identity under its admission transaction. Repeated admission returns the same run without republishing, including when a publish response was lost. A missing record or unknown outcome never triggers automatic resubmission.

The provider reads the authoritative WorkflowRunRecord. PAUSED stays pending; STOPPING stays unconfirmed until admitted work drains. Only FINISHED, FAILED or STOPPED produces a definitive result with the original acceptance evidence. External callbacks are not accepted; settlement uses local database evidence. The background consumer uses public thread/resume wakeups to query parked workflow providers after work completes.

Task details show linked workflow runs and their feedback forms, including retained child-run checkpoints. The workflow_feedback operation takes task_id, action_id, run_id, generation and answers. A checkpoint accepts a matching generation, and its request receipt is persisted with the continuation. Repeating the same answer does not publish another continuation; changing an answer under the same ID or answering a later checkpoint with an old generation returns a conflict. Publishing failures preserve the checkpoint's existing recovery action. An arbitrary running workflow cannot be suspended mid-node; the task exposes cooperative stop while that workflow is active.

Generated files registered by a finished, failed or stopped workflow are copied into the task's outputs/workflows/<run_id>/ directory, alongside readable output values. Copies are limited to 20 files of 50 MiB each; unavailable files are reported without rerunning the workflow. The retained tool receipt refers to these task-relative paths, while the original run and its artifacts remain accessible from the workflow link.

## Model binding and opt-in live validation

A task-scoped DesktopModelProvider resolves its frozen model ID, settings key and ordered endpoint mappings, using current credentials. App Server installs a global model resolver without task identity. The desktop configures its SessionDriver to use the native per-run ModelProvider fallback instead, so identical wire model IDs in different backends remain independent. Retained binding validation stays in the framework. Recheck this assembly choice when upgrading vv-agent; do not silently restore global model-ID lookup.

The ordinary test suite uses local deterministic model endpoints and disposable workflow databases. Run the real-model test only with explicit authorization:

~~~sh
cd backend
python tests/task_agent_live_smoke.py --settings /path/to/local.settings.json --workspace .cache/new-empty-live-workspace --model deepseek-v4.1-flash
~~~

The live test reads credentials through VECTORVEIN_LLM_SETTINGS_FILE without saving them to the workspace. It creates synthetic input and a local-only report workflow, tests read/question/file delivery and workflow approval/feedback/restart, checks that only one workflow run exists, and scans its generated files and databases for credential values. Its live-report.json contains statuses, tool names and checks, never keys or raw provider configuration. It does not start a GUI or use computer automation.

The workspace-writing switch governs the built-in write_file/edit_file tools. Workflow approval authorizes the selected workflow’s configured actions, which may access files or services outside the task folder under the existing desktop runner. The approval form links to that workflow for inspection. A task workspace is not a sandbox for workflow execution.


## Model failure presentation

The desktop observes exceptions through the public LLM client methods before vv-agent reduces an unsuccessful request to model_outcome_unknown. It retains only an allowlisted category, HTTP status, known parameter name and whether a rejection was observed before streaming began. Exception messages, response bodies, headers, URLs, keys and prompts are not copied into these diagnostic rows. Observations are joined to durable model-call events by call ID and survive application restart. Diagnostic-write failure does not replace the original exception or change execution/retry semantics.

The UI distinguishes authentication, permission, balance/quota, model/endpoint lookup, request parameters, context limits, rate limits, network/timeout and provider service errors. It links to Settings and shows the task's configured model and API model mapping. Historical model_outcome_unknown records without observations retain an explicit unknown-cause explanation; they are never reclassified as invalid keys by guesswork.

A generic unresolved-operation warning is suppressed only when every counted unresolved operation is an observed model rejection without streamed output. Unknown network outcomes, mixed tool/model outcomes and partial responses keep their uncertainty warning. This is presentation logic only: it does not rewrite the execution ledger or automatically retry a request. Model/endpoint changes require a new task because routing is snapshotted; credentials are resolved again for subsequent requests.


## Shell, delegation and permissions

New general-Agent tasks enable bash, check_background_command, stop_background_command, create_sub_task and sub_task_status. Custom Agent forms expose independent switches. Older saved profiles default these new capabilities off; older task snapshots never gain tools automatically. The resolved shell kind and executable are captured at task creation. Windows automatic selection prefers Git Bash, then PowerShell 7 and Windows PowerShell. POSIX uses Bash. The prompt names the actual shell so generated commands use the right syntax.

The host exposes native executors using public ToolRegistry registration; an allowlist alone does not make Bash visible to the planner. The native worker is configured through Agent.sub_agents. It shares the parent workspace and frozen model routing, credentials provider, reasoning settings, tool restrictions and permission policy. It supports foreground delegation, parallel batches, background execution and result queries, with further delegation disabled. Public child events project start/completion/results into the timeline. Root thread/resume wakeups recover child replies after process restart. Pending child approvals read their actual command/path arguments from the public SDK SessionRunEventStore view before display; child session IDs are not accepted as App Server thread IDs. This projection reads the execution ledger without writing it.

The workbench selects an approval mode for each new task; reusable Agents provide its default. The selected mode is frozen with the task. A retry with the same task ID and a different mode is rejected. Changing an Agent default does not change existing tasks.

| Mode | Automatic actions | Actions requiring approval |
| --- | --- | --- |
| Ask for approval | Enabled file operations inside the task workspace; planning, questions and delegation | External file access, all shell commands, selected workflows |
| Help me approve (default) | Ordinary workspace reads/planning, plus operations explicitly judged low risk by the independent configured LLM | Commands, file writes, external file access and workflows are reviewed; risky, uncertain or failed reviews require human approval |
| Full access | All enabled tools, including external files and selected workflows, using the current OS user's permissions | None at the per-tool approval layer |

The backend uses executor approval predicates and ToolPolicy, including for children. Decisions are matched to the native retained request and arguments. Denial returns a tool error without dispatch. Full access does not re-enable tools disabled in the Agent profile. These are application approval rules, not an OS sandbox; approving an unrestricted command authorizes its subprocess behavior. The full-access choice is visibly distinguished in the selector.

Windows Bash and command-management tools use desktop handlers registered through the public ToolRegistry interface. Each command is created suspended, assigned to a non-inheritable Windows Job with kill-on-close and no breakaway permission, then resumed. The explicit inherited-handle list contains only command stdin and output handles. No console window is opened. The exit code is read from the retained process handle after it is signalled; terminal completion additionally requires the Job's active-process count to reach zero. Detached descendants therefore keep a command running after its shell exits. Windows results retain status, exit_code, session_id and bounded output in a structured receipt.

Timeouts and explicit stop terminate the owned Job. Native run_cancelled stream events also stop jobs belonging to that root turn, including configured child agents; stale cancellation events cannot stop a later turn. Shutdown closes Jobs, and the OS kill-on-close rule covers an abrupt App Server exit. Pausing task reasoning does not freeze an already-running OS command. The Job is a process-lifecycle boundary, not a filesystem or network sandbox.

An actual observation/termination failure remains unknown rather than reporting fabricated success. Background handles are process-local and bound to the creating turn/workspace. Old SDK receipts are immutable: historical unknown results are not rewritten, and a missing handle after restart is not proof of an old command's result. Never rerun an uncertain command automatically. Other platforms continue using vv-agent's native command handlers. Complete output uses the existing SDK artifact store and public receipt reader. The UI uses eof, not a null nextOffset assumption, to stop result pagination.

Script checks cover actual shell output, background ownership/stop, delegation and parallel batches, disabled inherited tools, child-question restart/reply, cancellation, approval/denial before side effects, child-approval restart, and all three permission modes. The opt-in tests/task_agent_tools_live_smoke.py accepts --settings, --workspace and --model; it tests synthetic shell output and a child-computed total without storing API keys. It never drives the desktop.


## Independent approval reviewer

Settings → Model preferences includes a separate Task Agent risk-review model selector. Its provider/model pair is saved as task_agent_approval, validated with enabled model/family selection, and does not follow the primary task model. An empty setting is valid and routes reviews to the user. Each new review reads the current saved pair and current endpoint credentials; changing settings does not silently re-review a pending or already decided request.

Auto mode uses the public ApprovalProvider interface, after native approval admission and before tool dispatch. The reviewer receives the human goal, user follow-ups, workspace/shell, tool arguments and selected workflow descriptor. It has no tools. Its system instruction treats this evidence as data, including embedded instructions, and asks for exactly decision/risk/reason fields. Only an explicit allow with low risk and a compatible reason releases execution. No static command allowlist approves auto-mode commands. Workspace file writes also pass through this reviewer; ordinary local reads and planning do not require additional model calls.

Reviews use a bounded output, a 20-second per-request timeout and retry.max_attempts=1; configured endpoint failover still applies. Missing/disabled models, request errors, malformed/contradictory replies, oversized evidence, interrupted reviews and detected credential values fall back to human approval. Known endpoint keys are checked before any evidence is transmitted; credential-containing evidence is not sent. This is not a guarantee that arbitrary secrets can be recognized. No provider exception text or model free text is saved.

The audit stores only the native request identity, an operation fingerprint, reviewer model names, status, categorical verdict/reason, and timestamps. It excludes prompts, arguments and credentials. A successful decision is reused only for the same identity and arguments. A review interrupted before saving its outcome becomes manual; a late result cannot overwrite that outcome. Child agents inherit the same approval provider. Pending review UI shows progress and the fallback reason/settings link, and parent tool details show retained reviewer decisions. Existing manual approvals continue through native approval/resolve. Reviewing is distinct from waiting for human approval, and manual approval buttons are unavailable until the reviewer settles.

The opt-in shell/delegation acceptance script accepts --permission-mode auto to configure the reviewer only in its disposable test settings, validate real automatic approvals (including child writes), and submit a hypothetical credential-transfer operation for review without dispatching that command. It scans retained artifacts for configured key values.


## Desktop task-detail presentation

The task-detail layout follows the working reference at WSL ~/vectorvein/frontend/src/views/Workspace/TaskAgent/AgentTaskDetail.vue and components/workspace/taskAgent/{WorkspacePanelContainer,TaskOverviewCard,UserMessageBubble,SimplifiedToolActivityGroup,TaskContinueInput}. The reference repository is read only during alignment.

- Conversation/workspace split defaults to 40/60 with pointer and keyboard resizing. The surrounding 220px navigation can collapse. Workspace visibility does not discard open tabs; narrow windows can show the workspace alone and return to the conversation.
- A compact header and overview present the actual Agent, creation time, cycle count and actionable plan progress. User messages use the reference's right-aligned green bubble, with a separate dark surface, timestamps and copy actions.
- The timeline has only compact activity groups. Consecutive operations are grouped without merging across replies or turns. Expanding a group shows operation summaries; clicking opens full inputs, output and review evidence in a workspace tab. There is no detailed timeline view or switch.
- The workspace uses a 48px tab bar with independent file, tool, sub-agent result, plan and configuration views. Tabs can close, retain their own loaded content, and navigate with arrow/Home/End/Delete keys. Files are grouped by directory and searchable. Markdown previews use a 27px main heading and 14px body text, and stay beside the conversation instead of opening a modal.
- Follow-ups and bounded, collapsible questions/approval forms are part of the conversation flow. Existing native approval identities, retry receipts, pause/stop rules, and workflow checkpoints remain unchanged. Tool results still use the public paginated receipt API, including UTF-8 reconstruction across page boundaries.
- During ordinary execution, one thinking animation follows the latest live output and the send position contains the task's stop control. Questions, workflow waits, disconnected state and unresolved MCP provider waits do not show model-thinking feedback. Legacy paused tasks still expose resume; unknown MCP waits retain their explicit stop-waiting confirmation.
- The desktop shows only locally supported actions. Cloud sharing, organization membership, credits, sandbox management and task forks are not represented by decorative controls. Child tabs currently show the retained child result and status rather than a second execution controller.

Verification includes mounted Vue tests for activity grouping, equal-time user-message order, per-tab state, pagination and stale-response isolation. A separate headless browser fixture exercises the production components with synthetic API responses, including light/dark/1280px layouts, file/tool/child/plan tabs, workspace expansion and resizing. It does not open or control a user's desktop window or invoke a real model.


Windows process checks exercise native command execution, UTF-8 stdin/output and paths, exit code 259, detached descendants, timeout, explicit stop, root-task cancellation, ownership isolation, bounded output artifacts, concurrent capture isolation, failed supervision before user code resumes, and cleanup after abrupt host termination. The App Server test additionally cancels a task parked at a question after starting a background command and observes the retained process handle terminating.

Completed responses mark the end of a conversation segment. Intermediate assistant updates, tool groups and child results can collapse behind “View intermediate steps”; user messages, questions and final responses remain visible. Failed or unresolved command segments open by default. Paused and disconnected work is not treated as completed. Final-response markers are derived from retained completion events without duplicating the last assistant reply.

Workspace file tabs retain independent Preview/Code selection for Markdown and bounded HTML. HTML is rendered in an opaque, fully sandboxed iframe with a restrictive content security policy: inline styles and data images are allowed, while scripts, external resources and forms are blocked. Truncated HTML stays in source view. Command result tabs show the returned status, exit code, elapsed time and captured output separately, with the original receipt in a disclosure. A later command observation does not rewrite an earlier receipt.


## Local Projects and multiple folders

Projects persist in `task_projects`; `tasks.project_id` supplies project membership. Creation uses the desktop's native folder picker. Empty names use the first folder's basename. Folder paths are canonicalized and deduplicated, with the first folder serving as the default working directory. Editing a project uses an optimistic update guard and changes the scope of new tasks only. Existing tasks retain the project name and ordered roots in their configuration snapshot.

The navigation sidebar lists Projects below the primary navigation; it is the entry point for browsing and creating Projects, with no separate Project catalog tab or page. The empty list opens creation directly. Each project expands its tasks in five-item pages through the project-filtered `list` API with `limit` and `offset`. Project and task routes preserve the expanded tree and highlight the owning project. The hover card shows task counts, actual directory counts and paths, editing and local pinning. Header and project-row shortcuts open project creation and task creation. Individual Project pages link back to the workbench. Project edits refresh the sidebar, and expanded active task lists refresh their statuses. Pins persist in local UI storage; they do not change project ownership or filesystem permissions.

The main workbench has a Project selector next to the Agent selector above the composer. It defaults to a standalone task on each new visit. Choosing or clearing a Project keeps the current goal and attachments while renewing the submission identity. Submission uses the selected Project only after its metadata and folder availability have loaded. The dedicated Project page keeps its route-bound scope.

Project pages reuse the detail workspace component for folder selection and independent file preview tabs, including Preview/Code switching for Markdown and static HTML. The `project_files`, `project_preview_file` and `project_open_file` APIs resolve the Project's current saved roots directly and do not create or require an Agent task. They share the task file browser's path checks, bounded listings and bounded previews. Additional source formats such as Vue, TSX and Rust are previewed as text without expanding the native-open allowlist. Switching Projects or editing their ordered roots clears file tabs and rejects pending responses from the previous scope. Hiding and reopening the workspace retains the current tabs.

The Project page uses an icon-only edit action and a draggable workspace divider. Pointer and keyboard resizing share the detail-page interaction pattern, retain their width in local UI storage and constrain both panes; narrow screens use the existing workspace overlay instead. Its task search matches titles and goals across the Project before applying pagination, rather than filtering only recent items. The `list` API accepts a bounded literal substring in `search`, combined with `project_id`, `limit` and `offset`. Searches debounce input and discard stale responses; additional matches load in twenty-item pages. Active-task polling remains enabled for recent activity, while search pages retain their loaded results until a new search or retry.

This follows the cwd-plus-explicit-workspace-roots design in the local Codex reference: `codex-rs/core/src/config/mod.rs` resolves additional roots against cwd, starts workspace roots with cwd, and deduplicates them; `core/src/config/config_tests.rs::add_dir_override_extends_workspace_writable_roots` checks sibling roots without widening to their parent. The desktop does not create symlink mounts, merge folders or grant their common ancestor as a workspace root.

Project tasks execute directly in the primary folder. File tools can use absolute paths to additional roots; shell tools use `exec_dir` to select one. Children inherit the same roots and approval policy. The host verifies cwd and project metadata against the saved task before starting or resuming it. Missing or redirected project directories are rejected, not silently recreated. Standalone tasks keep their existing private task directories.

The independent risk reviewer receives the actual primary directory and the explicit root list. In request-approval mode, paths inside any selected root are workspace paths; other paths still require approval. Shell approval rules are unchanged. These application policies are not an OS sandbox. Project folders are shared between tasks, so agents must preserve unrelated files. Attachments are copied into `inputs/<task-id>/` under the primary root to separate them from other tasks' inputs.

The file panel selects one root at a time and distinguishes equal basenames by full paths. `project-files/<root-index>/<relative-path>` is a UI file reference, not a filesystem path for tools. Task previews resolve it against the task's frozen roots; Project-page previews use the Project's current roots. Both reject escapes, alternate data streams and private artifact paths. Browser listings stay bounded and omit dependency directories; root selection does not change a task's cwd.

Checks cover unnamed projects, canonical duplicates, edited project snapshots, project-filtered tasks, schema upgrades, invalid/forged roots, same-named files, per-task attachments, native folder picker cancellation, primary-root ordering, task creation inside a project, and an actual App Server flow with a child writing to the additional root, Bash running there after approval, and restart recovery after project edits.

## Removed conversation Agent

Task Agent is the sole interactive Agent module. The former pages, API namespaces, chat
WebSocket protocol, title worker, recording controls, and per-Agent shortcuts are removed.
Shared attachment previews, workflow node streaming, and global workspace shortcuts remain.
Workflow tool metadata generation is configured in Model preferences.
Migration 006 permanently deletes conversation tables, join tables, chat-triggered run records,
and obsolete settings and cached chat responses. The initial schema no longer creates them. Conversation models and
workflow message projections are removed; rollback cannot restore this history.

## SDK 0.33.1 / LLM 0.9.0

The dependency baseline includes OpenAI 3.46.0 and Anthropic 2.5.0. App Server v5,
session record schema 1, inbox schema 3, and SQLite user_version 3 are unchanged.
Upstream file paging accepts Unicode character cursors; workspace matching uses bounded regex
execution, and child Bash artifacts use the owning workspace scope. The desktop continues
using public tool registration and paginated result APIs. A script-based DeepSeek acceptance
run completed Bash and native child delegation with synthetic input, verified output, and no tool errors.

## Agent catalog and configuration

The desktop catalog follows the VectorVein TaskAgentNextAgents and AgentCatalogCard layout:
a compact header, separate navigation tabs and toolbar, a three-column desktop grid, model
labels and timestamps. Search, capability filters, sorting, pagination and grid/list view use
route query parameters. Favorites are stored locally. Secondary actions appear on hover or
keyboard focus. The configuration routes are `agents/new` and `agents/:agentId`, with basic
information/model defaults on the left and instructions/tools on the right. List filters are
retained when opening and returning from configuration.

The `profile` API reads a single saved profile without starting the task runtime. Profiles
retain creation/update timestamps and optional provider/model/reasoning defaults. Model
selections are validated against current configuration; credentials are never copied into
profiles. An empty selection follows the workbench. Choosing an Agent applies its defaults
to the new task composer; existing task snapshots are unchanged. The built-in general profile
can be edited in place, including its model defaults, permissions, tools, Skills and MCP
selections. Empty general-Agent instructions retain the built-in base instructions. Saved
general settings appear once in the catalog and apply to newly created tasks. Failed saves retain drafts, unavailable
workflows can be removed, and route changes reject late load responses. Leaving a modified
profile asks before discarding edits.

### Shared selection components

`components/taskAgent/AgentPicker.vue` is used by the workbench, task-list Agent filter,
and schedule editor. Its modal provides name/description/model search, capability filters,
pagination, and a configuration preview. An optional `agents` catalog reuses caller data;
without it, the component loads profiles and hydrates the selected label independently.

`components/taskAgent/TaskPicker.vue` provides server-side search, pagination and Agent,
Project, status and visibility filters. It includes hidden tasks by default. A caller can
supply `selectedTask` to reuse its own detail request; explicitly passing `null` means that
request is still pending. Page offsets never include an injected selected record.

Both components accept `v-model`, `disabled`, `compact`, `allowClear` and `placeholder`.
Confirmation or clearing emits `change(id, record)`; cancel and Escape discard the draft.
The shared `PickerModal` uses Ant Design theme tokens for teleported modal content.
The schedule editor retains responsibility for applying the selected task's runtime model,
approval mode and workspace, and rejects late detail responses.

`assets/css/scrollbar.css`, imported at the application entry point, applies 6px scrollbars,
transparent tracks and light gray thumbs globally, with a translucent light thumb in dark
mode. It also styles Ant Design virtual-list scrollbars and provides a Firefox fallback.

## Optional execution cycle limit

New and built-in general Agent profiles use `max_cycles: 0` by default, meaning no
application-configured cycle limit. Configuration exposes a switch: turning it on restores
the last entered positive limit; turning it off saves zero. Existing explicit limits and
frozen task snapshots keep their values. Task details display unlimited progress without a
fabricated denominator. Positive limits support the SDK's uint32 range.

vv-agent 0.33.1 requires a positive uint32 runtime budget; passing `None` silently falls back
to 10 cycles. The desktop maps zero to the public API's maximum budget, 4,294,967,295,
for both the parent run and worker sub-agent. This removes the previous 50-cycle application
cap while retaining the SDK's integer boundary. Tasks still finish normally or can be stopped.

## Permanent task and project deletion

The task catalog offers deletion in both table and card views. The project sidebar's
hover panel uses Ant Design text buttons and offers project deletion. Both actions require
confirmation. Project deletion removes the project and all its tasks, including tasks beyond
the first catalog page. It preserves every local folder and file, including task workspaces,
attachments and generated outputs. It does not move history to an archive.

`delete_task` requires `task_id` and `expected_updated_at`; `delete_project` requires
`project_id`, `expected_updated_at` and `expected_task_count`. The service rechecks the
project and task snapshots in a write transaction. Changed confirmations return HTTP 409
with `deletion_error: changed`. Only completed, failed or interrupted tasks may be deleted.
Unfinished workflows, risk reviews, background commands, active SDK sessions, live leases
and unconsumed inputs block deletion with a specific reason shown in the confirmation dialog.

vv-agent 0.33.1 has no permanent-delete RPC. Desktop maintenance therefore requires its pinned
SQLite schema version 3, fences writers with `BEGIN IMMEDIATE`, and removes owned sessions
and all descendants from the attached execution ledger along with desktop task projections,
messages, commands, workflow bindings, model failures and risk reviews. Ordinary transaction
failures roll back the changes; attached WAL databases do not guarantee cross-database
atomicity on power loss. Unknown execution schema versions are rejected. Global independent
workflow run history belongs to the workflow module and remains available there.

## Runtime model, permissions and context

The task-details composer keeps model/reasoning and permission selectors available while a
task is running or waiting for input. Changes apply between requests or before subsequent
tool operations; an in-flight model call is not interrupted. Existing approval requests
retain their identity and still require an explicit answer. An automatic risk review rechecks
the latest permission mode before authorizing execution.

Mutable overrides live in `config_snapshot.runtime_settings`; the original model binding,
Agent profile, Project roots and selected capability snapshots remain frozen. Model changes
use the public `thread/model/select` API with a durable desktop command and retained endpoint
route, including when configured models share a wire ID. The original runtime model binding
remains stable for native definition validation. Native context-summary calls keep their
separate original model route. Credentials are resolved at use and never saved in commands.
Settings changes use revision checks and an idempotent request ID, preserved after an uncertain
transport outcome and reconciled on the next task refresh.

The context ring beside the model selector shows recent reported input usage before the
popover is opened. Opening it reads native context estimates, window capacity and compression
threshold. The estimate is labeled separately from provider-reported usage. Cache hit rate
is the sum of reported cached input divided by the input counts for those same calls;
missing cache accounting stays unknown and partial accounting is labeled. Provider raw payloads
and retained summary contents are excluded from this view.

Manual compression uses `thread/compact/start` with an exact context version. Acceptance is
shown as queued until native events report completion or failure. A changed context requires
refreshing; an uncertain response retries the same action ID. The popover polls only while
open or while compression is pending and cancels its timers on navigation. Manual compression
is disabled during active execution or a pending interaction.


## Scheduling and notifications

Agent schedules use the shared visual schedule editor, per-occurrence execution identities, optional Project workspaces, new-task or retained-task execution, reversible task hiding, and configurable desktop notifications. See [Agent scheduling](task-agent-scheduling.md) for configuration, API, restart semantics, and verification.
