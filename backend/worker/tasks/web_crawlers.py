# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-04-13 15:45:13
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-25 21:43:04
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import yt_dlp
from pathvalidate import sanitize_filename
from bilili.api.acg_video import get_acg_video_subtitle

from utilities.config import Settings
from utilities.workflow import Workflow
from utilities.general import mprint_with_name
from utilities.network import crawl_text_from_url, new_httpx_client
from worker.tasks import task, timer


mprint = mprint_with_name(name="Web Crawlers Tasks")

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
    http_client = new_httpx_client(is_async=False)
    resp = http_client.get(url, headers=headers)
    info = resp.json()
    cid = info["data"][part_number - 1]["cid"]

    return aid, cid


@task
@timer
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
    else:
        raise Exception("url is not a string or list")

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
@timer
def bilibili_crawler(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    url_or_bvid = workflow.get_node_field_value(node_id, "url_or_bvid")
    download_video = workflow.get_node_field_value(node_id, "download_video", False)
    output_type = workflow.get_node_field_value(node_id, "output_type")

    if isinstance(url_or_bvid, list):
        urls = url_or_bvid
    else:
        urls = [url_or_bvid]

    http_client = new_httpx_client(is_async=False)

    subtitles = []
    titles = []
    videos = []
    for url in urls:
        if "b23.tv" in url:
            resp = http_client.get(url, headers=headers, follow_redirects=True)
            url = f"{resp.url.scheme}://{resp.url.host}{resp.url.path}"
        elif len(url) < 10:
            # 猜测是 https://b23.tv/TPsdmV5 这样的格式被 AI 识别为 TPsdmV5 输入了
            resp = http_client.get(f"https://b23.tv/{url}", headers=headers, follow_redirects=True)
            url = f"{resp.url.scheme}://{resp.url.host}{resp.url.path}"

        if "bilibili.com" in url:
            if not url.startswith("http"):
                url = "https://" + url
            parsed_url = urlparse(url)
            path_components = parsed_url.path.split("/")
            bvid = path_components[2].split("?")[0]
            query_dict = parse_qs(parsed_url.query)
            part_number = int(query_dict.get("p", ["1"])[0])
        else:
            bvid = url
            part_number = 1

        aid, cid = get_aid_cid(bvid, part_number=part_number)
        resp = http_client.get(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", headers=headers)
        title = resp.json()["data"]["title"]
        subtitle_list = get_acg_video_subtitle(bvid=bvid, cid=cid)
        if len(subtitle_list) == 0:
            subtitle_data = [] if output_type == "list" else ""
        else:
            # TODO: 这里直接选择列表第一个作为字幕了，对于多语言字幕未来要考虑让用户选择语言？
            subtitle_data_list = subtitle_list[0]["lines"]
            subtitle_data_list = [item["content"] for item in subtitle_data_list]
            subtitle_data = "\n".join(subtitle_data_list) if output_type == "str" else subtitle_data_list

        if download_video:
            output_folder = Path(Settings().output_folder) / sanitize_filename(title)
            ydl_opts = {
                "outtmpl": str(output_folder) + "/%(title)s.%(ext)s",
                "merge_output_format": "mp4",
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            for path in output_folder.iterdir():
                if path.is_file() and path.suffix == ".mp4":
                    video = str(path.absolute())
                    break
            else:
                video = ""
        else:
            video = ""

        titles.append(title)
        subtitles.append(subtitle_data)
        videos.append(video)

    title = titles if isinstance(url_or_bvid, list) else titles[0]
    subtitle_data = subtitles if isinstance(url_or_bvid, list) else subtitles[0]
    video = videos if isinstance(url_or_bvid, list) else videos[0]

    workflow.update_node_field_value(node_id, "output_subtitle", subtitle_data)
    workflow.update_node_field_value(node_id, "output_title", title)
    workflow.update_node_field_value(node_id, "output_video", video)
    return workflow.data


@task
@timer
def youtube_crawler(
    workflow_data: dict,
    node_id: str,
):
    workflow = Workflow(workflow_data)
    url_or_video_id = workflow.get_node_field_value(node_id, "url_or_video_id")
    output_type = workflow.get_node_field_value(node_id, "output_type")
    get_comments = workflow.get_node_field_value(node_id, "get_comments", False)
    comments_type = workflow.get_node_field_value(node_id, "comments_type", "text_only")

    if isinstance(url_or_video_id, list):
        urls = url_or_video_id
    else:
        urls = [url_or_video_id]

    formatted_urls = []
    for url in urls:
        if "youtube.com" in url:
            if not url.startswith("http"):
                url = "https://" + url
        elif "youtu.be" in url:
            if not url.startswith("http"):
                url = "https://" + url
        else:
            url = "https://www.youtube.com/watch?v=" + url
        formatted_urls.append(url)

    http_client = new_httpx_client(is_async=False)

    text_results = []
    title_results = []
    comments_results = []
    for url in formatted_urls:
        ydl_opts = {"writeautomaticsub": True, "getcomments": get_comments}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                title_results.append("")
                text_results.append("")
                if get_comments:
                    comments_results.append([])
                continue
            title = info["title"]
            comments = info.get("comments", [])
            if comments_type == "text_only":
                comments = [comment["text"] for comment in comments]

        # TODO: 这里直接选择列表第一个作为字幕了，对于多语言字幕未来要考虑让用户选择语言？
        subtitle_url = None
        if len(info["subtitles"]) > 0:
            subtitle_key = list(info["subtitles"].keys())[0]
            subtitle_file_list = info["subtitles"][subtitle_key]
            for subtitle_file in subtitle_file_list:
                if subtitle_file["ext"] == "json3":
                    subtitle_url = subtitle_file["url"]
                    break
        elif len(info["automatic_captions"]) > 0:
            for caption_key in info["automatic_captions"]:
                if not caption_key.startswith("en"):
                    continue
                caption_file_list = info["automatic_captions"][caption_key]
                for caption_file in caption_file_list:
                    if caption_file["ext"] == "json3":
                        subtitle_url = caption_file["url"]
                        break
                break
        else:
            mprint.error("No subtitle found")
            title_results.append(title)
            text_results.append("")
            if get_comments:
                comments_results.append(comments)
            continue

        title_results.append(title)
        if get_comments:
            comments_results.append(comments)

        if subtitle_url is None:
            mprint.error("No subtitle found")
            text_results.append("")
            continue
        subtitle_resp = http_client.get(subtitle_url, headers=headers)
        subtitle_data_list = subtitle_resp.json()["events"]
        formated_subtitle = []
        for item in subtitle_data_list:
            if "segs" not in item:
                continue
            line = "".join([seg["utf8"] for seg in item["segs"]]).strip()
            if len(line) == 0:
                continue
            formated_subtitle.append(line)
        subtitle_data = "\n".join(formated_subtitle) if output_type == "str" else formated_subtitle

        text_results.append(subtitle_data)

    title_value = title_results if isinstance(url_or_video_id, list) else title_results[0]
    workflow.update_node_field_value(node_id, "output_title", title_value)
    text_value = text_results if isinstance(url_or_video_id, list) else text_results[0]
    workflow.update_node_field_value(node_id, "output_subtitle", text_value)
    if get_comments:
        comments_value = comments_results if isinstance(url_or_video_id, list) else comments_results[0]
        workflow.update_node_field_value(node_id, "output_comments", comments_value)
    return workflow.data
