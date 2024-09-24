# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-05-16 18:54:18
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-15 18:44:15
import re
import json
import time
import base64
import urllib.request
from Crypto.Cipher import AES
from typing import overload, Literal
from Crypto.Util.Padding import unpad

import httpx
from bs4 import BeautifulSoup
from readability import Document
from markdownify import MarkdownConverter, chomp

from utilities.general import mprint
from utilities.config import Settings


headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
}

http_proxy_host_re = re.compile(r"http.*://(.*?)$")


def proxies():
    settings = Settings()
    if not settings.get("use_system_proxy", True):
        return {}
    else:
        system_proxies = urllib.request.getproxies()
        proxies = {}
        for protocol, proxy in system_proxies.items():
            http_proxy_host = http_proxy_host_re.findall(proxy)
            if not http_proxy_host:
                continue
            proxy_url = f"http://{http_proxy_host[0]}"
            proxies[f"{protocol}://"] = proxy_url
        return proxies


def proxies_for_requests():
    settings = Settings()
    if not settings.get("use_system_proxy", True):
        return {}
    else:
        system_proxies = urllib.request.getproxies()
        proxies_for_requests = {}
        for protocol, proxy in system_proxies.items():
            http_proxy_host = http_proxy_host_re.findall(proxy)
            if not http_proxy_host:
                continue
            proxy_url = f"http://{http_proxy_host[0]}"
            proxies_for_requests[protocol] = proxy_url
        return proxies_for_requests


@overload
def new_httpx_client(is_async: Literal[False] = False) -> httpx.Client: ...


@overload
def new_httpx_client(is_async: Literal[True] = True) -> httpx.AsyncClient: ...


def new_httpx_client(is_async: bool = False) -> httpx.Client | httpx.AsyncClient:
    settings = Settings()
    ssl_verification = not settings.get("skip_ssl_verification", False)
    if is_async:
        return httpx.AsyncClient(proxies=proxies(), verify=ssl_verification)
    else:
        return httpx.Client(proxies=proxies(), verify=ssl_verification)


def decrypt_aes_ecb_base64(ciphertext_base64, key):
    cipher = AES.new(key, AES.MODE_ECB)
    ciphertext = base64.b64decode(ciphertext_base64)
    return unpad(cipher.decrypt(ciphertext), AES.block_size).decode("utf-8")


class CustomMarkdownConverter(MarkdownConverter):
    def convert_b(self, el, text, convert_as_inline):
        return self.custom_bold_conversion(el, text, convert_as_inline)

    convert_strong = convert_b

    def custom_bold_conversion(self, el, text, convert_as_inline):
        markup = 2 * self.options["strong_em_symbol"]
        prefix, suffix, text = chomp(text)
        if not text:
            return ""
        return "%s%s%s%s%s " % (prefix, markup, text, markup, suffix)


def markdownify(html, **options):
    return CustomMarkdownConverter(**options).convert(html)


def clean_markdown(text: str):
    content = "\n\n".join([s.strip() for s in text.split("\n") if s.strip()])
    content = content.replace("![]()", "").replace("*\n", "")
    content = "\n\n".join([s.strip() for s in content.split("\n") if s.strip()])
    return content


def crawl_text_from_url(url: str):
    if not url.startswith("http"):
        url = f"http://{url}"

    http_client = new_httpx_client(is_async=False)

    try_times = 0
    crawl_success = False
    response = None
    while try_times < 5:
        try:
            response = http_client.get(url, headers=headers, follow_redirects=True)
            crawl_success = True
            break
        except Exception as e:
            mprint.error(e)
            try_times += 1
            time.sleep(1)

    if not crawl_success:
        raise Exception("Crawl failed")

    if response is None:
        raise Exception("Response is None")

    if "https://mp.weixin.qq.com/" in url:
        soup = BeautifulSoup(response.content, "lxml")
        content = str(soup.select_one("#js_content"))
        content = clean_markdown(markdownify(content))
        title_element = soup.select_one("#activity-name")
        title = title_element.text.strip() if title_element else ""
        result = {"title": title, "text": content, "url": url}
    elif url.startswith("https://zhuanlan.zhihu.com"):
        soup = BeautifulSoup(response.text, "lxml")
        content = str(soup.select_one(".Post-RichText"))
        content = clean_markdown(markdownify(content))
        title_element = soup.select_one(".Post-Title")
        title = title_element.text.strip() if title_element else ""
        result = {"title": title, "text": content, "url": url}
    elif url.startswith("https://www.zhihu.com/question/"):
        soup = BeautifulSoup(response.text, "lxml")
        title_element = soup.select_one(".QuestionHeader-title")
        title = title_element.text.strip() if title_element else ""
        content = soup.select_one(".RichContent-inner")
        if content is not None:
            for style in content.select("style"):
                style.decompose()
        content = str(content)
        content = clean_markdown(markdownify(content))
        result = {"title": title, "text": content, "url": url}
    elif "substack.com" in url:
        soup = BeautifulSoup(response.text, "lxml")
        title_element = soup.select_one(".post-title")
        title = title_element.text.strip() if title_element else ""
        content = str(soup.select_one(".available-content"))
        content = clean_markdown(markdownify(content))
        result = {"title": title, "text": content, "url": url}
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
    elif "github.com" in url:
        soup = BeautifulSoup(response.text, "lxml")
        if len(soup.select("readme-toc article")) > 0:
            content = str(soup.select_one("readme-toc article"))
        else:
            content = response.text
        content = clean_markdown(markdownify(content))
        title_element = soup.select_one("head title")
        title = title_element.text.strip() if title_element else ""
        result = {"title": title, "text": content, "url": url}
    else:
        doc = Document(response.content)
        result = {
            "title": doc.title(),
            "text": markdownify(doc.summary()),
            "url": url,
        }

    return result
