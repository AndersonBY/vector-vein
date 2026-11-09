"""Public AppServerHost bindings for desktop tasks."""
from __future__ import annotations

import os
from functools import partial
from pathlib import Path

from vv_agent import Agent, DefaultAppServerHost, RunConfig, ToolPolicy
from vv_agent.types import SubAgentConfig
from vv_agent.runtime.shell import resolve_shell_invocation
from vv_agent.app_server.host import model_summary
from vv_agent.app_server.protocol import ModelListResponse
from vv_agent.config import ConfigError
from vv_agent.model_settings import ModelSettings
from vv_agent.model import ModelRef
from vv_agent.workspace.local import LocalWorkspaceBackend

from .config import MAX_CYCLE_LIMIT, DesktopModelProvider, build_model_snapshot, current_llm_settings, resolve_snapshot
from .permissions import FILE_TOOLS as PATH_TOOLS, requires_approval


READ_ONLY_TOOLS = ["ask_user", "todo_write", "find_files", "file_info", "read_file", "search_files", "read_image"]
FILE_TOOLS = ["write_file", "edit_file"]
SHELL_TOOLS = ["bash", "check_background_command", "stop_background_command"]
SUB_AGENT_TOOLS = ["create_sub_task", "sub_task_status"]
SKILL_TOOLS = ["activate_skill"]


def execution_cycle_budget(profile):
    # The SDK requires a positive uint32; None falls back to 10 instead of disabling the limit.
    return profile.get("max_cycles", 0) or MAX_CYCLE_LIMIT


def desktop_tool_registry(permission_mode=None, approval_provider=None, *, knowledge_binding=None):
    from vv_agent.tools.builtins import build_default_registry
    from .mcp_library import MCPToolRegistry
    default_registry = build_default_registry()
    planner_extra_names = set(default_registry.list_planner_extra_tool_names())
    registry = MCPToolRegistry()
    for name in default_registry.list_tool_names():
        executor = default_registry.get_executor(name)
        registry.register_executor(
            executor,
            expose_to_model=default_registry.has_schema(name),
            planner_extra=name in planner_extra_names,
        )
    if os.name == "nt":
        from .windows_commands import command_manager
        for name, handler in (("bash", command_manager.run), ("check_background_command", command_manager.check), ("stop_background_command", command_manager.stop)):
            registry.get_executor(name).handler = handler
    # Explicit exposure is separate from ToolPolicy; configured children disable implicit ask_user.
    for name in [*SHELL_TOOLS, "ask_user"]:
        executor = registry.get_executor(name)
        registry.unregister(name)
        registry.register_executor(executor, expose_to_model=True, planner_extra=True)
    if permission_mode is not None:
        for name in [*PATH_TOOLS, "bash"]:
            if approval_provider is None:
                registry.get_executor(name).needs_approval = partial(requires_approval, permission_mode, name)
            else:
                from vv_agent.approval import ApprovalRequest

                def live_approval(context, arguments, tool_name=name):
                    return approval_provider.should_request(ApprovalRequest("preflight", tool_name, "preflight", arguments=arguments))

                registry.get_executor(name).needs_approval = live_approval
    if knowledge_binding:
        from .knowledge_workspace import register_knowledge_handlers
        register_knowledge_handlers(registry, **knowledge_binding)
    return registry


def command_shell(profile: dict) -> dict:
    if not profile.get("allow_shell", False):
        return {}
    shell = resolve_shell_invocation(shell=profile.get("shell", "auto"),
                                     windows_shell_priority=["git-bash", "pwsh", "powershell"])
    return {"kind": shell.kind, "executable": shell.prefix[0]}


