# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-16 18:54:18
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-05-18 22:25:34
import re
import time
import urllib.request

import httpx
from bs4 import BeautifulSoup
from readability import Document
from markdownify import markdownify

from utilities.print_utils import mprint, mprint_error


headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
}

http_proxy_host_re = re.compile(r"http.*://(.*?)$")
system_proxies = urllib.request.getproxies()

proxies = {}
proxies_for_requests = {}

for protocol, proxy in system_proxies.items():
    http_proxy_host = http_proxy_host_re.findall(proxy)
    if not http_proxy_host:
        continue
    proxy_url = f"http://{http_proxy_host[0]}"
    proxies[f"{protocol}://"] = proxies_for_requests[protocol] = proxy_url

mprint(f"Proxies: {proxies}")
mprint(f"Proxies for requests: {proxies_for_requests}")


def crawl_text_from_url(url: str):
    try_times = 0
    crawl_success = False
    while try_times < 5:
        try:
            response = httpx.get(url, headers=headers, proxies=proxies)
            crawl_success = True
            break
        except Exception as e:
            mprint_error(e)
            try_times += 1
            time.sleep(1)

    if not crawl_success:
        raise Exception("Crawl failed")

    if "https://mp.weixin.qq.com/" in url:
        soup = BeautifulSoup(response.content, "lxml")
        content = str(soup.select_one("#js_content"))
        content = markdownify(content)
        content = "\n\n".join([s.strip() for s in content.split("\n") if s.strip()])
        content = content.replace("![]()", "").replace("*\n", "")
        content = "\n\n".join([s.strip() for s in content.split("\n") if s.strip()])
        result = {
            "title": soup.select_one("#activity-name").text.strip(),
            "text": content,
            "url": url,
        }
    else:
        doc = Document(response.content)
        result = {
            "title": doc.title(),
            "text": markdownify(doc.summary()),
            "url": url,
        }

    return result
