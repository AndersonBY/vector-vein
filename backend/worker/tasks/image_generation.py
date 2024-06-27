# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-29 15:30:27
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-25 17:27:32
import uuid
import base64

import httpx

from worker.tasks import task, timer
from utilities.config import Settings
from utilities.network import proxies
from utilities.workflow import Workflow
from utilities.file_processing import static_file_server
from utilities.ai_utils import get_openai_client_and_model


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
@timer
def stable_diffusion(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    provider = workflow.get_node_field_value(node_id, "provider", "self-host")
    input_prompt = workflow.get_node_field_value(node_id, "prompt")
    input_negative_prompt = workflow.get_node_field_value(node_id, "negative_prompt")
    model = workflow.get_node_field_value(node_id, "model")
    cfg_scale = workflow.get_node_field_value(node_id, "cfg_scale")
    sampler = workflow.get_node_field_value(node_id, "sampler")
    width = workflow.get_node_field_value(node_id, "width")
    height = workflow.get_node_field_value(node_id, "height")
    size = workflow.get_node_field_value(node_id, "size")
    aspect_ratio = workflow.get_node_field_value(node_id, "aspect_ratio")
    output_type = workflow.get_node_field_value(node_id, "output_type")

    if width is None or height is None:
        size = size.replace(" ", "")
        width, height = size.split("x")
        width = int(width)
        height = int(height)

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
    image_folder = static_file_server.static_folder_path / "images"
    settings = Settings()
    STABILITY_KEY = settings.stability_key
    for index, prompt in enumerate(prompts):
        if provider == "self-host":
            stable_diffusion_base_url = settings.stable_diffusion_base_url.rstrip("/")
            url = f"{stable_diffusion_base_url}/sdapi/v1/txt2img"
            data = {
                "prompt": prompt,
                "negative_prompt": negative_prompts[index],
                "sampler_index": SAMPLER_MAP[sampler],
                "steps": 30,
                "width": width,
                "height": height,
                "cfg_scale": cfg_scale,
            }
            response = httpx.post(url, json=data, proxies=proxies(), timeout=None)
            image_base64 = response.json()["images"][0]
            image_name = f"{uuid.uuid4().hex}.jpg"
            local_file = image_folder / image_name
            with open(local_file, "wb") as image_file:
                image_file.write(base64.b64decode(image_base64))
        elif provider == "stable-diffusion-official":
            if model == "sd-core":
                url = "https://api.stability.ai/v2beta/stable-image/generate/core"
                model_params = {}
            elif model.startswith("sd3"):
                url = "https://api.stability.ai/v2beta/stable-image/generate/sd3"
                model_params = {"model": model}
            elif model == "sd-ultra":
                url = "https://api.stability.ai/v2beta/stable-image/generate/ultra"
                model_params = {}

            if model == "sd3-large-turbo":
                negative_prompt_params = {}
            else:
                negative_prompt_params = {"negative_prompt": negative_prompts[index]}

            response = httpx.post(
                url,
                headers={"authorization": f"Bearer {STABILITY_KEY}", "accept": "image/*"},
                files={"none": ""},
                data={
                    "prompt": prompt,
                    **negative_prompt_params,
                    "aspect_ratio": aspect_ratio,
                    "output_format": "png",
                    **model_params,
                },
                timeout=180,
            )
            image_name = f"{uuid.uuid4().hex}.png"
            local_file = image_folder / image_name
            with open(local_file, "wb") as file:
                file.write(response.content)

        image_url = static_file_server.get_file_url(f"images/{image_name}")
        if output_type == "only_link":
            results.append(image_url)
        elif output_type == "markdown":
            results.append(f"![{image_url}]({image_url})")
        elif output_type == "html":
            results.append(f'<img src="{image_url}"/>')

    output = results[0] if isinstance(input_prompt, str) and isinstance(input_negative_prompt, str) else results
    workflow.update_node_field_value(node_id, "output", output)
    return workflow.data


@task
@timer
def dall_e(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    input_prompt = workflow.get_node_field_value(node_id, "prompt")
    model = workflow.get_node_field_value(node_id, "model")
    size = workflow.get_node_field_value(node_id, "size")
    quality = workflow.get_node_field_value(node_id, "quality")
    style = workflow.get_node_field_value(node_id, "style")
    output_type = workflow.get_node_field_value(node_id, "output_type")

    if isinstance(input_prompt, str):
        prompts = [input_prompt]
    elif isinstance(input_prompt, list):
        prompts = input_prompt

    client, model_id = get_openai_client_and_model(is_async=False, model_id=model)
    image_folder = static_file_server.static_folder_path / "images"
    results = []
    for prompt in prompts:
        response = client.images.generate(
            model=model_id,
            prompt=prompt,
            n=1,
            response_format="b64_json",
            size=size,
            quality=quality,
            style=style,
        )

        image_base64 = response.data[0].b64_json
        image_bytes = base64.decodebytes(bytes(image_base64, "utf-8"))
        image_name = f"{uuid.uuid4().hex}.png"
        local_file = image_folder / image_name
        with open(local_file, "wb") as image_file:
            image_file.write(image_bytes)

        image_url = static_file_server.get_file_url(f"images/{image_name}")

        if output_type == "only_link":
            results.append(image_url)
        elif output_type == "markdown":
            results.append(f"![{image_url}]({image_url})")
        elif output_type == "html":
            results.append(f'<img src="{image_url}"/>')

    output = results[0] if isinstance(input_prompt, str) else results
    workflow.update_node_field_value(node_id, "output", output)
    return workflow.data
