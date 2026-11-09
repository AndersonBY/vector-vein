# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 20:58:33
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-25 21:42:59
import re
import io
import builtins
import uuid
import shutil
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, cast
from threading import RLock

from api.utils import run_workflow_common
from models.workflow_models import WorkflowRunRecord, Workflow as WorkflowModel
from utilities.config import Settings
from utilities.workflow import Workflow
from utilities.workflow_artifacts import register_artifact
from utilities.workflow_errors import WorkflowInputError, WorkflowExecutionError, add_failure, node_failure, redact_message, workflow_error_payload
from utilities.workflow_stopping import WorkflowStopped
from utilities.workflow_feedback import WorkflowPaused
from utilities.general import mprint_with_name
from utilities.media_processing import get_screenshot
from utilities.network import new_httpx_client
from utilities.web_search import search_pages
from utilities.http_request import perform_http_request
from worker.tasks import task, timer


mprint = mprint_with_name(name="Tools Tasks")

# ponytail: serialize legacy working-directory file collection; use isolated workers if throughput matters.
_PYTHON_FILE_LOCK = RLock()


@task
@timer
def http_request(workflow_data: dict, node_id: str):
    workflow = Workflow(workflow_data)
    for field, value in (("status_code", None), ("response_headers", {}), ("response_body", ""), ("response_json", None)):
        workflow.update_node_field_value(node_id, field, value)
    defaults = {"url": "", "method": "GET", "headers": "{}", "query_params": "{}", "body_type": "none", "body": "", "timeout": 30, "follow_redirects": False, "fail_on_http_error": True}
    options = {field: workflow.get_node_field_value(node_id, field, default) for field, default in defaults.items()}
    result = perform_http_request(**options)
    for field, value in result.items():
        workflow.update_node_field_value(node_id, field, value)
    if options["fail_on_http_error"] and result["status_code"] >= 400:
        raise RuntimeError(f"HTTP request returned status {result['status_code']}")
    return workflow.data

SKIPPING_FIELDS = [
    "language",
    "code",
    "output",
    "use_oversea_node",
    "list_input",
    "error_msg",
    "console_msg",
    "files",
    "continue_on_error",
]

def convert_parameter_value(value, parameter_type):
    if parameter_type == "str":
        return str(value)
    elif parameter_type == "int":
        return int(value)
    elif parameter_type == "float":
        return float(value)
    elif parameter_type == "bool":
        return bool(value)
    return value  # if none of the types match


@task
@timer
def programming_function(workflow_data: dict, node_id: str):
    workflow = Workflow(workflow_data)
    code = workflow.get_node_field_value(node_id, "code")
    if workflow.get_node_field_value(node_id, "language") != "python":
        raise ValueError("Unsupported language")
    list_input = workflow.get_node_field_value(node_id, "list_input", False)
    if isinstance(list_input, str):
        list_input = list_input.lower() == "true"
    parameters_batch = None
    for field in workflow.get_node_fields(node_id):
        if field in SKIPPING_FIELDS:
            continue
        parameter = workflow.get_node_field_value(node_id, field)
        parameter_type = workflow.get_node_field_value_by_key(node_id, field, "type")
        if list_input:
            if not isinstance(parameter, list):
                raise ValueError("Batch parameters must be lists")
            if parameters_batch is None:
                parameters_batch = [{} for _ in parameter]
            if len(parameter) != len(parameters_batch):
                raise ValueError("Batch parameter lists must have equal lengths")
            for batch, value in zip(parameters_batch, parameter):
                batch[field] = convert_parameter_value(value, parameter_type)
        else:
            if parameters_batch is None:
                parameters_batch = [{}]
            parameters_batch[0][field] = convert_parameter_value(parameter, parameter_type)
    if parameters_batch is None:
        parameters_batch = [{}]
    match = re.search(r"```.*?\n(.*?)\n```", code, re.DOTALL)
    compiled = compile(match.group(1) if match else code, "<workflow-python>", "exec")
    output_folder = Path(Settings().output_folder).resolve()
    output_folder.mkdir(parents=True, exist_ok=True)
    output_batch, files_batch, errors, consoles = [], [], [], []
    for parameters in parameters_batch:
        console = io.StringIO()
        # Capture this node's direct prints without replacing process-wide stdout.
        def node_print(*args, **kwargs):
            kwargs.setdefault("file", console)
            print(*args, **kwargs)
        namespace = {"__builtins__": {**vars(builtins), "print": node_print}}
        with _PYTHON_FILE_LOCK:
            original_files = set(Path.cwd().iterdir())
            try:
                exec(compiled, namespace)
                main = cast(Callable[..., Any] | None, namespace.get("main"))
                output_batch.append(main(**parameters) if callable(main) else None)
                errors.append("")
            except Exception as exc:
                output_batch.append(None)
                errors.append(redact_message(traceback.format_exc(), workflow_data))
                if workflow.get_node_field_value(node_id, "continue_on_error", False) is not True:
                    add_failure(workflow_data, node_failure(exc, workflow_data, node_id, "tools.programming_function"))
            consoles.append(console.getvalue())
            files = []
            for file in sorted(set(Path.cwd().iterdir()) - original_files):
                if not file.is_file() or file.is_symlink():
                    continue
                destination = output_folder / file.name
                if file.resolve() != destination:
                    if destination.exists():
                        destination = output_folder / f"{file.stem}_{uuid.uuid4().hex[:12]}{file.suffix}"
                    shutil.move(str(file), str(destination))
                register_artifact(workflow.data, node_id, destination)
                files.append(str(destination))
            files_batch.append(files)
    for field, values in (("output", output_batch), ("files", files_batch), ("error_msg", errors), ("console_msg", consoles)):
        workflow.update_node_field_value(node_id, field, values if list_input else values[0])
    if any(errors) and workflow.get_node_field_value(node_id, "continue_on_error", False) is not True:
        indexes = [index for index, error in enumerate(errors) if error]
        failure = workflow_data["failures"][0]
        raise RuntimeError(f"Python node failed at item indexes: {indexes}; {failure['exception_type']}: {failure['message']}")
    return workflow.data


