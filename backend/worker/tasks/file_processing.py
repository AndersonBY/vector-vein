# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 20:58:33
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-28 14:29:34
import html
import json
import uuid
from pathlib import Path

from utilities.config import Settings
from utilities.workflow import Workflow
from utilities.file_processing import get_files_contents, remove_markdown_image, remove_url_and_email
from worker.tasks import task, timer


@task
@timer
def file_loader(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    files = workflow.get_node_field_value(node_id, "files")
    need_remove_image: bool = workflow.get_node_field_value(node_id, "remove_image", True)
    need_remove_url_and_email: bool = workflow.get_node_field_value(node_id, "remove_url_and_email", True)

    if isinstance(files, str):
        files = [files]

    results = get_files_contents(files)
    output = []
    for result in results:
        if need_remove_image:
            result = remove_markdown_image(result, 0)
        if need_remove_url_and_email:
            result = remove_url_and_email(result)
        output.append(result)

    if len(files) == 1:
        output = output[0]

    workflow.update_node_field_value(node_id, "output", output)
    return workflow.data


@task
@timer
def file_upload(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    files = workflow.get_node_field_value(node_id, "files")
    if isinstance(files, str):
        files = [files]
    if len(files) == 1:
        workflow.update_node_field_value(node_id, "output", files[0])
    else:
        workflow.update_node_field_value(node_id, "output", files)
    return workflow.data


@task
@timer
def document_convert(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    files = workflow.get_node_field_value(node_id, "files", [])
    output_format = str(workflow.get_node_field_value(node_id, "output_format", "txt")).lower().lstrip(".")
    if not files:
        workflow.update_node_field_value(node_id, "output", "")
        return workflow.data

    if isinstance(files, str):
        files = [files]

    output_dir = Path(Settings().output_folder) / "document_convert"
    output_dir.mkdir(parents=True, exist_ok=True)

    contents = get_files_contents(files)
    output_files = []
    for file_path, content in zip(files, contents):
        source_path = Path(file_path)
        filename = f"{source_path.stem}-{uuid.uuid4().hex[:8]}.{output_format}"
        target_path = output_dir / filename

        if output_format == "json":
            target_path.write_text(
                json.dumps(
                    {
                        "source": str(source_path),
                        "output_format": output_format,
                        "content": content,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        elif output_format == "html":
            target_path.write_text(
                "<html><body><pre>"
                + html.escape(content)
                + "</pre></body></html>",
                encoding="utf-8",
            )
        else:
            target_path.write_text(content, encoding="utf-8")

        output_files.append(target_path.as_posix())

    workflow.update_node_field_value(node_id, "output", output_files[0] if len(output_files) == 1 else output_files)
    return workflow.data