def capability_instructions(snapshot: dict, *, child=False) -> str:
    shell = snapshot.get("command_shell", {})
    mode = snapshot.get("agent_profile", {}).get("permission_mode")
    text = (f"\nTask permission mode: {mode}. External file access and shell commands follow the application's approval policy. "
            "If approval is denied, do not retry the same action through another tool or child agent. "
            "Only perform actions needed for the user's request. " if mode else "")
    if snapshot.get("agent_profile", {}).get("allow_shell"):
        text += (f"\nThe bash tool executes {shell.get('kind', 'the configured shell')} commands in the task workspace. "
                 "Use that shell's syntax. Check exit_code and output. For running/stopping commands, query the existing session_id until a terminal status before claiming completion. "
                 "Copy session_id exactly as returned; never shorten it or change its prefix. "
                 "An unknown status means process-tree completion is unconfirmed. "
                 "Do not repeat a command merely because its outcome is unknown. Use check_background_command and "
                 "stop_background_command for retained command handles. Never expose credentials in commands or output.")
    if not child and snapshot.get("agent_profile", {}).get("allow_sub_agents"):
        text += ("\nDelegate independent, bounded work with create_sub_task using agent_id='worker'. "
                 "Children share this workspace and model; assign disjoint output paths. "
                 "Use tasks for a batch, or wait_for_completion=false and sub_task_status for background work. "
                 "Collect child results before declaring completion. Children cannot delegate further.")
    from .projects import workspace_instructions
    from .integrations import render_frozen_skills_prompt
    if snapshot.get("knowledge_bases"):
        from .knowledge import KNOWLEDGE_INSTRUCTIONS
        text += KNOWLEDGE_INSTRUCTIONS
    return text + workspace_instructions(snapshot) + render_frozen_skills_prompt(snapshot)


