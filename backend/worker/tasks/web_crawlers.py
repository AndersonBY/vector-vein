# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-13 15:45:13
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-23 11:32:25
from urllib.parse import urlparse, parse_qs

import httpx

from utilities.workflow import Workflow
from utilities.web_crawler import crawl_text_from_url
from worker.tasks import task


headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
}


def get_aid_cid(bvid, part_number):
    table = "fZodR9XQDSUm21yCkr6zBqiveYah8bt4xsWpHnJE7jL5VG3guMTKNPAwcF"
    tr = {}
    for i in range(58):
        tr[table[i]] = i
    s = [11, 10, 3, 8, 4, 6]
    xor = 177451812
    add = 8728348608

    if "BV" in bvid:
        r = 0
        for i in range(6):
            r += tr[bvid[s[i]]] * 58**i
        aid = (r - add) ^ xor
    else:
        aid = bvid

    url = f"https://api.bilibili.com/x/player/pagelist?bvid={bvid}&jsonp=jsonp"
    resp = httpx.get(url, headers=headers)
    info = resp.json()
    cid = info["data"][part_number - 1]["cid"]

    return aid, cid


@task
def text_crawler(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    input_url = workflow.get_node_field_value(node_id, "url")
    if input_url is None or (isinstance(input_url, str) and input_url == ""):
        raise Exception("url is empty")
    if isinstance(input_url, str):
        urls = [input_url]
    elif isinstance(input_url, list):
        urls = input_url

    output_type = workflow.get_node_field_value(node_id, "output_type")
    output_data = {
        "text": [],
        "title": [],
    }
    for url in urls:
        result = crawl_text_from_url(url)
        if output_type == "text":
            output_data["text"].append(result["text"])
            output_data["title"].append(result["title"])
        elif output_type == "json":
            output_data["text"].append(result)

    if output_type == "text":
        text_value = output_data["text"] if isinstance(input_url, list) else output_data["text"][0]
        title_value = output_data["title"] if isinstance(input_url, list) else output_data["title"][0]
        workflow.update_node_field_value(node_id, "output_text", text_value)
        workflow.update_node_field_value(node_id, "output_title", title_value)
    elif output_type == "json":
        text_value = output_data["text"] if isinstance(input_url, list) else output_data["text"][0]
        workflow.update_node_field_value(node_id, "output_text", text_value)
    return workflow.data


@task
def bilibili_crawler(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    url_or_bvid = workflow.get_node_field_value(node_id, "url_or_bvid")
    output_type = workflow.get_node_field_value(node_id, "output_type")
    if "bilibili.com" in url_or_bvid:
        if not url_or_bvid.startswith("http"):
            url_or_bvid = "https://" + url_or_bvid
        parsed_url = urlparse(url_or_bvid)
        path_components = parsed_url.path.split("/")
        bvid = path_components[2].split("?")[0]
        query_dict = parse_qs(parsed_url.query)
        part_number = int(query_dict.get("p", ["1"])[0])
    else:
        bvid = url_or_bvid
        part_number = 1

    aid, cid = get_aid_cid(bvid, part_number=part_number)
    resp = httpx.get(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", headers=headers)
    title = resp.json()["data"]["title"]

    resp = httpx.get(f"https://api.bilibili.com/x/player/wbi/v2?aid={aid}&cid={cid}", headers=headers)
    subtitle_list = resp.json()["data"]["subtitle"]["subtitles"]
    if len(subtitle_list) == 0:
        subtitle_data = [] if output_type == "list" else ""
    else:
        # TODO: 这里直接选择列表第一个作为字幕了，对于多语言字幕未来要考虑让用户选择语言？
        subtitle_url = subtitle_list[0]["subtitle_url"]
        if subtitle_url.startswith("//"):
            subtitle_url = "https:" + subtitle_url
        subtitle_resp = httpx.get(subtitle_url, headers=headers)
        subtitle_data_list = subtitle_resp.json()["body"]
        subtitle_data_list = [item["content"] for item in subtitle_data_list]
        subtitle_data = "\n".join(subtitle_data_list) if output_type == "str" else subtitle_data_list

    workflow.update_node_field_value(node_id, "output_subtitle", subtitle_data)
    workflow.update_node_field_value(node_id, "output_title", title)
    return workflow.data
