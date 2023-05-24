# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-26 20:58:33
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-25 02:35:54
import re
import json

import httpx
from bs4 import BeautifulSoup

from utilities.workflow import Workflow
from utilities.web_crawler import proxies, headers
from worker.tasks import task


@task
def programming_function(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    code = workflow.get_node_field_value(node_id, "code")
    language = workflow.get_node_field_value(node_id, "language")
    fields = workflow.get_node_fields(node_id)
    parameters = {}
    for field in fields:
        if field in ("code", "language", "output"):
            continue
        parameter = workflow.get_node_field_value(node_id, field)
        parameter_type = workflow.get_node(node_id).get_field(field).get("type")
        if parameter_type == "str":
            parameters[field] = str(parameter)
        elif parameter_type == "int":
            parameters[field] = int(parameter)
        elif parameter_type == "float":
            parameters[field] = float(parameter)
        elif parameter_type == "bool":
            parameters[field] = bool(parameter)
        else:
            parameters[field] = parameter

    pattern = r"```.*?\n(.*?)\n```"
    code_block_search = re.search(pattern, code, re.DOTALL)

    if code_block_search:
        pure_code = code_block_search.group(1)
    else:
        pure_code = code

    if language == "python":
        exec(pure_code, globals())
        result = main(**parameters)
    else:
        result = "Not implemented"
    workflow.update_node_field_value(node_id, "output", result)
    return workflow.data


@task
def image_search(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    search_text = workflow.get_node_field_value(node_id, "search_text")
    search_engine = workflow.get_node_field_value(node_id, "search_engine")
    count = workflow.get_node_field_value(node_id, "count")
    output_type = workflow.get_node_field_value(node_id, "output_type")

    if search_engine == "bing":
        params = {
            "q": search_text,
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
        response = httpx.get("https://cn.bing.com/images/async", params=params, headers=headers, proxies=proxies)
        soup = BeautifulSoup(response.text, "lxml")
        images = []
        images_elements = soup.select(".imgpt>a")
        for image_element in images_elements[:count]:
            image_data = json.loads(image_element["m"])
            title = image_data["t"]
            url = image_data["murl"]
            if output_type == "text":
                images.append(url)
            elif output_type == "markdown":
                images.append(f"![{title}]({url})")

    workflow.update_node_field_value(node_id, "output", images)
    return workflow.data
