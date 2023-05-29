# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-29 15:30:27
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-29 20:35:06
import uuid
import base64
from pathlib import Path

import httpx

from utilities.workflow import Workflow
from utilities.web_crawler import proxies
from utilities.static_file_server import StaticFileServer
from worker.tasks import task


SAMPLER_MAP = {
    "ddim": "DDIM",
    "plms": "PLMS",
    "k_euler": "Euler",
    "k_euler_ancestral": "Euler a",
    "k_heun": "Heun",
    "k_dpm_2": "DPM2",
    "k_dpm_2_ancestral": "DPM2 a",
    "k_dpmpp_2s_ancestral": "DPM++ 2S a",
    "k_dpmpp_2m": "DPM++ 2M",
    "k_dpmpp_sde": "DPM++ SDE",
}


@task
def stable_diffusion(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    input_prompt = workflow.get_node_field_value(node_id, "prompt")
    input_negative_prompt = workflow.get_node_field_value(node_id, "negative_prompt")
    model = workflow.get_node_field_value(node_id, "model")
    cfg_scale = workflow.get_node_field_value(node_id, "cfg_scale")
    sampler = SAMPLER_MAP[workflow.get_node_field_value(node_id, "sampler")]
    width = workflow.get_node_field_value(node_id, "width")
    height = workflow.get_node_field_value(node_id, "height")
    output_type = workflow.get_node_field_value(node_id, "output_type")

    image_folder = Path("./data") / "static" / "images"
    stable_diffusion_base_url = workflow.setting.get("stable_diffusion_base_url")

    url = f"{stable_diffusion_base_url}/sdapi/v1/txt2img"

    if isinstance(input_prompt, str):
        prompts = [input_prompt]
    elif isinstance(input_prompt, list):
        prompts = input_prompt

    if isinstance(input_negative_prompt, str):
        negative_prompts = [input_negative_prompt]
    elif isinstance(input_negative_prompt, list):
        negative_prompts = input_negative_prompt

    if len(prompts) < len(negative_prompts) and len(prompts) == 1:
        prompts = prompts * len(negative_prompts)
    elif len(prompts) > len(negative_prompts) and len(negative_prompts) == 1:
        negative_prompts = negative_prompts * len(prompts)

    results = []
    for index, prompt in enumerate(prompts):
        data = {
            "prompt": prompt,
            "negative_prompt": negative_prompts[index],
            "sampler_index": sampler,
            "steps": 30,
            "width": width,
            "height": height,
            "cfg_scale": cfg_scale,
        }
        response = httpx.post(url, json=data, proxies=proxies, timeout=None)
        image_base64 = response.json()["images"][0]
        image_name = f"{uuid.uuid4().hex}.jpg"
        local_file = image_folder / image_name
        with open(local_file, "wb") as image_file:
            image_file.write(base64.b64decode(image_base64))
        results.append(StaticFileServer.get_file_url(f"images/{image_name}"))

    output = results[0] if isinstance(input_prompt, str) else results
    if output_type == "only_link":
        workflow.update_node_field_value(node_id, "output", output)
    elif output_type == "markdown":
        workflow.update_node_field_value(node_id, "output", f"![{output}]({output})")
    elif output_type == "html":
        workflow.update_node_field_value(node_id, "output", f'<img src="{output}"/>')

    workflow.set_node_status(node_id, 200)
    return workflow.data
