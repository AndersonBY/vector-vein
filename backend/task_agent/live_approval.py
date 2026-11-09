"""Consult the task's current user-selected policy before approving a subsequent tool operation."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from vv_agent.approval import ApprovalDecision

from .permissions import FILE_TOOLS, requires_approval
from .risk_review import LLMApprovalProvider
from .runtime_settings import permission_mode, settings_for

SAFE_INTERNAL_TOOLS = {"ask_user", "todo_write", "activate_skill", "create_sub_task", "sub_task_status", "check_background_command", "stop_background_command"}


class LiveApprovalProvider(LLMApprovalProvider):
    def _task_and_mode(self):
        task = self.store.get_task(self.task_id)
        mode = permission_mode(task) if task else "ask"
        return task, mode if mode in {"ask", "auto", "full"} else "ask"

    def should_request(self, request):
        task, mode = self._task_and_mode()
        if not task:
            return True
        if settings_for(task).get("preserved_approval_id") == request.request_id:
            return True
        if mode == "full" or request.tool_name in SAFE_INTERNAL_TOOLS:
            return False
        if request.tool_name in FILE_TOOLS:
            snapshot = task["config_snapshot"]
            roots = (snapshot.get("project") or {}).get("roots") or [str(self.store.path.parent / "workspaces" / self.task_id)]
            if snapshot.get("knowledge_bases"):
                from .knowledge_workspace import _VfsError, normalize_knowledge_path
                try:
                    virtual = normalize_knowledge_path(request.arguments.get("path", "."), Path(roots[0]))
                except (ValueError, _VfsError):
                    # The knowledge handler rejects malformed reserved paths before any IO.
                    return False
                if virtual is not None:
                    # Reads are scoped by the owner bridge; virtual writes are always rejected.
                    return False
            context = SimpleNamespace(workspace=Path(roots[0]), task_metadata={
                "workspace_roots": roots,
                "skill_roots": [item["bundle_path"] for item in snapshot.get("skills", [])],
            })
            return requires_approval(mode, request.tool_name, context, request.arguments)
        return True

    def decide(self, request):
        task, mode = self._task_and_mode()
        if task and settings_for(task).get("preserved_approval_id") == request.request_id:
            return None
        if mode == "full":
            return ApprovalDecision.allow()
        if mode != "auto":
            return None
        decision = super().decide(request)
        # A risk review may outlive a user's switch back to manual approval.
        task, latest_mode = self._task_and_mode()
        if task and settings_for(task).get("preserved_approval_id") == request.request_id:
            return None
        if latest_mode == "full":
            return ApprovalDecision.allow()
        return decision if latest_mode == "auto" else None
