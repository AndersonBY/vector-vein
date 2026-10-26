# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 20:58:33
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-25 21:42:59
import re
import io
import builtins
import uuid
import json
import shutil
import traceback
from pathlib import Path
from urllib.parse import quote
from typing import Any, Callable, Dict, List, cast
from threading import RLock

from bs4 import BeautifulSoup

from api.utils import run_workflow_common
from models.workflow_models import WorkflowRunRecord, Workflow as WorkflowModel
from utilities.config import Settings
from utilities.workflow import Workflow
from utilities.general import Retry, mprint_with_name
from utilities.media_processing import get_screenshot
from utilities.network import headers, new_httpx_client
from worker.tasks import task, timer


mprint = mprint_with_name(name="Tools Tasks")

# ponytail: serialize legacy working-directory file collection; use isolated workers if throughput matters.
_PYTHON_FILE_LOCK = RLock()

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
            except Exception:
                output_batch.append(None)
                errors.append(traceback.format_exc())
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
                files.append(str(destination))
            files_batch.append(files)
    for field, values in (("output", output_batch), ("files", files_batch), ("error_msg", errors), ("console_msg", consoles)):
        workflow.update_node_field_value(node_id, field, values if list_input else values[0])
    if any(errors) and workflow.get_node_field_value(node_id, "continue_on_error", False) is not True:
        indexes = [index for index, error in enumerate(errors) if error]
        raise RuntimeError(f"Python node failed at item indexes: {indexes}")
    return workflow.data