@task
@timer
def image_search(workflow_data: dict, node_id: str):
    workflow = Workflow(workflow_data)
    search_text = workflow.get_node_field_value(node_id, "search_text")
    search_engine = workflow.get_node_field_value(node_id, "search_engine")
    count = workflow.get_node_field_value(node_id, "count")
    output_type = workflow.get_node_field_value(node_id, "output_type")
    if search_engine != "pexels":
        raise WorkflowInputError("该图片搜索引擎已不受支持，请在节点中重新选择 Pexels。")
    if isinstance(count, str) and count.strip().isdigit():
        count = int(count)
    if type(count) is not int or not 1 <= count <= 80 or output_type not in {"text", "markdown"}:
        raise WorkflowInputError("图片搜索数量必须是 1 到 80 的整数，输出格式请选择文本或 Markdown。")
    key = Settings().get("pexels_api_key", "")
    if not key:
        raise WorkflowInputError("请先在设置中配置 Pexels API Key。")
    search_texts = [search_text] if isinstance(search_text, str) else search_text
    if not isinstance(search_texts, list) or any(not isinstance(text, str) or not text.strip() for text in search_texts):
        raise WorkflowInputError("图片搜索词必须是非空文本或文本列表。")
    results = []
    with new_httpx_client(is_async=False) as client:
        for text in search_texts:
            response = client.get("https://api.pexels.com/v1/search", params={"query": text, "per_page": count},
                                  headers={"Authorization": key}, timeout=30)
            response.raise_for_status()
            images = []
            for image in response.json()["photos"][:count]:
                url, photographer, photo_url = image["src"]["original"], image["photographer"], image["url"]
                if output_type == "text":
                    images.append(f"{url}\nPexels {photographer}: {photo_url}")
                else:
                    images.append(f"![{photographer}]({url})\nPexels {photographer}: [{photo_url}]({photo_url})")
            results.append(images)
    workflow.update_node_field_value(node_id, "output", results if isinstance(search_text, list) else results[0])
    return workflow.data


