# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 20:58:33
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-04-29 19:29:46
import re
import json
import random
from copy import deepcopy
from typing import Any

from vv_llm.types import BackendType
from vv_llm.chat_clients import create_chat_client
from vv_llm.settings import settings as vv_llm_settings
from vv_llm.types.llm_parameters import ChatCompletionMessage

from worker.tasks import task, timer
from utilities.config import Settings
from utilities.workflow import Workflow
from api.utils import run_workflow_common
from models.workflow_models import WorkflowRunRecord, Workflow as WorkflowModel


@task
@timer
def empty(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    return workflow.data


@task
@timer
def conditional(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    field_type = workflow.get_node_field_value(node_id, "field_type")
    left_field = workflow.get_node_field_value(node_id, "left_field")
    right_field = workflow.get_node_field_value(node_id, "right_field")
    operator = workflow.get_node_field_value(node_id, "operator")
    true_output = workflow.get_node_field_value(node_id, "true_output")
    false_output = workflow.get_node_field_value(node_id, "false_output")
    if field_type == "string":
        left_field = str(left_field)
        right_field = str(right_field)
    elif field_type == "number":
        left_field = float(left_field)
        right_field = float(right_field)

    if operator == "equal":
        result = left_field == right_field
    elif operator == "not_equal":
        result = left_field != right_field
    elif operator == "greater_than":
        result = float(left_field) > float(right_field)
    elif operator == "less_than":
        result = float(left_field) < float(right_field)
    elif operator == "greater_than_or_equal":
        result = float(left_field) >= float(right_field)
    elif operator == "less_than_or_equal":
        result = float(left_field) <= float(right_field)
    elif operator == "include":
        result = str(right_field) in str(left_field)
    elif operator == "not_include":
        result = str(right_field) not in str(left_field)
    elif operator == "is_empty":
        result = left_field == ""
    elif operator == "is_not_empty":
        result = left_field != ""
    elif operator == "starts_with":
        result = str(left_field).startswith(str(right_field))
    elif operator == "ends_with":
        result = str(left_field).endswith(str(right_field))
    else:
        result = False

    if result:
        workflow.update_node_field_value(node_id, "output", true_output)
    else:
        workflow.update_node_field_value(node_id, "output", false_output)

    return workflow.data


@task
@timer
def random_choice(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    input_list = workflow.get_node_field_value(node_id, "input")
    if isinstance(input_list[0], list):
        output = []
        for item in input_list:
            output.append(random.choice(item))
    else:
        output = random.choice(input_list)
    workflow.update_node_field_value(node_id, "output", output)
    return workflow.data


@task
@timer
def json_process(
    workflow_data: dict,
    node_id: str,
):
    def _try_parse_json(input_data):
        try:
            return json.loads(input_data)
        except json.JSONDecodeError:
            pattern = r"```.*?\n(.*?)\n```"
            json_block_search = re.search(pattern, input_data, re.DOTALL)
            if not json_block_search:
                raise ValueError("Invalid JSON format")
            parsed_data = json.loads(json_block_search.group(1))
            return parsed_data

    workflow = Workflow(workflow_data)
    raw_input = workflow.get_node_field_value(node_id, "input")

    if isinstance(raw_input, str):
        parsed_input = _try_parse_json(raw_input)
    else:
        parsed_input = raw_input

    if isinstance(parsed_input, dict):
        input_list = [parsed_input]
    elif isinstance(parsed_input, list):
        input_list = parsed_input
    else:
        input_list = parsed_input

    parsed_input_data = []
    for input_item in input_list:
        if not isinstance(input_item, str):
            parsed_input_data.append(input_item)
            continue
        parsed_input_data.append(_try_parse_json(input_item))

    process_mode = workflow.get_node_field_value(node_id, "process_mode")
    key = workflow.get_node_field_value(node_id, "key")
    default_value = workflow.get_node_field_value(node_id, "default_value")
    keys = workflow.get_node_field_value(node_id, "keys", [])

    input_fields_has_list = isinstance(parsed_input, list) or isinstance(key, list)
    output = []
    output_keys = {k: [] for k in keys}
    if not isinstance(key, list):
        key = [key]

    if len(key) < len(parsed_input_data):
        key = key * len(parsed_input_data)
    elif len(key) > len(parsed_input_data):
        parsed_input_data = parsed_input_data * len(key)

    if process_mode == "get_value":
        for i in range(len(parsed_input_data)):
            output.append(parsed_input_data[i].get(key[i], default_value))
    elif process_mode == "get_multiple_values":
        for input_item in parsed_input_data:
            for k in keys:
                output_keys[k].append(input_item.get(k, default_value))
    elif process_mode == "list_values":
        for i in range(len(parsed_input_data)):
            output.append(list(parsed_input_data[i].values()))
    elif process_mode == "list_keys":
        for i in range(len(parsed_input_data)):
            output.append(list(parsed_input_data[i].keys()))

    if process_mode != "get_multiple_values":
        if not input_fields_has_list:
            output = output[0]
        workflow.update_node_field_value(node_id, "output", output)
    else:
        for k in keys:
            if not input_fields_has_list:
                output_keys[k] = output_keys[k][0]
            workflow.update_node_field_value(node_id, f"output-{k}", output_keys[k])

    return workflow.data


WORKFLOW_SELECTOR_PROVIDER_MAP = {
    "openai": BackendType.OpenAI,
    "anthropic": BackendType.Anthropic,
    "deepseek": BackendType.DeepSeek,
    "gemini": BackendType.Gemini,
    "groq": BackendType.Groq,
    "minimax": BackendType.MiniMax,
    "mistral": BackendType.Mistral,
    "moonshot": BackendType.Moonshot,
    "qwen": BackendType.Qwen,
    "yi": BackendType.Yi,
    "zhipuai": BackendType.ZhiPuAI,
    "baichuan": BackendType.Baichuan,
    "ernie": BackendType.Ernie,
    "stepfun": BackendType.StepFun,
    "xai": BackendType.XAI,
}


def _selector_backend_and_model(model_selector: str) -> tuple[BackendType | None, str]:
    if "/" in model_selector:
        provider, model = model_selector.split("/", 1)
    elif "⋄" in model_selector:
        provider, model = model_selector.split("⋄", 1)
    else:
        return None, model_selector
    return WORKFLOW_SELECTOR_PROVIDER_MAP.get(provider.strip().lower()), model.strip()


def _best_effort_select_workflow(workflows: list[WorkflowModel], selector_input: str, selector_template: str):
    if not workflows:
        return None, "no workflow candidates"
    if len(workflows) == 1:
        workflow = workflows[0]
        return workflow, f"selected the only candidate: {workflow.title}"

    normalized_query = f"{selector_template}\n{selector_input}".lower()
    best_workflow = workflows[0]
    best_score = -1
    for workflow in workflows:
        score = 0
        for token in (workflow.title, workflow.brief):
            if token and token.lower() in normalized_query:
                score += max(len(token), 8)
        if workflow.wid.hex.lower() in normalized_query:
            score += 100
        if score > best_score:
            best_workflow = workflow
            best_score = score
    return best_workflow, f"heuristic match score={best_score}"


def _select_workflow_with_model(
    workflows: list[WorkflowModel],
    selector_input: str,
    selector_template: str,
    llm_model: str,
) -> tuple[WorkflowModel | None, str]:
    backend_type, model_name = _selector_backend_and_model(llm_model)
    if backend_type is None or not model_name:
        return _best_effort_select_workflow(workflows, selector_input, selector_template)

    user_settings = Settings()
    vv_llm_settings.load(user_settings.get("llm_settings"))
    client = create_chat_client(backend=backend_type, model=model_name, stream=False)
    workflow_candidates = [
        {
            "wid": workflow.wid.hex,
            "title": workflow.title,
            "brief": workflow.brief,
        }
        for workflow in workflows
    ]
    prompt = (
        "Select the best workflow candidate.\n"
        "Return JSON with keys selected_workflow_id and reason only.\n\n"
        f"Selection guide:\n{selector_template}\n\n"
        f"User input:\n{selector_input}\n\n"
        f"Candidates:\n{json.dumps(workflow_candidates, ensure_ascii=False, indent=2)}"
    )
    response = client.create_completion(messages=[{"role": "user", "content": prompt}])
    content = response.content or ""
    try:
        parsed = json.loads(content)
        selected_workflow_id = parsed.get("selected_workflow_id", "")
        reason = parsed.get("reason", "")
    except Exception:
        selected_workflow_id = ""
        reason = content

    for workflow in workflows:
        if workflow.wid.hex == selected_workflow_id:
            return workflow, reason or f"selected by {llm_model}"
    return _best_effort_select_workflow(workflows, selector_input, selector_template)


def _apply_selector_input(workflow_data: dict, selector_input: str):
    if not selector_input:
        return workflow_data
    for node in workflow_data.get("nodes", []):
        template = node.get("data", {}).get("template", {})
        for field_name in ("input", "prompt", "query", "text", "topic", "requirement"):
            field_data = template.get(field_name)
            if field_data is None or field_data.get("is_output"):
                continue
            if field_data.get("value"):
                continue
            field_data["value"] = selector_input
            return workflow_data
    return workflow_data


@task
@timer
def workflow_selector(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    async_task_data = workflow.get_async_task(node_id)

    if async_task_data is None:
        selector_input = workflow.get_node_field_value(node_id, "input", "")
        selector_template = workflow.get_node_field_value(node_id, "template", "")
        llm_model = workflow.get_node_field_value(node_id, "llm_model", "")
        workflow_candidates = workflow.get_node_field_value(node_id, "workflow_ids", []) or []
        candidate_ids = [item.get("id") for item in workflow_candidates if item.get("id")]
        workflows = list(
            WorkflowModel.select().where(WorkflowModel.wid.in_(candidate_ids), WorkflowModel.status == "VALID")
        )
        workflows = [item for item in workflows if item.wid.hex != workflow.workflow_id]
        selected_workflow, selection_reason = _select_workflow_with_model(
            workflows,
            selector_input,
            selector_template,
            llm_model,
        )
        if selected_workflow is None:
            raise Exception("No workflow candidate selected")

        selected_workflow_data = _apply_selector_input(deepcopy(selected_workflow.data), selector_input)
        record_rid = run_workflow_common(
            workflow_data=selected_workflow_data,
            workflow=selected_workflow,
            run_from=WorkflowRunRecord.RunFromTypes.WORKFLOW,
            workflow_version=selected_workflow.version,
        )
        workflow.add_async_task(
            node_id,
            {
                "record_id": record_rid,
                "selected_workflow_id": selected_workflow.wid.hex,
                "selected_workflow_title": selected_workflow.title,
                "selection_reason": selection_reason,
            },
        )
        workflow_selector.retry(workflow.data, node_id, retry_delay=1)

    async_task_data = workflow.get_async_task(node_id)
    if async_task_data is None:
        raise Exception("Async workflow selector task not found")
    record = (
        WorkflowRunRecord.select()
        .join(WorkflowModel)
        .where(WorkflowRunRecord.rid == async_task_data["record_id"])
        .first()
    )
    if record is None:
        raise Exception("Selected workflow run record not found")
    if record.status in ("RUNNING", "QUEUED"):
        workflow_selector.retry(workflow.data, node_id, retry_delay=1)
    if record.status != "FINISHED":
        raise Exception("Selected workflow run failed")

    workflow.update_node_field_value(node_id, "selected_workflow_id", async_task_data["selected_workflow_id"])
    workflow.update_node_field_value(node_id, "selection_reason", async_task_data["selection_reason"])
    workflow.update_node_field_value(
        node_id,
        "output",
        {
            "workflow_id": async_task_data["selected_workflow_id"],
            "workflow_title": async_task_data["selected_workflow_title"],
            "record_id": record.rid.hex,
            "workflow_version": record.workflow_version,
            "data": record.data,
        },
    )
    return workflow.data


@task
@timer
def human_feedback(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    human_input = workflow.get_node_field_value(node_id, "human_input", "")
    workflow.update_node_field_value(node_id, "output", human_input)
    return workflow.data


@task
@timer
def workflow_loop(
    workflow_data: dict,
    node_id: str,
):
    def check_condition(value, operator, target):
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

    def render_template(template, context):
        for key, value in context.items():
            template = template.replace(f"{{{key}}}", str(value))
        return template

    def call_ai_model(backend: str, model: str, prompt: str) -> ChatCompletionMessage:
        user_settings = Settings()
        vv_llm_settings.load(user_settings.get("llm_settings"))
        client = create_chat_client(backend=BackendType(backend.lower()), model=model.lower(), stream=False)
        response = client.create_completion(messages=[{"role": "user", "content": prompt}])
        return response

    workflow = Workflow(workflow_data)
    internal_fields = [
        "workflow_id",
        "loop_count",
        "max_loop_count",
        "initial_values",
        "assignment_in_loop",
        "loop_end_condition",
        "output_field_condition_field",
        "output_field_condition_operator",
        "output_field_condition_value",
        "judgement_model",
        "judgement_prompt",
        "judgement_end_output",
    ]

    assignment_in_loop = workflow.get_node_field_value(node_id, "assignment_in_loop")
    max_loop_count = workflow.get_node_field_value(node_id, "max_loop_count")
    loop_end_condition = workflow.get_node_field_value(node_id, "loop_end_condition")
    output_field_condition_field = workflow.get_node_field_value(node_id, "output_field_condition_field")
    output_field_condition_operator = workflow.get_node_field_value(node_id, "output_field_condition_operator")
    output_field_condition_value = workflow.get_node_field_value(node_id, "output_field_condition_value")
    judgement_model = workflow.get_node_field_value(node_id, "judgement_model")
    judgement_prompt = workflow.get_node_field_value(node_id, "judgement_prompt")
    judgement_end_output = workflow.get_node_field_value(node_id, "judgement_end_output")

    used_credits = 0
    judgement_model_backend, judgement_model = judgement_model.split("⋄")
    max_loop_count = min(int(max_loop_count), 100)

    async_task_data = workflow.get_async_task(node_id)
    if async_task_data is None:
        workflow_id = workflow.get_node_field_value(node_id, "workflow_id")
        if workflow.workflow_id == workflow_id:
            raise Exception("Can't invoke self!")

        fields = workflow.get_node_fields(node_id)
        input_fields: dict[str, dict[str, Any]] = {}
        output_fields: dict[str, dict[str, Any]] = {}
        output_fields_cumulative: dict[str, list[str]] = {}

        for field in fields:
            if field in internal_fields:
                continue

            if workflow.is_node_field_output(node_id, field):
                output_fields[field] = {
                    "node_id": workflow.get_node_field_value_by_key(node_id, field, "node"),
                    "output_field_key": workflow.get_node_field_value_by_key(node_id, field, "output_field_key"),
                    "value": None,
                }
                output_fields_cumulative[field] = []
                continue

            field_original_node_id = workflow.get_node_field_value_by_key(node_id, field, "nodeId")
            field_value = workflow.get_node_field_value(node_id, field)
            input_fields.setdefault(field_original_node_id, {})[field] = field_value

        workflow_model = WorkflowModel.get(WorkflowModel.wid == workflow_id)
        _workflow_data = workflow_model.data
        data = {"input_fields": input_fields}
        for _node_id, node_fields in data["input_fields"].items():
            for original_node in _workflow_data["nodes"]:
                if original_node["id"] == _node_id:
                    break
            else:
                raise Exception("node not found")
            for field_name, field_value in node_fields.items():
                original_node["data"]["template"][field_name]["value"] = field_value

        record_rid = run_workflow_common(
            workflow_data=_workflow_data,
            workflow=workflow_model,
            run_from=WorkflowRunRecord.RunFromTypes.WORKFLOW,
        )

        workflow.add_async_task(
            node_id,
            {
                "record_id": record_rid,
                "output_fields": output_fields,
                "output_fields_cumulative": output_fields_cumulative,
                "loop_count": 1,
                "used_credits": 0,
            },
        )
        workflow_loop.retry(workflow.data, node_id, retry_delay=1)
    else:
        record_id = async_task_data["record_id"]
        output_fields = async_task_data["output_fields"]
        output_fields_cumulative = async_task_data["output_fields_cumulative"]
        loop_count = async_task_data["loop_count"]
        used_credits = async_task_data["used_credits"]
        record = WorkflowRunRecord.select().join(WorkflowModel).where(WorkflowRunRecord.rid == record_id).first()
        if record.status in ("RUNNING", "QUEUED"):
            workflow_loop.retry(workflow.data, node_id, retry_delay=1)
        elif record.status != "FINISHED":
            raise Exception("Run workflow failed!")

        nodes = record.data["nodes"]
        for node in nodes:
            for output_field, output_field_data in output_fields.items():
                if node["id"] != output_field_data["node_id"]:
                    continue
                output_value = node["data"]["template"][output_field_data["output_field_key"]]["value"]
                output_field_data["value"] = output_value
                output_fields_cumulative[output_field].append(output_value)  # 添加新的输出值到累积列表

        # 更新输出字段
        for output_field, output_field_data in output_fields.items():
            output_value = output_field_data["value"]
            workflow.update_node_field_value(node_id, output_field, output_value)

        # 检查循环终止条件
        should_continue = True
        if loop_count >= max_loop_count:
            should_continue = False
        elif loop_end_condition == "output_field_condition":
            condition_value = workflow.get_node_field_value(node_id, output_field_condition_field)
            should_continue = not check_condition(
                condition_value, output_field_condition_operator, output_field_condition_value
            )
        elif loop_end_condition == "ai_model_judgement":
            prompt = render_template(judgement_prompt, output_fields)
            ai_response = call_ai_model(judgement_model_backend, judgement_model, prompt)
            ai_response_content = ai_response.content or ""
            if ai_response_content.strip() == judgement_end_output.strip():
                should_continue = False

        if should_continue:
            # 继续循环
            loop_count += 1

            # 更新循环内赋值
            for field, assignment in assignment_in_loop.items():
                if assignment["source"] == "constant":
                    new_value = assignment["value"]
                elif assignment["source"] == "input_field":
                    new_value = workflow.get_node_field_value(node_id, assignment["value"])
                elif assignment["source"] == "output_field":
                    new_value = output_fields[assignment["value"]]["value"]
                elif assignment["source"] == "output_field_cumulative":
                    new_value = "\n\n".join(map(str, output_fields_cumulative[assignment["value"]]))
                elif assignment["source"] == "loop_count":
                    new_value = loop_count
                else:
                    new_value = None

                workflow.update_node_field_value(node_id, field, new_value)

            # 重新调用工作流
            workflow_id = workflow.get_node_field_value(node_id, "workflow_id")
            input_fields = {}
            for field in workflow.get_node_fields(node_id):
                if field not in internal_fields and not workflow.is_node_field_output(node_id, field):
                    field_original_node_id = workflow.get_node_field_value_by_key(node_id, field, "nodeId")
                    field_value = workflow.get_node_field_value(node_id, field)
                    input_fields.setdefault(field_original_node_id, {})[field] = field_value

            workflow_model = WorkflowModel.get(WorkflowModel.wid == workflow_id)
            _workflow_data = workflow_model.data
            data = {"input_fields": input_fields}
            for _node_id, node_fields in data["input_fields"].items():
                for original_node in _workflow_data["nodes"]:
                    if original_node["id"] == _node_id:
                        break
                else:
                    raise Exception("node not found")
                for field_name, field_value in node_fields.items():
                    original_node["data"]["template"][field_name]["value"] = field_value

            record_rid = run_workflow_common(
                workflow_data=_workflow_data,
                workflow=workflow_model,
                run_from=WorkflowRunRecord.RunFromTypes.WORKFLOW,
            )

            workflow.update_async_task(
                node_id,
                {
                    "record_id": record_rid,
                    "output_fields": output_fields,
                    "output_fields_cumulative": output_fields_cumulative,
                    "loop_count": loop_count,
                    "used_credits": used_credits,
                },
            )
            workflow_loop.retry(workflow.data, node_id, retry_delay=1)

    return workflow.data
