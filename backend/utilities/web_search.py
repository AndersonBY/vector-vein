"""Structured web search using explicitly configured provider credentials."""
from urllib.parse import quote, urlsplit

from utilities.workflow_errors import WorkflowInputError


DEEPSEEK_SEARCH_ENDPOINT = "https://api.deepseek.com/v1/tools/search"


def search_pages(client, settings, engine, query, count):
    if not isinstance(query, str) or not query.strip():
        raise WorkflowInputError("搜索词不能为空。")
    if type(count) is not int or not 1 <= count <= 50:
        raise WorkflowInputError("搜索结果数量必须是 1 到 50 的整数。")
    if engine == "deepseek":
        if len(query) > 128:
            raise WorkflowInputError("DeepSeek 搜索词不能超过 128 个字符。")
        key = settings.get("web_search.deepseek.api_key", "")
        if not isinstance(key, str) or not key.strip():
            raise WorkflowInputError("请先在设置 → 网络搜索 → DeepSeek 中配置 API Key。")
        endpoint = settings.get("web_search.deepseek.endpoint", DEEPSEEK_SEARCH_ENDPOINT)
        try:
            url = urlsplit(endpoint)
            if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.fragment:
                raise ValueError()
            url.port
        except (TypeError, ValueError):
            raise WorkflowInputError("DeepSeek 搜索接口地址必须是有效的 HTTP/HTTPS URL。") from None
        try:
            response = client.post(endpoint, headers={"Authorization": f"Bearer {key.strip()}", "Content-Type": "application/json"},
                                   json={"query": query, "count": count, "need_content": False}, timeout=60)
        except Exception:
            raise RuntimeError("DeepSeek 搜索连接失败或超时，请检查接口地址及网络后重试。") from None
        if response.status_code != 200:
            reason = {401: "API Key 无效，请检查网络搜索配置。", 402: "账号余额不足，请充值后重试。",
                      429: "请求过于频繁，请稍后重试。"}.get(response.status_code, "请检查搜索参数或稍后重试。")
            raise RuntimeError(f"DeepSeek 搜索失败（HTTP {response.status_code}）：{reason}")
        try:
            results = response.json()["results"]
            if not isinstance(results, list) or any(not isinstance(item, dict) or
                any(not isinstance(item.get(field), str) for field in ("title", "url", "snippet")) or
                ("summary" in item and not isinstance(item["summary"], str)) for item in results):
                raise ValueError()
            return [{"title": item["title"], "url": item["url"], "content": item["snippet"] or item.get("summary") or ""}
                    for item in results[:count]]
        except (KeyError, TypeError, ValueError):
            raise RuntimeError("DeepSeek 搜索返回了无效的结果格式。") from None
    if engine == "jina.ai":
        headers = {"Accept": "application/json"}
        key = settings.get("web_search.jinaai.api_key", "")
        if key:
            headers["Authorization"] = f"Bearer {key}"
        try:
            response = client.get(f"https://s.jina.ai/{quote(query, safe='')}", headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data.get("code") != 200 or not isinstance(data.get("data"), list):
                raise ValueError()
            return data["data"][:count]
        except Exception:
            raise RuntimeError("Jina 搜索失败，请检查 API Key、网络连接或稍后重试。") from None
    raise WorkflowInputError("该搜索引擎已不受支持，请在文本搜索节点中重新选择 DeepSeek 或 Jina。")