@task
@timer
def screenshot(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    monitor_number = workflow.get_node_field_value(node_id, "monitor_number")
    output_type = workflow.get_node_field_value(node_id, "output_type")

    result = get_screenshot(output_type=output_type, monitor_number=monitor_number)
    if output_type == "file_path":
        register_artifact(workflow.data, node_id, result)
    workflow.update_node_field_value(node_id, "output", result)
    return workflow.data


@task
@timer
def text_search(workflow_data: dict, node_id: str):
    settings = Settings()
    workflow = Workflow(workflow_data)
    search_text = workflow.get_node_field_value(node_id, "search_text")
    engine = workflow.get_node_field_value(node_id, "search_engine")
    count = workflow.get_node_field_value(node_id, "count", 10)
    combined = workflow.get_node_field_value(node_id, "combine_result_in_text", True)
    snippet_length = workflow.get_node_field_value(node_id, "max_snippet_length", 300)
    output_type = workflow.get_node_field_value(node_id, "output_type", "markdown")
    queries = [search_text] if isinstance(search_text, str) else search_text
    if engine not in {"deepseek", "jina.ai"}:
        raise WorkflowInputError("该搜索引擎已不受支持，请在文本搜索节点中重新选择 DeepSeek 或 Jina。")
    if not isinstance(queries, list) or any(not isinstance(query, str) or not query.strip() for query in queries):
        raise WorkflowInputError("搜索词必须是非空文本或文本列表。")
    if engine == "deepseek" and any(len(query) > 128 for query in queries):
        raise WorkflowInputError("DeepSeek 搜索词不能超过 128 个字符。")
    if isinstance(count, str) and count.strip().isdigit():
        count = int(count)
    if type(count) is not int or not 1 <= count <= 50:
        raise WorkflowInputError("搜索结果数量必须是 1 到 50 的整数。")
    if type(snippet_length) is not int or snippet_length < 0 or output_type not in {"text", "markdown"}:
        raise WorkflowInputError("请检查搜索节点的摘要长度与输出格式。")
    outputs = {"output_page_title": [], "output_page_url": [], "output_page_snippet": []}
    separator = "\n\n" if output_type == "markdown" else "\n"
    with new_httpx_client(is_async=False) as client:
        for query in queries:
            results = search_pages(client, settings, engine, query, count)
            titles, urls, snippets = [], [], []
            for result in results:
                title, url = result["title"], result["url"]
                titles.append(f"### {title}" if output_type == "markdown" else title)
                urls.append(f"[{url}]({url})" if output_type == "markdown" else url)
                snippets.append((result.get("content") or result.get("description") or "")[:snippet_length])
            for field, values in zip(outputs, (titles, urls, snippets)):
                outputs[field].append(separator.join(values) if combined else values)
    for field, values in outputs.items():
        workflow.update_node_field_value(node_id, field, values if isinstance(search_text, list) else values[0])
    return workflow.data


@task
@timer
def workflow_invoke(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    sleep_interval = 1

    if workflow.get_async_task(node_id) is None:
        workflow_id = workflow.get_node_field_value(node_id, "workflow_id")
        if workflow.workflow_id == workflow_id:
            raise Exception("Can't invoke self!")
        list_input = workflow.get_node_field_value(node_id, "list_input")
        fields = workflow.get_node_fields(node_id)

        # 每个batch相当于一次工作流调用的参数
        input_fields_batches: List[Dict[str, Dict[str, Any]]] = []
        output_fields_batches = {}
        for field in fields:
            if field in ("workflow_id", "list_input"):
                continue

            if workflow.get_node_field_value_by_key(node_id, field, "is_output"):
                output_fields_batches[field] = {
                    "node_id": workflow.get_node_field_value_by_key(node_id, field, "node"),
                    "output_field_key": workflow.get_node_field_value_by_key(node_id, field, "output_field_key"),
                    "values": [],
                }
                continue

            field_original_node_id = workflow.get_node_field_value_by_key(node_id, field, "nodeId")
            field_value = workflow.get_node_field_value(node_id, field)
            field_values = field_value if list_input else [field_value]
            if len(input_fields_batches) == 0:
                input_fields_batches = [dict() for _ in range(len(field_values))]
            for batch, field_value in zip(input_fields_batches, field_values):
                batch.setdefault(field_original_node_id, {})[field] = field_value

        record_ids = []
        workflow_model = WorkflowModel.get(WorkflowModel.wid == workflow_id)
        for input_fields in input_fields_batches:
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
                parent_rid=workflow.record_id,
            )
            record_ids.append(record_rid)

        workflow.add_async_task(
            node_id,
            {"record_ids": record_ids, "finished_record_ids": [], "output_fields_batches": output_fields_batches},
        )
        workflow_invoke.retry(workflow.data, node_id, retry_delay=1)
    else:
        async_task_data = workflow.get_async_task(node_id)
        if async_task_data is None:
            raise Exception("Async task not found!")
        record_ids = async_task_data["record_ids"]
        finished_record_ids = async_task_data["finished_record_ids"]
        output_fields_batches = async_task_data["output_fields_batches"]
        for record_id in record_ids:
            if record_id in finished_record_ids:
                continue
            record = WorkflowRunRecord.select().join(WorkflowModel).where(WorkflowRunRecord.rid == record_id).first()
            if record.status == "STOPPED":
                raise WorkflowStopped()
            if record.status == "PAUSED":
                raise WorkflowPaused(record.rid.hex)
            if record.status in ("RUNNING", "QUEUED", "STOPPING"):
                continue
            elif record.status != "FINISHED":
                raise WorkflowExecutionError(workflow_error_payload(record)["failures"])

            finished_record_ids.append(record_id)

            nodes = record.data["nodes"]
            for node in nodes:
                for output_field_data in output_fields_batches.values():
                    if node["id"] != output_field_data["node_id"]:
                        continue
                    output_field_data["values"].append(
                        node["data"]["template"][output_field_data["output_field_key"]]["value"]
                    )

        if len(finished_record_ids) != len(record_ids):
            mprint(f"Recheck in {sleep_interval} seconds")
            workflow.update_async_task(
                node_id,
                {
                    "record_ids": record_ids,
                    "finished_record_ids": finished_record_ids,
                    "output_fields_batches": output_fields_batches,
                },
            )
            workflow_invoke.retry(workflow.data, node_id, retry_delay=1)

    for output_field, output_field_data in output_fields_batches.items():
        # output_values = output_field_data["values"] if list_input else output_field_data["values"][0]
        output_values = (
            output_field_data["values"] if len(output_field_data["values"]) > 1 else output_field_data["values"][0]
        )
        workflow.update_node_field_value(node_id, output_field, output_values)

    return workflow.data