@task
@timer
def image_search(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    search_text = workflow.get_node_field_value(node_id, "search_text")
    search_engine = workflow.get_node_field_value(node_id, "search_engine")
    count = workflow.get_node_field_value(node_id, "count")
    output_type = workflow.get_node_field_value(node_id, "output_type")

    http_client = new_httpx_client(is_async=False)

    results = []
    if search_engine == "bing":
        if isinstance(search_text, list):
            search_texts = search_text
        else:
            search_texts = [search_text]

        for text in search_texts:
            params = {
                "q": text,
                "first": "-",
                "count": 30,
                "cw": 1920,
                "ch": 929,
                "relp": 59,
                "tsc": "ImageHoverTitle",
                "datsrc": "I",
                "layout": "RowBased_Landscape",
                "mmasync": 1,
            }
            images = []
            response = http_client.get(
                "https://cn.bing.com/images/async",
                params=params,
                headers=headers,
            )
            soup = BeautifulSoup(response.text, "lxml")
            images_elements = soup.select(".imgpt>a")
            for image_element in images_elements[:count]:
                m = image_element["m"]
                if isinstance(m, list):
                    m = m[0]
                image_data = json.loads(m)
                title = image_data["t"]
                url = image_data["murl"]
                if output_type == "text":
                    images.append(url)
                elif output_type == "markdown":
                    images.append(f"![{title}]({url})")
            results.append(images)
    elif search_engine == "pexels":
        pexels_api_key = Settings().pexels_api_key
        if isinstance(search_text, list):
            search_texts = search_text
        else:
            search_texts = [search_text]
        for text in search_texts:
            params = {
                "query": text,
                "per_page": 30,
            }
            images = []
            response = http_client.get(
                "https://api.pexels.com/v1/search",
                params=params,
                headers={"Authorization": pexels_api_key},
            )
            data = response.json()
            for image_data in data["photos"][:count]:
                title = image_data["photographer"]
                url = image_data["src"]["original"]
                photographer = image_data["photographer"]
                pexels_photo_url = image_data["url"]
                if output_type == "text":
                    images.append(f"{url}\nPexels {photographer}: {pexels_photo_url}")
                elif output_type == "markdown":
                    images.append(
                        f"![{title}]({url})\nPexels {photographer}: [{pexels_photo_url}]({pexels_photo_url})"
                    )
            results.append(images)

    output = results if isinstance(search_text, list) else results[0]
    workflow.update_node_field_value(node_id, "output", output)
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

    workflow.update_node_field_value(
        node_id, "output", get_screenshot(output_type=output_type, monitor_number=monitor_number)
    )
    return workflow.data


@task
@timer
def text_search(
    workflow_data: dict,
    node_id: str,
):
    http_client = new_httpx_client(is_async=False)

    def format_output(text: str, text_type: str, output_type: str):
        if output_type == "text":
            return text
        if text_type == "name" or text_type == "title":
            return f"### {text}"
        elif text_type == "url":
            return f"[{text}]({text})"
        elif text_type == "snippet" or text_type == "content":
            return text

    def search_with_jinaai(query: str, max_results: int = 5, try_times: int = 0) -> list:
        if try_times > 5:
            return []

        headers = {"Accept": "application/json"}
        if try_times > 2:
            headers["Authorization"] = f"Bearer {settings.get('web_search.jinaai.api_key')}"

        try:
            response = http_client.get(
                f"https://s.jina.ai/{quote(query)}",
                headers=headers,
                timeout=30,
            )
            result = response.json()

            if result["code"] == 200:
                return result["data"]
            else:
                return search_with_jinaai(query, max_results, try_times + 1)
        except Exception as e:
            mprint.error(e)
            return search_with_jinaai(query, max_results, try_times + 1)

    def format_text_search_results(
        results: list, combine_result_in_text: bool, output_type: str, max_snippet_length: int
    ):
        split_str = "\n\n" if output_type == "markdown" else "\n"
        output_title, output_url, output_snippet = [], [], []

        for result in results:
            title = format_output(result["title"], "title", output_type)
            url = format_output(result["url"], "url", output_type)
            snippet = format_output(
                result.get("content", result.get("description", ""))[:max_snippet_length], "content", output_type
            )

            output_title.append(title)
            output_url.append(url)
            output_snippet.append(snippet)

        if combine_result_in_text:
            return {
                "title": split_str.join(output_title),
                "url": split_str.join(output_url),
                "snippet": split_str.join(output_snippet),
            }
        return {
            "title": output_title,
            "url": output_url,
            "snippet": output_snippet,
        }

    settings = Settings()
    workflow = Workflow(workflow_data)
    search_text = workflow.get_node_field_value(node_id, "search_text")
    search_engine = workflow.get_node_field_value(node_id, "search_engine")
    count = workflow.get_node_field_value(node_id, "count")
    combine_result_in_text = workflow.get_node_field_value(node_id, "combine_result_in_text")
    max_snippet_length = workflow.get_node_field_value(node_id, "max_snippet_length", 300)
    output_type = workflow.get_node_field_value(node_id, "output_type")

    search_texts = [search_text] if isinstance(search_text, str) else search_text

    results = {
        "output_page_title": [],
        "output_page_url": [],
        "output_page_snippet": [],
    }

    def handle_bing_results(search_results):
        split_str = "\n\n" if output_type == "markdown" else "\n"
        titles, urls, snippets = [], [], []

        for web_page in search_results["webPages"]["value"]:
            titles.append(format_output(web_page["name"], "name", output_type))
            urls.append(format_output(web_page["url"], "url", output_type))
            snippets.append(format_output(web_page["snippet"][:max_snippet_length], "snippet", output_type))

        if combine_result_in_text:
            results["output_page_title"].append(split_str.join(titles))
            results["output_page_url"].append(split_str.join(urls))
            results["output_page_snippet"].append(split_str.join(snippets))
        else:
            results["output_page_title"].append(titles)
            results["output_page_url"].append(urls)
            results["output_page_snippet"].append(snippets)

    if search_engine == "bing":
        search_url = settings.get("web_search.bing.endpoint")
        headers = {"Ocp-Apim-Subscription-Key": settings.get("web_search.bing.ocp_apim_subscription_key")}
        for text in search_texts:
            params = {"q": text, "count": count}
            request_success, response = (
                Retry(http_client.get)
                .args(
                    url=search_url,
                    headers=headers,
                    params=params,
                    timeout=20,
                )
                .retry_times(3)
                .sleep_time(10)
                .run()
            )
            if not request_success or response is None:
                continue

            search_results = response.json()
            handle_bing_results(search_results)

    elif search_engine == "jina.ai":
        for text in search_texts:
            search_results = search_with_jinaai(text, max_results=count)
            output = format_text_search_results(
                search_results, combine_result_in_text, output_type, max_snippet_length
            )
            results["output_page_title"].append(output["title"])
            results["output_page_url"].append(output["url"])
            results["output_page_snippet"].append(output["snippet"])

    if isinstance(search_text, list):
        workflow.update_node_field_value(node_id, "output_page_title", results["output_page_title"])
        workflow.update_node_field_value(node_id, "output_page_url", results["output_page_url"])
        workflow.update_node_field_value(node_id, "output_page_snippet", results["output_page_snippet"])
    else:
        workflow.update_node_field_value(node_id, "output_page_title", results["output_page_title"][0])
        workflow.update_node_field_value(node_id, "output_page_url", results["output_page_url"][0])
        workflow.update_node_field_value(node_id, "output_page_snippet", results["output_page_snippet"][0])

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
            if record.status in ("RUNNING", "QUEUED"):
                continue
            elif record.status != "FINISHED":
                raise Exception("Run workflow failed!")

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
