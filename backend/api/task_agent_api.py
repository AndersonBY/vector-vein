import sqlite3

from api.utils import JResponse
from task_agent.client import TaskAgentError
from task_agent.config import ConfigError
from task_agent.service import TaskConflict, required_id, task_agent_service
from task_agent import files
from task_agent.projects import ProjectError
from task_agent.deletion import DeletionConflict
from task_agent.skills import SkillLibraryError
from task_agent.mcp_library import MCPLibraryError
from task_agent.scheduler import ScheduleError
from utilities.attachment_preview import AttachmentPreviewError

_SAFE_MCP_DETAIL_KEYS = {"count", "limit", "bytes", "pages", "tool_name", "namespaced_name", "reason", "issues", "status_code"}


def _serialize_skill_error(error: SkillLibraryError) -> dict:
    payload = {
        "kind": "skills",
        "code": error.code,
        "message": error.message,
    }
    if error.diagnostics:
        payload["diagnostics"] = [str(item)[:500] for item in error.diagnostics[:10]]
    return payload


def _serialize_mcp_error(error: MCPLibraryError) -> dict:
    payload = {
        "kind": "mcp",
        "code": error.code,
        "message": error.message,
    }
    if isinstance(error.details, dict) and error.details:
        safe_details = {k: v for k, v in error.details.items() if k in _SAFE_MCP_DETAIL_KEYS}
        if safe_details:
            payload["details"] = safe_details
    return payload


def _call(operation, *, deletion: bool = False):
    try:
        return JResponse(data=operation())
    except (KeyError, FileNotFoundError):
        return JResponse(status=404, msg="Task or file not found")
    except DeletionConflict as error:
        return JResponse(status=409, msg="Task deletion blocked", data={"deletion_error": error.code})
    except TaskConflict as error:
        return JResponse(status=409, msg=str(error))
    except ScheduleError as error:
        return JResponse(status=409, msg="Schedule request could not be applied", data={"schedule_error": {"code": error.code}})
    except SkillLibraryError as error:
        return JResponse(status=400, msg=error.message, data={"integration_error": _serialize_skill_error(error)})
    except MCPLibraryError as error:
        return JResponse(status=400, msg=error.message, data={"integration_error": _serialize_mcp_error(error)})
    except ConfigError as error:
        from task_agent.model_errors import configuration_failure
        return JResponse(status=400, msg="Invalid model configuration", data={"model_failure": configuration_failure(error)})
    except ProjectError as error:
        return JResponse(status=400, msg="Project folders unavailable", data={"project_error": error.code})
    except (TypeError, ValueError, AttachmentPreviewError):
        return JResponse(status=400, msg="Invalid task request")
    except TaskAgentError as error:
        if error.code == -32028:
            return JResponse(status=409, msg="Context changed. Refresh before compacting.", data={"context_error": "context_changed"})
        if error.code in {-32024, -32025, -32602}:
            return JResponse(status=409, msg="The task changed. Refresh and try again.")
        return JResponse(status=503, msg="Task Agent connection unavailable. Retry the same request.")
    except OSError:
        return JResponse(status=503, msg="Task resource unavailable")
    except sqlite3.Error:
        if deletion:
            return JResponse(status=503, msg="Task history unavailable", data={"deletion_error": "failed"})
        return JResponse(status=503, msg="Task data unavailable")


