# Task Agent Skills and MCP

## Goal and acceptance scope

Integrate reusable local Skills and local/remote MCP tools into the desktop Task Agent.
Users must be able to manage integrations, select them in an Agent, create a task with a
frozen capability selection, observe actual activation/tool calls, and understand failures.
Existing workflows, Projects, permission modes, child agents and model settings remain usable.

Reference UI sources are the WSL VectorVein frontend's `TaskAgentNextSpace.vue`,
`MySkills.vue`, `SkillFormModal.vue`, `SkillSelector.vue`, `MCPToolManagement.vue` and
`MCPToolSelector.vue`. Desktop scope is a local library and user-configured servers;
cloud marketplaces, organization administration and hosted-provider OAuth are separate products.

## Product contract

- Add Skills and MCP entries to the Task Agent sidebar, using the current typography,
  full-width page headers, compact toolbars, Ant Design controls and hover/focus actions.
- Skills: searchable local library, create/edit instructions, import a directory or
  `.zip`/`.skill` bundle, inspect bundled resources and validation errors, enable/disable,
  and confirm removal. Source folders are never modified or deleted by library management.
- MCP: searchable server catalog, create/edit/disable/remove, stdio command/arguments/cwd
  and environment settings, Streamable HTTP and legacy SSE URLs/headers, configurable
  bounded timeouts, explicit connection test/tool discovery, tool schemas and selection.
  Loading a list or editing a draft must not launch a server.
- Agent configuration selects Skills and individual MCP tools alongside existing workflows.
  Empty selections grant no new capability. Unavailable selected entries remain visible
  and removable. Task details show the frozen selection and actual runtime outcomes.
- The workbench's MCP connector selector follows the reference `SimpleTaskCreator.vue`:
  use Agent defaults initially, allow an explicit per-task override, and preserve the goal
  draft while choosing tools. Changing a selection starts a new task-creation input identity.
  An omitted selection uses Agent defaults; an explicit empty selection clears those tools.
- Lists, cached task history and capability summaries read stored metadata without connecting
  to external MCP services. A completed connection test is labeled as a past test result,
  not proof of a still-open connection.
- Missing imports, invalid frontmatter, unavailable executables, authentication failures,
  timeouts, changed tool schemas and lost execution outcomes have actionable localized errors.

## Runtime and data invariants

### Skills

Use vv-agent 0.33.1's public Skill parser/validator, metadata `available_skills`, and
built-in `activate_skill`. Inspect the actual SDK prompt and child-agent propagation
before assembly. A Skill describes instructions and resources; it does not grant shell,
write access or MCP tools independently of the task's existing permissions.

Imported assets are copied into application-owned versioned storage. Validate size/count,
UTF-8/frontmatter, path collisions, symlinks/reparse points, archive traversal and expansion
limits before publication. Do not extract directly into a Project. Resource browsing is
bounded to the imported bundle. Editing a library entry creates a new revision; existing
tasks retain their original instructions/assets and do not depend on the source folder.
Deleting a library entry cannot break an already-created task's frozen bundle.

### MCP

Use the official Python MCP client SDK for transports/protocol, adapted through vv-agent's
public FunctionTool and Provider contracts. Do not implement a competing JSON-RPC protocol
or modify installed SDK files. Preserve the meaning of discovered input schemas, namespace
tool names deterministically and expose only the selected tools. Treat server descriptions
and tool results as untrusted task data. Untrusted read-only annotations alone do not bypass
the application's approval policy.

Discovered tool schemas are bound to the tested server configuration. Connection edits mark
that discovery stale until retested, while retaining old metadata for inspection. Test result
publication checks the saved revision so an old connection cannot overwrite a newer edit.

Store connection configuration and credentials separately from public task snapshots.
Credential-bearing environment/header values are write-only in normal API responses, retained
on unchanged edits, explicitly clearable, and resolved only in the backend. No raw credentials
may appear in model context, risk-review evidence, task messages/events, CLI output or errors.
Changing endpoint/command/tool identity must not silently redirect an existing task; credential
rotation may use current credentials for its retained server identity.
Stdio children inherit only the client SDK's bounded platform environment and explicit server
variables, never the entire application environment. Discard or redact untrusted subprocess
stderr. Redact configured credentials from returned MCP content as well as failure messages.
Apply the same credential rules to SDK loggers; suppressing wrapper exception text alone is
insufficient when a transport logs malformed remote content or connection failures itself.

Retain a dispatch identity and execution state before invoking an MCP tool. A completed return
is reusable evidence; a timeout, disconnect, cancellation or process restart after dispatch is
an unknown outcome unless there is affirmative terminal evidence. Never automatically replay
such an operation. MCP does not provide exactly-once external side effects. Present uncertainty
honestly and preserve the existing task interruption/recovery semantics.
Include integration execution rows in task/project deletion and reject deletion while their
external work is still active or its completion cannot be confirmed.

Ask/auto/full modes retain their current meanings. MCP calls participate in the same explicit
approval path and independent configured risk model. Approval evidence includes the selected
server/tool and action arguments without credentials. Child agents cannot gain integrations
or permissions absent from the parent selection.

Own transport connections/processes explicitly. Connection tests, failed startup, normal calls,
cancellation, task teardown and application exit must close their owned resources. Local stdio
processes use structured executable arguments and no visible console. Remote cancellation does
not imply that the remote server's side effects were undone or that execution stopped.

## Delivery stages