class DesktopTaskAgentHost(DefaultAppServerHost):
    def __init__(self, task_root: Path, *, settings_loader=current_llm_settings):
        self.task_root = task_root.resolve()
        self.settings_loader = settings_loader
        self.provider = DesktopModelProvider(settings_loader)
        self._mcp_runtime = None

    @property
    def mcp_runtime(self):
        if self._mcp_runtime is None:
            from .mcp_runtime import MCPRuntimeManager
            self._mcp_runtime = MCPRuntimeManager(self.task_root)
        return self._mcp_runtime

    def _on_event(self, event) -> None:
        if os.name == "nt":
            from .windows_commands import command_manager
            command_manager.on_event(event)
        if self._mcp_runtime is not None:
            self._mcp_runtime.on_event(event)

    def shutdown(self) -> None:
        if self._mcp_runtime is not None:
            self._mcp_runtime.shutdown()

    def _snapshot(self, request) -> dict:
        metadata = request.metadata if isinstance(request.metadata, dict) else {}
        snapshot = metadata.get("model_snapshot")
        if not isinstance(snapshot, dict):
            raise ValueError("Task model snapshot is required")
        return snapshot

    def _resolved(self, request):
        return resolve_snapshot(self._snapshot(request), self.settings_loader())

    @staticmethod
    def _settings(snapshot: dict) -> ModelSettings:
        effort = snapshot.get("reasoning_effort", "default")
        return ModelSettings(reasoning={"effort": effort} if effort != "default" else None)

    def _workspace(self, thread_id: str, cwd: str | None) -> Path:
        if not cwd:
            raise ValueError("Task workspace is required")
        workspace = Path(cwd).resolve()
        from .store import BusinessStore
        from .projects import validate_saved_roots
        task = BusinessStore(self.task_root / "tasks.db").get_task(thread_id)
        project = task["config_snapshot"].get("project") if task else None
        if project:
            roots = validate_saved_roots(project["roots"])
            if workspace != Path(roots[0]):
                raise ValueError("Task cwd does not match its saved Project")
            return workspace
        root = self.task_root / "workspaces"
        if workspace.parent != root or workspace.name != thread_id:
            raise ValueError("Task workspace is outside its allowed boundary")
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    def authorize(self, connection_id: str, method: str, params: dict) -> bool:
        if method != "thread/start":
            return True
        try:
            if params.get("agentKey") != "desktop-task" or not isinstance(params.get("inputId"), str):
                return False
            self._workspace(params["inputId"], params.get("cwd"))
            snapshot = params.get("metadata", {}).get("model_snapshot")
            from .store import BusinessStore
            from .integrations import validate_frozen_integrations
            task = BusinessStore(self.task_root / "tasks.db").get_task(params["inputId"])
            saved_snapshot = task["config_snapshot"] if task else None
            expected_project = saved_snapshot.get("project") if saved_snapshot else None
            if not isinstance(snapshot, dict) or snapshot.get("project") != expected_project or not snapshot.get("endpoint_options"):
                return False
            validate_frozen_integrations(self.task_root, snapshot, saved_snapshot)
            from .knowledge import validate_frozen_knowledge
            validate_frozen_knowledge(snapshot, saved_snapshot)
            return True
        except (TypeError, ValueError):
            return False

    def resolve_agent(self, request) -> Agent:
        resolved = self._resolved(request)
        snapshot = self._snapshot(request)
        profile = snapshot.get("agent_profile", {})
        from .store import BusinessStore
        from .integrations import validate_frozen_integrations
        saved = BusinessStore(self.task_root / "tasks.db").get_task(request.thread_id)
        validate_frozen_integrations(self.task_root, snapshot, saved["config_snapshot"] if saved else None)
        from .knowledge import knowledge_tools
        retrieval_tools = knowledge_tools(self.task_root, request.thread_id, snapshot)
        model_snapshot = snapshot
        from .workflows import workflow_tools
        from .mcp_runtime import mcp_tools
        return Agent(
            name="vectorvein-task-agent",
            instructions=(
                "Complete the user's goal using the task workspace and the available tools. "
                "For multi-step work, maintain a short todo list and explain progress briefly. "
                "Read supplied inputs before drawing conclusions. Ask the user when a decision is needed. "
                "When file tools are available, save deliverables under outputs/ and link them with relative paths. "
                "Do not claim a file was created or a tool succeeded without checking its result. "
                "For configured workflows, call their tools with the declared inputs and wait for the retained result. "
                "Workflow approval and human feedback are handled by the application; never invent approval or restart a pending run. "
                "Respond in the user's language.\n\n" + profile.get("instructions", "")
                + capability_instructions(snapshot)
            ),
            tools=workflow_tools(snapshot.get("workflow_tools", [])) + mcp_tools(snapshot.get("mcp_tools", [])) + retrieval_tools,
            sub_agents={"worker": SubAgentConfig(
                model=resolved.model_id,
                description="Complete a bounded delegated task and report verified results and output paths.",
                system_prompt=("Complete only the delegated task. You share the parent's workspace. "
                               "Read inputs, verify tool results, save deliverables under outputs/, and report failures honestly. "
                               "Respond in the user's language.\n" + profile.get("instructions", "")
                               + capability_instructions(snapshot, child=True)),
                max_cycles=execution_cycle_budget(profile),
            )} if profile.get("allow_sub_agents", False) else {},
            model=resolved,
            model_settings=self._settings(model_snapshot),
        )

    def build_run_config(self, request) -> RunConfig:
        resolved = self._resolved(request)
        snapshot = self._snapshot(request)
        profile = snapshot.get("agent_profile", {})
        from .store import BusinessStore
        from .integrations import validate_frozen_integrations
        store = BusinessStore(self.task_root / "tasks.db")
        saved = store.get_task(request.thread_id)
        saved_snapshot = saved["config_snapshot"] if saved else None
        from .runtime_settings import permission_mode as task_permission_mode
        if snapshot.get("project") != (saved_snapshot.get("project") if saved_snapshot else None):
            raise ValueError("Project workspace does not match the saved task")
        available_skills, skill_roots = validate_frozen_integrations(self.task_root, snapshot, saved_snapshot)
        from .knowledge import validate_frozen_knowledge, KNOWLEDGE_TOOLS
        knowledge_mounts = validate_frozen_knowledge(snapshot, saved_snapshot)
        from .workflows import WorkflowProvider
        from .mcp_runtime import MCPToolProvider
        descriptors = snapshot.get("workflow_tools", [])
        mcp_descriptors = snapshot.get("mcp_tools", [])
        workspace = self._workspace(request.thread_id, request.cwd)
        permission_mode = task_permission_mode(saved) if saved else profile.get("permission_mode")
        providers = {item["tool_name"]: WorkflowProvider(self.task_root, request.thread_id, workspace, item) for item in descriptors}
        if mcp_descriptors:
            runtime = self.mcp_runtime
            for item in mcp_descriptors:
                providers[item["namespaced_name"]] = MCPToolProvider(
                    self.task_root,
                    request.thread_id,
                    workspace,
                    item,
                    runtime,
                    store=store,
                )
        tools = READ_ONLY_TOOLS + (FILE_TOOLS if profile.get("allow_file_writes", True) else []) + list(providers)
        if knowledge_mounts:
            tools += KNOWLEDGE_TOOLS
        if profile.get("allow_shell", False):
            tools += SHELL_TOOLS
        if profile.get("allow_sub_agents", False):
            tools += SUB_AGENT_TOOLS
        if available_skills:
            tools += SKILL_TOOLS
        from .live_approval import LiveApprovalProvider
        approval_provider = LiveApprovalProvider(store, request.thread_id) if permission_mode is not None else None
        # Native model selections override requests without changing the frozen runtime identity.
        model_snapshot = snapshot
        summary_alias = f"desktop-summary/{request.thread_id}"
        return RunConfig(
            approval_provider=approval_provider,
            model=resolved,
            model_provider=DesktopModelProvider(self.settings_loader, snapshot=model_snapshot, summary_alias=summary_alias,
                on_failure=lambda call, failure: store.save_model_failure(request.thread_id, call.metadata.get("call_id"), failure)),
            model_settings=self._settings(model_snapshot),
            workspace=workspace,
            workspace_backend=LocalWorkspaceBackend(workspace, allow_outside_root=True) if (permission_mode or skill_roots) else None,
            tool_providers=providers,
            stream=self._on_event if (os.name == "nt" or mcp_descriptors) else None,
            tool_registry_factory=partial(
                desktop_tool_registry, permission_mode, approval_provider,
                knowledge_binding={"task_root": self.task_root, "task_id": request.thread_id,
                                   "snapshot": snapshot, "workspace": workspace} if knowledge_mounts else None,
            ) if permission_mode or knowledge_mounts or profile.get("allow_shell") or profile.get("allow_sub_agents") or snapshot.get("mcp_tools") else None,
            max_cycles=execution_cycle_budget(profile),
            tool_policy=ToolPolicy(allowed_tools=tools, approval="on_request" if permission_mode is not None else "default"),
            metadata={"task_id": request.thread_id,
                      "memory_summary_backend": snapshot["backend"],
                      "memory_summary_model": summary_alias,
                      **({"workspace_roots": snapshot["project"]["roots"]} if snapshot.get("project") else {}),
                      **({"allow_outside_workspace_paths": True} if (permission_mode or skill_roots) else {}),
                      **({"available_skills": available_skills, "skill_roots": skill_roots} if available_skills else {}),
                      **({"bash_shell": snapshot["command_shell"]["executable"]}
                      if profile.get("allow_shell", False) else {})},
        )

    def resolve_model(self, request: dict):
        settings = self.settings_loader()
        from .store import BusinessStore
        store = BusinessStore(self.task_root / "tasks.db")
        if request.get("route"):
            from .runtime_settings import resolve_selection
            snapshot = resolve_selection(store, request)
            resolved = resolve_snapshot(snapshot, settings)
            provider = DesktopModelProvider(self.settings_loader, snapshot=snapshot,
                on_failure=lambda call, failure: store.save_model_failure(request["route"]["desktop_task_id"], call.metadata.get("call_id"), failure))
            return provider.client(resolved), resolved
        # Initial and child requests retain the original task binding, even when wire IDs collide.
        task_id = request.get("metadata", {}).get("task_id")
        if task_id:
            task = store.get_task(task_id)
            if not task or request["model"] != task["config_snapshot"]["model_id"]:
                raise ValueError("Task model does not match its saved binding")
            snapshot = task["config_snapshot"]
            resolved = resolve_snapshot(snapshot, settings)
            provider = DesktopModelProvider(self.settings_loader, snapshot=snapshot,
                on_failure=lambda call, failure: store.save_model_failure(task_id, call.metadata.get("call_id"), failure))
            return provider.client(resolved), resolved
        if request.get("provider"):
            resolved = resolve_snapshot(build_model_snapshot(settings, request["provider"], request["model"]), settings)
        else:
            resolved = self.provider.resolve(ModelRef.named(request["model"]))
        return self.provider.client(resolved), resolved

    def list_models(self, request) -> ModelListResponse:
        settings = self.settings_loader()
        models = []
        for backend, config in settings.get("backends", {}).items():
            for model in config.get("models", {}):
                try:
                    resolved = resolve_snapshot(build_model_snapshot(settings, backend, model), settings)
                except (ConfigError, TypeError, ValueError):
                    continue
                if request.provider is None or request.provider == backend:
                    models.append(model_summary(resolved))
        return ModelListResponse(models=models)