class TaskAgentAPI:
    name = "task_agent"

    def status(self, payload):
        return _call(lambda: task_agent_service().status())

    def create(self, payload):
        return _call(lambda: task_agent_service().create_task(payload, background=True))

    def list(self, payload):
        def operation():
            limit = payload.get("limit", 20)
            offset = payload.get("offset", 0)
            search = payload.get("search", "")
            if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
                raise ValueError("Invalid limit")
            if not isinstance(search, str) or len(search) > 256:
                raise ValueError("Invalid search")
            options = {key: payload[key] for key in ("statuses", "agent_id", "sort_by", "sort_order", "summary", "visibility") if key in payload}
            if "statuses" in options and (not isinstance(options["statuses"], list) or any(
                value not in {"PENDING", "PROCESSING", "WAITING_FOR_USER", "WAITING_FOR_APPROVAL", "WAITING_FOR_WORKFLOW",
                              "COMPLETED", "PAUSED", "FAILED", "INTERRUPTED"} for value in options["statuses"]
            )):
                raise ValueError("Invalid task status")
            if options.get("agent_id") is not None:
                required_id(options["agent_id"], "agent ID")
            if "sort_by" in options and options["sort_by"] not in {"created_at", "updated_at"}:
                raise ValueError("Invalid task sort")
            if "sort_order" in options and options["sort_order"] not in {"asc", "desc"}:
                raise ValueError("Invalid task sort")
            if "summary" in options and type(options["summary"]) is not bool:
                raise ValueError("Invalid task summary option")
            return task_agent_service().list_tasks(limit, payload.get("project_id"), offset, search, **options)
        return _call(operation)

    def projects(self, payload):
        return _call(lambda: {"projects": task_agent_service().list_projects()})

    def set_hidden(self, payload):
        return _call(lambda: task_agent_service().set_hidden(payload))

    def schedules(self, payload):
        return _call(lambda: {"schedules": task_agent_service().scheduler.list()})

    def schedule(self, payload):
        return _call(lambda: task_agent_service().scheduler.get(payload.get("schedule_id")))

    def save_schedule(self, payload):
        return _call(lambda: task_agent_service().scheduler.save(payload))

    def delete_schedule(self, payload):
        return _call(lambda: task_agent_service().scheduler.delete(payload))

    def run_schedule(self, payload):
        return _call(lambda: task_agent_service().scheduler.run_now(payload))

    def retry_schedule_run(self, payload):
        return _call(lambda: task_agent_service().scheduler.retry_run(payload))

    def delete_task(self, payload):
        return _call(lambda: task_agent_service().delete_task(payload), deletion=True)

    def delete_project(self, payload):
        return _call(lambda: task_agent_service().delete_project(payload), deletion=True)

    def project(self, payload):
        return _call(lambda: task_agent_service().get_project(payload.get("project_id")))

    def save_project(self, payload):
        return _call(lambda: task_agent_service().save_project(payload))

    def get(self, payload):
        def operation():
            cached = payload.get("cached", False)
            if type(cached) is not bool:
                raise ValueError("Invalid cached flag")
            return task_agent_service().get_task(required_id(payload.get("task_id"), "task ID"), cached=cached)
        return _call(operation)

    def send_message(self, payload):
        return _call(lambda: task_agent_service().send_message(payload))

    def recover(self, payload):
        return _call(lambda: task_agent_service().recover_task(payload.get("task_id")))

    def retry_start(self, payload):
        return _call(lambda: task_agent_service().retry_start(payload.get("task_id"), background=True))

    def action(self, payload):
        return _call(lambda: task_agent_service().act(payload))

    def update_runtime_settings(self, payload):
        return _call(lambda: task_agent_service().update_runtime_settings(payload))

    def task_context(self, payload):
        return _call(lambda: task_agent_service().task_context(payload))

    def compact_context(self, payload):
        return _call(lambda: task_agent_service().compact_context(payload))

    def approval(self, payload):
        return _call(lambda: task_agent_service().approve(payload))

    def workflows(self, payload):
        from task_agent.workflows import workflow_catalog
        return _call(lambda: {"workflows": workflow_catalog()})

    def workflow_feedback(self, payload):
        return _call(lambda: task_agent_service().workflow_feedback(payload))

    def profiles(self, payload):
        return _call(lambda: {"agents": task_agent_service().list_profiles()})

    def profile(self, payload):
        return _call(lambda: task_agent_service().get_profile(payload.get("agent_id")))

    def save_profile(self, payload):
        return _call(lambda: task_agent_service().save_profile(payload))

    def skills(self, payload):
        def operation():
            search = (payload or {}).get("search", "")
            return {"skills": task_agent_service().list_skills(search)}
        return _call(operation)

    def skill(self, payload):
        return _call(lambda: task_agent_service().get_skill((payload or {}).get("skill_id")))

    def local_skills(self, payload):
        return _call(lambda: task_agent_service().local_skills())

    def save_skill(self, payload):
        return _call(lambda: task_agent_service().save_skill(payload))

    def import_skill(self, payload):
        return _call(lambda: task_agent_service().import_skill(payload))

    def delete_skill(self, payload):
        return _call(lambda: task_agent_service().delete_skill(payload))

    def skill_files(self, payload):
        return _call(lambda: task_agent_service().skill_files(payload))

    def skill_preview_file(self, payload):
        return _call(lambda: task_agent_service().skill_preview_file(payload))

    def open_skill_directory(self, payload):
        return _call(lambda: task_agent_service().open_skill_directory(payload))

    def mcp_servers(self, payload):
        def operation():
            search = (payload or {}).get("search", "")
            return {"servers": task_agent_service().list_mcp_servers(search)}
        return _call(operation)

    def mcp_server(self, payload):
        return _call(lambda: task_agent_service().get_mcp_server((payload or {}).get("server_id")))

    def save_mcp_server(self, payload):
        return _call(lambda: task_agent_service().save_mcp_server(payload))

    def delete_mcp_server(self, payload):
        return _call(lambda: task_agent_service().delete_mcp_server(payload))

    def test_mcp_server(self, payload):
        return _call(lambda: task_agent_service().test_mcp_server(payload))

    def set_mcp_tool_enabled(self, payload):
        return _call(lambda: task_agent_service().set_mcp_tool_enabled(payload))

    def mcp_tools(self, payload):
        return _call(lambda: {"tools": task_agent_service().list_mcp_tools()})

    def files(self, payload):
        return _call(lambda: files.list_files(task_agent_service(), payload.get("task_id"), payload.get("root_id")))

    def preview_file(self, payload):
        return _call(lambda: files.preview_file(task_agent_service(), payload.get("task_id"), payload.get("path")))

    def open_file(self, payload):
        return _call(lambda: files.open_file(task_agent_service(), payload.get("task_id"), payload.get("path"), payload.get("reveal") is True))

    def project_files(self, payload):
        return _call(lambda: files.list_files(task_agent_service(), None, payload.get("root_id"), project_id=required_id(payload.get("project_id"), "project ID")))

    def project_preview_file(self, payload):
        return _call(lambda: files.preview_file(task_agent_service(), None, payload.get("path"), project_id=required_id(payload.get("project_id"), "project ID")))

    def project_open_file(self, payload):
        return _call(lambda: files.open_file(task_agent_service(), None, payload.get("path"), payload.get("reveal") is True, project_id=required_id(payload.get("project_id"), "project ID")))

    def tool_result(self, payload):
        return _call(lambda: task_agent_service().read_tool_result(payload))