1. Verify SDK/reference behavior; settle public API shapes, storage and lifecycle ownership.
2. Implement and test library persistence, safe imports, secret-preserving MCP configuration
   and real transport discovery against disposable local servers.
3. Integrate Agent selections, frozen task capabilities, Skills activation, MCP Provider calls,
   approval, child-agent scope and non-replay recovery. Run real App Server integration tests.
4. Implement the management/configuration/detail surfaces and both locales. Exercise real
   Vue/Ant controls with a headless browser and isolated fixture data.
5. Review changes, run relevant regressions/build and synchronize desktop static resources.

## Library and task API contracts

The Task Agent API exposes `skills`, `skill`, `save_skill`, `import_skill`, `delete_skill`,
`skill_files` and `skill_preview_file`. Resource queries accept a retained `version`, including
after the catalog entry has been removed. The managed bundle remains available to existing tasks.
`skill_files` also returns the revision's native parsed `name` and `description`, so historical
inspection does not need to reimplement YAML metadata parsing in the frontend.
`save_skill` edits a complete native `SKILL.md`; an enabled-only update preserves its content.

`local_skills` discovers immediate Skill folders in `~/.agents/skills`, `~/.codex/skills`
and `~/.claude/skills`. It reads bounded `SKILL.md` metadata only, reports unavailable roots
and truncated scans, and does not execute instructions or import anything. Common installation
directory links resolve to their target and duplicate targets appear once; instruction-file
links and links inside imported bundles remain subject to the existing rejection rules.
Hidden folders and arbitrary recursive home-directory searches are excluded. Selected entries
use the existing `import_skill` validation and immutable revision storage.

MCP management uses `mcp_servers`, `mcp_server`, `save_mcp_server`, `delete_mcp_server`,
`test_mcp_server`, `set_mcp_tool_enabled` and `mcp_tools`. Only explicit connection tests perform
discovery. Server details return environment/header key names and configuration-presence flags,
never saved values. Blank edit values preserve credentials; `clear_env_keys` and
`clear_header_keys` remove named entries. A blank remote URL edit preserves the private URL;
`display_url` is a masked display value and must not be submitted as the original URL.

Agent profiles store `skill_ids` (at most 20) and `mcp_tool_ids` (at most 64). Skill identities
use the existing bounded desktop ID format; MCP tool identities are deterministic namespaced
IDs of at most 64 characters. Selections must be unique arrays; explicit `null` is invalid.
Distinct library entries with the same internal Skill name cannot be selected together.

Task creation freezes managed Skill revision descriptors in `config_snapshot.skills` and MCP
definitions in `config_snapshot.mcp_tools`. Public task views omit managed filesystem bindings
and large input schemas. A task retry retains these original definitions. Requests reconstructed
by the execution host must match the saved integrations and Agent configuration, including
legacy profiles whose absent permission fields cannot be added by a request.

Validation failures use `data.integration_error` with `kind`, `code`, `message` and bounded
diagnostics/details where available. Concurrent edit conflicts use the existing conflict
response. Generic database failures do not masquerade as task-deletion errors.

## Desktop usage

Open Skills or MCP from the Task Agent sidebar. Import Skills from a local directory or
bundle, or create a `SKILL.md` in the editor. Resource previews use the imported revision;
task links to a particular revision are read-only even when the library entry has changed
or been deleted.

In the import dialog, Local Agents scans these common locations on request. Filter by source,
search and select multiple entries, then import the selection. A partial failure keeps the
remaining selection and its per-item errors so retry does not repeat successful imports.
Source folders remain unchanged. Skills with the same name as an existing library item are
labeled for review before selecting them.

The Skill detail header uses text buttons for saving and deleting. Open Skill folder opens
the managed directory in the operating system's file explorer; historical inspection opens
that retained revision's directory. Unsaved new Skills have no directory action. Directory
resolution uses the same managed-root and link checks as resource reads.

Save an MCP server, then explicitly test its connection to discover tools. Enable the
individual tools to make them available to Agent configuration. Environment variables,
headers and private URLs are saved in the backend: blank saved fields preserve their values,
and the explicit clear controls remove them. After changing connection settings, test again
before selecting its tools.

The Agent editor has separate Skills and MCP capability tabs. The workbench's MCP button
is beside the composer controls and supports following Agent defaults, selecting tools for
this task, or clearing the selection. Library load failures offer retry and retain selected
IDs; they are not interpreted as deletion of those capabilities.

The task workspace shows frozen capabilities and tool results in tabs. MCP results include
the server/tool, durable status, diagnostics, structured content and retained artifacts.
Child-session MCP executions also appear in the tool list. An unknown outcome remains a
warning; stopping a provider wait does not replay the call or assert that remote effects
were cancelled. Historical unknown outcomes do not block a later independent conversation
turn.

## Verification requirements

Use temporary directories and local deterministic model/MCP fixtures. Cover stdio, Streamable
HTTP and SSE discovery/calls; configuration persistence after returning to the page; secret
preservation/clearing and no secret leaks; missing/changed selections; disabled servers;
invalid inputs; import traversal/symlink/oversize rejection; frozen Skill resources after
source edits/removal; real Skill activation; approval allow/deny; child scope; restart after
dispatch without duplicate execution; timeout/cancellation uncertainty; and process cleanup.

Headless checks cover empty/loading/error states, search, CRUD/import, tool schemas/selection,
Agent save/reload, task display, light/dark/narrow layout and keyboard access. Existing task,
workflow, Project and attachment regressions must pass. Do not restart an active manual-test
desktop window as part of automated validation.
