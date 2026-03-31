from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from utilities.workflow import Workflow


def check_condition(value: Any, operator: str, target: Any) -> bool:
    if operator == "equal":
        return str(value) == str(target)
    elif operator == "not_equal":
        return str(value) != str(target)
    elif operator == "greater_than":
        return float(value) > float(target)
    elif operator == "less_than":
        return float(value) < float(target)
    elif operator == "greater_than_or_equal":
        return float(value) >= float(target)
    elif operator == "less_than_or_equal":
        return float(value) <= float(target)
    elif operator == "include":
        return str(target) in str(value)
    elif operator == "not_include":
        return str(target) not in str(value)
    elif operator == "is_empty":
        return not value
    elif operator == "is_not_empty":
        return bool(value)
    elif operator == "starts_with":
        return str(value).startswith(str(target))
    elif operator == "ends_with":
        return str(value).endswith(str(target))
    return False


def normalize_condition_value(field_type: str, value: Any) -> Any:
    if field_type == "number":
        return float(value)
    if field_type == "string":
        return str(value)
    return value


def get_conditional_branches(workflow: "Workflow", node_id: str) -> tuple[list[dict[str, Any]], str, str]:
    branches: list[dict[str, Any]] = workflow.get_node_field_value(node_id, "branches", default=[]) or []
    if branches:
        default_value_key = workflow.get_node_field_value(node_id, "default_value_key", default="default_value")
        default_output_handle = workflow.get_node_field_value(node_id, "default_output_handle", default="default_output")
        return branches, default_value_key, default_output_handle

    if workflow.is_node_field_output(node_id, "true_output") or workflow.is_node_field_output(node_id, "false_output"):
        return [
            {
                "operator": workflow.get_node_field_value(node_id, "operator"),
                "right_field_key": "right_field",
                "output_value_key": "true_value",
                "output_handle": "true_output",
            }
        ], "false_value", "false_output"

    return [], "", ""


def resolve_conditional_branch(workflow: "Workflow", node_id: str) -> tuple[str, Any, list[str]]:
    field_type = workflow.get_node_field_value(node_id, "field_type")
    left_field = normalize_condition_value(field_type, workflow.get_node_field_value(node_id, "left_field"))
    branches, default_value_key, default_output_handle = get_conditional_branches(workflow, node_id)

    if not branches:
        operator = workflow.get_node_field_value(node_id, "operator")
        right_field = normalize_condition_value(field_type, workflow.get_node_field_value(node_id, "right_field"))
        result = check_condition(left_field, operator, right_field)
        selected_value = workflow.get_node_field_value(node_id, "true_output" if result else "false_output")
        return "", selected_value, []

    active_handles = [branch.get("output_handle") for branch in branches if branch.get("output_handle")]
    if default_output_handle:
        active_handles.append(default_output_handle)
    active_handles = list(dict.fromkeys(active_handles))

    for branch in branches:
        output_handle = branch.get("output_handle")
        if not output_handle:
            continue

        operator = branch.get("operator") or "equal"
        right_field_key = branch.get("right_field_key") or "right_field"
        right_field = normalize_condition_value(
            field_type,
            workflow.get_node_field_value(node_id, right_field_key, default=""),
        )

        if check_condition(left_field, operator, right_field):
            output_value_key = branch.get("output_value_key") or "true_value"
            output_value = workflow.get_node_field_value(node_id, output_value_key, default="")
            return output_handle, output_value, active_handles

    default_value = workflow.get_node_field_value(node_id, default_value_key, default="")
    return default_output_handle, default_value, active_handles
