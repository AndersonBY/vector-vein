# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-16 18:54:18
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-07-07 17:50:34
import re
import json
import time
import base64
import urllib.request
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

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


def decrypt_aes_ecb_base64(ciphertext_base64, key):
    cipher = AES.new(key, AES.MODE_ECB)
    ciphertext = base64.b64decode(ciphertext_base64)
    return unpad(cipher.decrypt(ciphertext), AES.block_size).decode("utf-8")


def clean_markdown(text: str):
    content = "\n\n".join([s.strip() for s in text.split("\n") if s.strip()])
    content = content.replace("![]()", "").replace("*\n", "")
    content = "\n\n".join([s.strip() for s in content.split("\n") if s.strip()])
    return content


def crawl_text_from_url(url: str):
    if not url.startswith("http"):
        url = f"http://{url}"

    try_times = 0
    crawl_success = False
    while try_times < 5:
        try:
            response = httpx.get(url, headers=headers, proxies=proxies, follow_redirects=True)
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
        content = clean_markdown(markdownify(content))
        result = {
            "title": soup.select_one("#activity-name").text.strip(),
            "text": content,
            "url": url,
        }
    elif url.startswith("https://zhuanlan.zhihu.com"):
        soup = BeautifulSoup(response.text, "lxml")
        content = str(soup.select_one(".Post-RichText"))
        content = clean_markdown(markdownify(content))
        result = {
            "title": soup.select_one(".Post-Title").text.strip(),
            "text": content,
            "url": url,
        }
    elif url.startswith("https://www.zhihu.com/question/"):
        soup = BeautifulSoup(response.text, "lxml")
        content = soup.select_one(".RichContent-inner")
        for style in content.select("style"):
            style.decompose()
        content = str(content)
        content = clean_markdown(markdownify(content))
        result = {
            "title": soup.select_one(".QuestionHeader-title").text.strip(),
            "text": content,
            "url": url,
        }
    elif "substack.com" in url:
        soup = BeautifulSoup(response.text, "lxml")
        content = str(soup.select_one(".available-content"))
        content = clean_markdown(markdownify(content))
        result = {
            "title": soup.select_one(".post-title").text.strip(),
            "text": content,
            "url": url,
        }
    elif "36kr.com" in url:
        script_content = re.findall(r"<script>window.initialState=(.*?)</script>", response.text)[0]
        encrypted_data = json.loads(script_content)
        if encrypted_data["isEncrypt"]:
            key = "efabccee-b754-4c"  # 不确定这个key是不是固定的
            decrypted_data = decrypt_aes_ecb_base64(encrypted_data["state"], key.encode("utf-8"))
        else:
            decrypted_data = encrypted_data["state"]
        decrypted_data_json = json.loads(decrypted_data)
        html_content = decrypted_data_json["articleDetail"]["articleDetailData"]["data"]["widgetContent"]
        content = clean_markdown(markdownify(html_content))
        result = {
            "title": decrypted_data_json["articleDetail"]["articleDetailData"]["data"]["widgetTitle"].strip(),
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
